"""
벡터 기반 객체 충돌 예측 모델
"""
from collections import deque
import time
import math
import numpy as np
from app.utils.coord_utils import calculate_bearing
from app.utils.geometry_utils import VehicleRectangle, latlon_to_cartesian, cartesian_to_latlon, do_rectangles_intersect
from app.utils.logger import setup_logger
from config import CAR_LENGTH, CAR_WIDTH, TTC_THRESHOLD

# 로거 설정
logger = setup_logger(__name__)

class CollisionPredictor:
    def __init__(self, history_size=10, car_length=CAR_LENGTH, car_width=CAR_WIDTH, ttc_threshold=TTC_THRESHOLD):
        """
        충돌 예측기 초기화

        Parameters:
        history_size: int - 위치 이력 저장 크기
        car_length: float - 차량 길이 (미터)
        car_width: float - 차량 너비 (미터)
        ttc_threshold: float - 충돌 경고 임계값 (초)
        """
        self.objects = {}  # 객체 ID를 키로 하는 딕셔너리
        self.history_size = history_size
        self.car_length = car_length
        self.car_width = car_width
        self.ttc_threshold = ttc_threshold
        self.collision_warnings = {}  # 충돌 경고 표시할 객체 쌍과 TTC 값 {(id1, id2): ttc}
        self.collision_points = {}  # 충돌 예상 지점 {(id1, id2): (lat, lon)}
        self.reference_position = None  # 카르테시안 좌표계 변환을 위한 기준점

        # 초기화 로그
        logger.info(f"충돌 예측기 초기화: 크기={car_length}x{car_width}m, TTC 임계값={ttc_threshold}초, 이력 크기={history_size}")

    def update(self, obj_id, lat, lon, timestamp):
        """
        객체 위치 업데이트

        Parameters:
        obj_id: int - 객체 ID
        lat, lon: float - 객체 위치 (위도, 경도)
        timestamp: float - 현재 시간 (초)
        """
        # 기준점 설정 (첫 번째 객체의 첫 위치를 기준으로 사용)
        if self.reference_position is None:
            self.reference_position = (lat, lon)

        # 새 객체 등록 또는 기존 객체 이력 업데이트
        if obj_id not in self.objects:
            self.objects[obj_id] = {
                'positions': deque(maxlen=self.history_size),  # 위치 이력
                'cart_positions': deque(maxlen=self.history_size),  # 카르테시안 좌표 이력
                'timestamps': deque(maxlen=self.history_size),  # 타임스탬프 이력
                'velocity': (0, 0),  # (x_velocity, y_velocity) in m/s
                'acceleration': (0, 0),  # (x_accel, y_accel) in m/s²
                'speed': 0,  # 속도 (m/s)
                'heading': 0,  # 방향 (도)
                'rectangle': None  # 차량 직사각형 객체
            }

        # 위치 및 시간 이력 추가
        self.objects[obj_id]['positions'].append((lat, lon))

        # 카르테시안 좌표 계산 및 저장
        cart_pos = latlon_to_cartesian(lat, lon,
                                      self.reference_position[0],
                                      self.reference_position[1])
        self.objects[obj_id]['cart_positions'].append(cart_pos)

        self.objects[obj_id]['timestamps'].append(timestamp)

        # 속도 및 방향 계산 (최소 2개 이상의 이력이 있을 때)
        if len(self.objects[obj_id]['positions']) >= 2:
            self._calculate_velocity_and_heading(obj_id)

            # 가속도 계산 (최소 3개 이상의 이력이 있을 때)
            if len(self.objects[obj_id]['positions']) >= 3:
                self._calculate_acceleration(obj_id)

    def update_from_detection(self, detected_objects):
        """
        감지된 객체 목록에서 업데이트

        Parameters:
        detected_objects: list - 감지된 객체 목록

        Returns:
        dict - 업데이트된 객체 정보 포함 딕셔너리
        """
        current_time = time.time()
        updated_objects = {}

        for obj in detected_objects:
            obj_id = obj['id']
            lat, lon = obj['coords']

            # 추적기에 객체 위치 업데이트
            self.update(obj_id, lat, lon, current_time)

            # 업데이트된 객체 정보 저장
            if obj_id in self.objects:

                updated_objects[obj_id] = {
                    'id': obj_id,
                    'coords': (lat, lon),
                    'speed': self.objects[obj_id]['speed'],
                    'heading': self.objects[obj_id]['heading'],
                    'acceleration': self.objects[obj_id]['acceleration'],
                    'rectangle': self.objects[obj_id]['rectangle'].corners if self.objects[obj_id][
                        'rectangle'] else None,
                    'class_id': obj.get('class_id', -1),
                    'class_name': obj.get('class_name', 'unknown')
                }
                logger.debug(f"객체 {obj_id} 정보: 속도={self.objects[obj_id]['speed']}, 방향={self.objects[obj_id]['heading']}")

        # 비활성 객체 정리
        self.clean_inactive_objects(current_time)

        # 충돌 예측 수행
        collisions = self.predict_collisions()

        return {
            'objects': updated_objects,
            'collisions': collisions,
            'collision_points': self.collision_points
        }

    def _calculate_velocity_and_heading(self, obj_id):
        """
        객체의 속도와 방향 계산

        Parameters:
        obj_id: int - 객체 ID
        """
        # 가장 최근 두 지점의 위치와 시간
        pos_prev = self.objects[obj_id]['positions'][-2]
        pos_curr = self.objects[obj_id]['positions'][-1]
        cart_prev = self.objects[obj_id]['cart_positions'][-2]
        cart_curr = self.objects[obj_id]['cart_positions'][-1]
        time_prev = self.objects[obj_id]['timestamps'][-2]
        time_curr = self.objects[obj_id]['timestamps'][-1]

        # 시간 간격 (초)
        dt = time_curr - time_prev
        if dt <= 0:
            return  # 시간 간격이 없으면 계산 불가

        # 카르테시안 좌표에서의 변화 (미터)
        dx = cart_curr[0] - cart_prev[0]
        dy = cart_curr[1] - cart_prev[1]

        # 속도 벡터 계산 (m/s)
        vx = dx / dt
        vy = dy / dt

        # 속력 계산 (m/s)
        speed = math.sqrt(vx**2 + vy**2)

        # 방향 계산 (도)
        heading = calculate_bearing(pos_prev[0], pos_prev[1], pos_curr[0], pos_curr[1])

        # 객체 정보 업데이트
        self.objects[obj_id]['velocity'] = (vx, vy)  # 속도 벡터 (m/s)
        self.objects[obj_id]['speed'] = speed  # 속력 (m/s)
        self.objects[obj_id]['heading'] = heading  # 방향 (도)

        # 현재 위치와 방향을 바탕으로 차량 직사각형 업데이트
        self.objects[obj_id]['rectangle'] = VehicleRectangle(
            pos_curr[0], pos_curr[1], heading, self.car_length, self.car_width
        )
        logger.debug(f"객체 {obj_id} 속도 계산: 위치1={pos_prev}, 위치2={pos_curr}, dt={dt}초")

    def _calculate_acceleration(self, obj_id):
        """
        객체의 가속도 계산 (가장 최근 3개 위치 데이터 사용)

        Parameters:
        obj_id: int - 객체 ID
        """
        if len(self.objects[obj_id]['cart_positions']) < 3 or len(self.objects[obj_id]['timestamps']) < 3:
            return

        # 가장 최근 세 지점의 카르테시안 위치와 시간
        pos_t0 = self.objects[obj_id]['cart_positions'][-3]
        pos_t1 = self.objects[obj_id]['cart_positions'][-2]
        pos_t2 = self.objects[obj_id]['cart_positions'][-1]

        time_t0 = self.objects[obj_id]['timestamps'][-3]
        time_t1 = self.objects[obj_id]['timestamps'][-2]
        time_t2 = self.objects[obj_id]['timestamps'][-1]

        # 시간 간격
        dt1 = time_t1 - time_t0
        dt2 = time_t2 - time_t1

        if dt1 <= 0 or dt2 <= 0:
            return  # 시간 간격이 없으면 계산 불가

        # 각 구간의 속도 계산
        vx1 = (pos_t1[0] - pos_t0[0]) / dt1
        vy1 = (pos_t1[1] - pos_t0[1]) / dt1

        vx2 = (pos_t2[0] - pos_t1[0]) / dt2
        vy2 = (pos_t2[1] - pos_t1[1]) / dt2

        # 가속도 계산 (속도 변화율)
        ax = (vx2 - vx1) / ((dt1 + dt2) / 2)  # 평균 시간 간격 사용
        ay = (vy2 - vy1) / ((dt1 + dt2) / 2)

        # 객체 정보 업데이트
        self.objects[obj_id]['acceleration'] = (ax, ay)  # 가속도 벡터 (m/s²)

    def _predict_position_at_time(self, obj_id, time_delta):
        """
        가속도를 고려하여 특정 시간 후의 위치 예측

        Parameters:
        obj_id: int - 객체 ID
        time_delta: float - 예측 시간 (초)

        Returns:
        (lat, lon): 예측된 위도, 경도 좌표
        """
        if len(self.objects[obj_id]['positions']) == 0:
            return None

        # 현재 위치 (카르테시안)
        current_cart_pos = self.objects[obj_id]['cart_positions'][-1]

        # 속도 및 가속도
        velocity = self.objects[obj_id]['velocity']
        acceleration = self.objects[obj_id]['acceleration']

        # 등가속도 운동 방정식 사용 (s = s₀ + v₀t + ½at²)
        future_x = current_cart_pos[0] + velocity[0] * time_delta + 0.5 * acceleration[0] * time_delta ** 2
        future_y = current_cart_pos[1] + velocity[1] * time_delta + 0.5 * acceleration[1] * time_delta ** 2

        # 카르테시안 좌표를 위도/경도로 다시 변환
        return cartesian_to_latlon(future_x, future_y, self.reference_position[0], self.reference_position[1])

    def _compute_closest_approach_time(self, id1, id2):
        """
        두 객체 간의 최근접 시간 계산 (가속도 고려)

        Parameters:
        id1, id2: int - 객체 ID

        Returns:
        float or None: 최근접 시간 (초), 미래에 발생하지 않으면 None
        """
        # 현재 위치 벡터 (카르테시안 좌표)
        p1 = np.array(self.objects[id1]['cart_positions'][-1])
        p2 = np.array(self.objects[id2]['cart_positions'][-1])

        # 상대 위치 벡터
        r = p2 - p1

        # 속도 벡터
        v1 = np.array(self.objects[id1]['velocity'])
        v2 = np.array(self.objects[id2]['velocity'])

        # 상대 속도 벡터
        v = v2 - v1

        # 가속도 벡터
        a1 = np.array(self.objects[id1]['acceleration'])
        a2 = np.array(self.objects[id2]['acceleration'])

        # 상대 가속도 벡터
        a = a2 - a1

        # 두 객체가 서로 접근하는지 확인
        approaching = np.dot(r, v) < 0
        if not approaching:
            return None  # 서로 멀어지는 중이면 충돌 없음

        # 등가속 운동 케이스
        if np.linalg.norm(a) > 1e-10:
            min_distance = float('inf')
            closest_time = None

            for t in np.linspace(0, self.ttc_threshold, 20):
                # 등가속도 운동 방정식으로 시간 t에서의 상대 위치 계산
                rt = r + v * t + 0.5 * a * t**2
                distance = np.linalg.norm(rt)

                if distance < min_distance:
                    min_distance = distance
                    closest_time = t

            return closest_time

        # 등속 운동 케이스 (가속도가 무시할 만큼 작은 경우)
        else:
            # 속도가 0에 가까우면 최근접 시간 없음
            v_squared = np.dot(v, v)
            if v_squared < 1e-10:
                return None

            # 최근접 시간 = -r·v / |v|²
            t_closest = -np.dot(r, v) / v_squared

            # 과거 시간이면 무시
            if t_closest <= 0:
                return None

            # TTC 임계값보다 크면 무시
            if t_closest > self.ttc_threshold:
                return None

            return t_closest

    def predict_collisions(self):
        """
        벡터 기반 충돌 예측 (가속도 고려 + 최근접 시간 계산 + 직사각형 충돌 검사)

        Returns:
        dict - 충돌 경고 딕셔너리 {(id1, id2): ttc}
        """
        # 충돌 경고 초기화
        self.collision_warnings = {}
        self.collision_points = {}

        # 모든 객체 쌍에 대해 충돌 예측
        obj_ids = list(self.objects.keys())
        for i in range(len(obj_ids)):
            for j in range(i + 1, len(obj_ids)):
                id1, id2 = obj_ids[i], obj_ids[j]

                # 두 객체가 모두 직사각형 정보를 갖고 있는지 확인
                if self.objects[id1]['rectangle'] is None or self.objects[id2]['rectangle'] is None:
                    continue

                # 현재 직사각형이 이미 충돌 중인지 확인
                rect1 = self.objects[id1]['rectangle']
                rect2 = self.objects[id2]['rectangle']

                if do_rectangles_intersect(rect1.corners, rect2.corners):
                    # 이미 충돌 중인 경우
                    self.collision_warnings[(min(id1, id2), max(id1, id2))] = 0.0
                    # 충돌 중인 경우 충돌 지점은 두 객체의 중심점 중간
                    pos1 = self.objects[id1]['positions'][-1]
                    pos2 = self.objects[id2]['positions'][-1]
                    self.collision_points[(min(id1, id2), max(id1, id2))] = (
                        (pos1[0] + pos2[0]) / 2,
                        (pos1[1] + pos2[1]) / 2
                    )
                    continue

                # 벡터 기반으로 가장 가까워지는 시간 계산
                closest_time = self._compute_closest_approach_time(id1, id2)

                if closest_time is not None and closest_time <= self.ttc_threshold:
                    # 해당 시간에 두 객체의 위치 예측
                    future_pos1 = self._predict_position_at_time(id1, closest_time)
                    future_pos2 = self._predict_position_at_time(id2, closest_time)

                    if future_pos1 is None or future_pos2 is None:
                        continue

                    # 해당 시간에 두 직사각형 생성
                    future_rect1 = VehicleRectangle(
                        future_pos1[0], future_pos1[1],
                        self.objects[id1]['heading'],
                        self.car_length, self.car_width
                    )

                    future_rect2 = VehicleRectangle(
                        future_pos2[0], future_pos2[1],
                        self.objects[id2]['heading'],
                        self.car_length, self.car_width
                    )

                    # 직사각형 교차 여부로 충돌 판단
                    if do_rectangles_intersect(future_rect1.corners, future_rect2.corners):
                        self.collision_warnings[(min(id1, id2), max(id1, id2))] = closest_time
                        self.collision_points[(min(id1, id2), max(id1, id2))] = (
                            (future_pos1[0] + future_pos2[0]) / 2,
                            (future_pos1[1] + future_pos2[1]) / 2
                        )

        return self.collision_warnings

    def clean_inactive_objects(self, current_time, max_inactive_time=3.0):
        """
        일정 시간 동안 업데이트되지 않은 객체 제거

        Parameters:
        current_time: float - 현재 시간 (초)
        max_inactive_time: float - 최대 비활성 시간 (초)
        """
        inactive_ids = []
        for obj_id, obj_data in self.objects.items():
            if len(obj_data['timestamps']) > 0:
                last_seen = obj_data['timestamps'][-1]
                if current_time - last_seen > max_inactive_time:
                    inactive_ids.append(obj_id)

        # 비활성 객체 제거
        for obj_id in inactive_ids:
            del self.objects[obj_id]

    def get_object_info(self, obj_id):
        """
        특정 객체의 정보 반환

        Parameters:
        obj_id: int - 객체 ID

        Returns:
        dict - 객체 정보 딕셔너리 또는 None
        """
        if obj_id in self.objects:
            obj = self.objects[obj_id]
            return {
                'id': obj_id,
                'position': obj['positions'][-1] if obj['positions'] else None,
                'speed': obj['speed'],
                'heading': obj['heading'],
                'acceleration': obj['acceleration'],
                'rectangle': obj['rectangle'].corners if obj['rectangle'] else None,
            }
        return None

    def get_all_objects_info(self):
        """
        모든 객체의 정보 반환

        Returns:
        dict - 객체 ID를 키로 하고 객체 정보를 값으로 하는 딕셔너리
        """
        objects_info = {}
        for obj_id in self.objects:
            objects_info[obj_id] = self.get_object_info(obj_id)
        return objects_info