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
from config import CAR_LENGTH, CAR_WIDTH, TTC_THRESHOLD, RISK_THRESHOLD

# 로거 설정
logger = setup_logger(__name__)

class CollisionPredictor:
    def __init__(self, history_size=10, car_length=CAR_LENGTH, car_width=CAR_WIDTH,
                 ttc_threshold=TTC_THRESHOLD, risk_threshold=RISK_THRESHOLD):
        """
        업그레이드된 충돌 예측기 초기화

        Parameters:
        history_size: int - 위치 이력 저장 크기
        car_length: float - 차량 길이 (미터)
        car_width: float - 차량 너비 (미터)
        ttc_threshold: float - 충돌 경고 임계값 (초)
        risk_threshold: float - 위험도 점수 임계값 (0-100)
        """
        self.objects = {}  # 객체 ID를 키로 하는 딕셔너리
        self.history_size = history_size
        self.car_length = car_length
        self.car_width = car_width
        self.ttc_threshold = ttc_threshold
        self.risk_threshold = risk_threshold

        # 결과 저장
        self.collision_warnings = {}  # 충돌 경고 표시할 객체 쌍과 위험도 점수 {(id1, id2): risk_score}
        self.collision_points = {}  # 충돌 예상 지점 {(id1, id2): (lat, lon)}
        self.risk_details = {}  # 위험도 세부 정보 {(id1, id2): detailed_scores}
        self.reference_position = None  # 카르테시안 좌표계 변환을 위한 기준점

        # 위험도 가중치 설정 (총 100%)
        self.weights = {
            'relative_speed': 0.35,    # 상대속도 위험도 - 35%
            'distance': 0.30,          # 거리 기반 위험도 - 30%
            'direction_convergence': 0.20,  # 방향 수렴도 위험도 - 20%
            'time_based': 0.15         # 시간 기반 위험도(TTC) - 15%
        }

        # 위험도 계산을 위한 임계값들
        self.thresholds = {
            'min_distance': 5.0,       # 최소 안전 거리 (미터)
            'max_distance': 50.0,      # 최대 감지 거리 (미터)
            'max_relative_speed': 20.0, # 최대 상대속도 (m/s, 약 72km/h)
            'critical_ttc': 1.0,       # 치명적 TTC (초)
            'safe_ttc': 8.0           # 안전 TTC (초)
        }

        logger.info(f"업그레이드된 충돌 예측기 초기화: 위험도 임계값={risk_threshold}점")

    def update(self, obj_id, lat, lon, timestamp):
        """
        객체 위치 업데이트 (기존과 동일)
        """
        # 기준점 설정
        if self.reference_position is None:
            self.reference_position = (lat, lon)

        # 새 객체 등록 또는 기존 객체 이력 업데이트
        if obj_id not in self.objects:
            self.objects[obj_id] = {
                'positions': deque(maxlen=self.history_size),
                'cart_positions': deque(maxlen=self.history_size),
                'timestamps': deque(maxlen=self.history_size),
                'velocity': (0, 0),
                'acceleration': (0, 0),
                'speed': 0,
                'heading': 0,
                'rectangle': None
            }

        # 위치 및 시간 이력 추가
        self.objects[obj_id]['positions'].append((lat, lon))

        # 카르테시안 좌표 계산 및 저장
        cart_pos = latlon_to_cartesian(lat, lon,
                                      self.reference_position[0],
                                      self.reference_position[1])
        self.objects[obj_id]['cart_positions'].append(cart_pos)
        self.objects[obj_id]['timestamps'].append(timestamp)

        # 속도 및 방향 계산
        if len(self.objects[obj_id]['positions']) >= 2:
            self._calculate_velocity_and_heading(obj_id)

            # 가속도 계산
            if len(self.objects[obj_id]['positions']) >= 3:
                self._calculate_acceleration(obj_id)

    def update_from_detection(self, detected_objects):
        """
        감지된 객체 목록에서 업데이트
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
                    'rectangle': self.objects[obj_id]['rectangle'].corners if self.objects[obj_id]['rectangle'] else None,
                    'class_id': obj.get('class_id', -1),
                    'class_name': obj.get('class_name', 'unknown')
                }

        # 비활성 객체 정리
        self.clean_inactive_objects(current_time)

        # 충돌 예측 수행 (점수 기반 시스템)
        risk_scores = self.predict_collisions_by_risk_score()

        return {
            'objects': updated_objects,
            'collisions': risk_scores,
            'collision_points': self.collision_points,
            'risk_details': self.risk_details
        }

    def _calculate_velocity_and_heading(self, obj_id):
        """객체의 속도와 방향 계산"""
        pos_prev = self.objects[obj_id]['positions'][-2]
        pos_curr = self.objects[obj_id]['positions'][-1]
        cart_prev = self.objects[obj_id]['cart_positions'][-2]
        cart_curr = self.objects[obj_id]['cart_positions'][-1]
        time_prev = self.objects[obj_id]['timestamps'][-2]
        time_curr = self.objects[obj_id]['timestamps'][-1]

        dt = time_curr - time_prev
        if dt <= 0:
            return

        dx = cart_curr[0] - cart_prev[0]
        dy = cart_curr[1] - cart_prev[1]

        vx = dx / dt
        vy = dy / dt
        speed = math.sqrt(vx**2 + vy**2)
        heading = calculate_bearing(pos_prev[0], pos_prev[1], pos_curr[0], pos_curr[1])

        self.objects[obj_id]['velocity'] = (vx, vy)
        self.objects[obj_id]['speed'] = speed
        self.objects[obj_id]['heading'] = heading

        self.objects[obj_id]['rectangle'] = VehicleRectangle(
            pos_curr[0], pos_curr[1], heading, self.car_length, self.car_width
        )

    def _calculate_acceleration(self, obj_id):
        """객체의 가속도 계산 (기존과 동일)"""
        if len(self.objects[obj_id]['cart_positions']) < 3:
            return

        pos_t0 = self.objects[obj_id]['cart_positions'][-3]
        pos_t1 = self.objects[obj_id]['cart_positions'][-2]
        pos_t2 = self.objects[obj_id]['cart_positions'][-1]

        time_t0 = self.objects[obj_id]['timestamps'][-3]
        time_t1 = self.objects[obj_id]['timestamps'][-2]
        time_t2 = self.objects[obj_id]['timestamps'][-1]

        dt1 = time_t1 - time_t0
        dt2 = time_t2 - time_t1

        if dt1 <= 0 or dt2 <= 0:
            return

        vx1 = (pos_t1[0] - pos_t0[0]) / dt1
        vy1 = (pos_t1[1] - pos_t0[1]) / dt1
        vx2 = (pos_t2[0] - pos_t1[0]) / dt2
        vy2 = (pos_t2[1] - pos_t1[1]) / dt2

        ax = (vx2 - vx1) / ((dt1 + dt2) / 2)
        ay = (vy2 - vy1) / ((dt1 + dt2) / 2)

        self.objects[obj_id]['acceleration'] = (ax, ay)

    def predict_collisions_by_risk_score(self):
        """
        점수 기반 충돌 예측 시스템

        Returns:
        dict - 위험도 점수가 임계값 이상인 객체 쌍 {(id1, id2): risk_score}
        """
        self.collision_warnings = {}
        self.collision_points = {}
        self.risk_details = {}

        obj_ids = list(self.objects.keys())

        for i in range(len(obj_ids)):
            for j in range(i + 1, len(obj_ids)):
                id1, id2 = obj_ids[i], obj_ids[j]

                # 두 객체가 모두 유효한 정보를 갖고 있는지 확인
                if (self.objects[id1]['rectangle'] is None or
                    self.objects[id2]['rectangle'] is None or
                    len(self.objects[id1]['positions']) < 2 or
                    len(self.objects[id2]['positions']) < 2):
                    continue

                # 위험도 점수 계산
                risk_score, risk_breakdown = self._calculate_risk_score(id1, id2)

                # 위험도가 임계값 이상인 경우 경고 추가
                if risk_score >= self.risk_threshold:
                    pair_key = (min(id1, id2), max(id1, id2))
                    self.collision_warnings[pair_key] = risk_score
                    self.risk_details[pair_key] = risk_breakdown

                    # 충돌 예상 지점 계산
                    collision_point = self._estimate_collision_point(id1, id2)
                    if collision_point:
                        self.collision_points[pair_key] = collision_point

        return self.collision_warnings

    def _calculate_risk_score(self, id1, id2):
        """
        두 객체 간의 위험도 점수 계산

        Returns:
        tuple: (총 위험도 점수, 세부 점수 딕셔너리)
        """
        # 현재 위치와 속도 정보
        pos1 = self.objects[id1]['cart_positions'][-1]
        pos2 = self.objects[id2]['cart_positions'][-1]
        vel1 = np.array(self.objects[id1]['velocity'])
        vel2 = np.array(self.objects[id2]['velocity'])

        # 1. 거리 기반 위험도 (30%)
        distance_risk = self._calculate_distance_risk(pos1, pos2)

        # 2. 상대속도 위험도 (35%)
        relative_speed_risk = self._calculate_relative_speed_risk(pos1, pos2, vel1, vel2)

        # 3. 방향 수렴도 위험도 (20%)
        convergence_risk = self._calculate_direction_convergence_risk(id1, id2, pos1, pos2, vel1, vel2)

        # 4. 시간 기반 위험도 (15%)
        time_risk = self._calculate_time_based_risk(pos1, pos2, vel1, vel2)

        # 가중 평균으로 총 위험도 계산
        total_risk = (
            distance_risk * self.weights['distance'] +
            relative_speed_risk * self.weights['relative_speed'] +
            convergence_risk * self.weights['direction_convergence'] +
            time_risk * self.weights['time_based']
        ) * 100  # 0-100점 스케일로 변환

        risk_breakdown = {
            'total_risk': total_risk,
            'distance_risk': distance_risk * 100,
            'relative_speed_risk': relative_speed_risk * 100,
            'convergence_risk': convergence_risk * 100,
            'time_risk': time_risk * 100,
            'distance_meters': np.linalg.norm(np.array(pos2) - np.array(pos1))
        }

        return total_risk, risk_breakdown

    def _calculate_distance_risk(self, pos1, pos2):
        """
        거리 기반 위험도 계산 (0-1)
        가까울수록 위험도 증가
        """
        distance = np.linalg.norm(np.array(pos2) - np.array(pos1))

        if distance <= self.thresholds['min_distance']:
            return 1.0  # 최대 위험
        elif distance >= self.thresholds['max_distance']:
            return 0.0  # 위험 없음
        else:
            # 거리에 반비례하는 위험도 (지수 감소)
            normalized_distance = (distance - self.thresholds['min_distance']) / (
                self.thresholds['max_distance'] - self.thresholds['min_distance']
            )
            return math.exp(-3 * normalized_distance)  # 지수적 감소

    def _calculate_relative_speed_risk(self, pos1, pos2, vel1, vel2):
        """
        상대속도 위험도 계산 (0-1)
        접근 속도가 빠를수록 위험도 증가
        """
        # 상대 위치 벡터
        relative_pos = np.array(pos2) - np.array(pos1)
        # 상대 속도 벡터
        relative_vel = vel2 - vel1

        # 두 차량이 서로 접근하고 있는지 확인 (내적이 음수면 접근)
        if np.dot(relative_pos, relative_vel) >= 0:
            return 0.0  # 멀어지고 있으면 위험 없음

        # 접근 속도 (상대속도의 크기)
        relative_speed = np.linalg.norm(relative_vel)

        if relative_speed <= 0.1:  # 거의 정지 상태
            return 0.0
        elif relative_speed >= self.thresholds['max_relative_speed']:
            return 1.0  # 최대 위험
        else:
            # 상대속도에 비례하는 위험도
            return min(1.0, relative_speed / self.thresholds['max_relative_speed'])

    def _calculate_direction_convergence_risk(self, id1, id2, pos1, pos2, vel1, vel2):
        """
        방향 수렴도 위험도 계산 (0-1)
        진행 방향이 교차점으로 수렴할수록 위험도 증가
        """
        # 속도가 너무 낮으면 방향 분석 불가
        speed1 = np.linalg.norm(vel1)
        speed2 = np.linalg.norm(vel2)
        if speed1 < 0.5 or speed2 < 0.5:  # 1.8km/h 미만
            return 0.3  # 저속에서는 중간 정도 위험도

        # 진행 방향 벡터 (단위 벡터)
        dir1 = vel1 / speed1
        dir2 = vel2 / speed2

        # 현재 상대 위치
        relative_pos = np.array(pos2) - np.array(pos1)
        distance = np.linalg.norm(relative_pos)

        if distance < 0.1:  # 너무 가까운 경우
            return 1.0

        # 각 차량이 상대방 쪽으로 향하고 있는지 확인
        # 차량1이 차량2 방향으로 향하는 정도
        approach1 = np.dot(dir1, relative_pos / distance)
        # 차량2가 차량1 방향으로 향하는 정도
        approach2 = np.dot(dir2, -relative_pos / distance)

        # 두 차량 모두 서로를 향해 접근하고 있는 경우
        if approach1 > 0 and approach2 > 0:
            # 진행 방향 간의 각도 (내적 이용)
            dot_product = np.dot(dir1, dir2)
            dot_product = np.clip(dot_product, -1.0, 1.0)
            angle = math.acos(abs(dot_product))  # 0 ~ π/2

            # 직각에 가까울수록 위험 (교차로 상황)
            # π/2 (90도)에서 최대 위험도
            angle_risk = math.sin(angle)  # 90도에서 1.0

            # 접근 정도에 따른 가중치
            approach_factor = min(approach1, approach2)

            return angle_risk * approach_factor
        else:
            # 한 방향으로만 접근하거나 멀어지는 경우
            return max(0, (approach1 + approach2) / 4)  # 낮은 위험도

    def _calculate_time_based_risk(self, pos1, pos2, vel1, vel2):
        """
        시간 기반 위험도 계산 (0-1)
        """
        # 상대 위치와 속도
        relative_pos = np.array(pos2) - np.array(pos1)
        relative_vel = vel2 - vel1

        # 접근하고 있지 않으면 위험 없음
        if np.dot(relative_pos, relative_vel) >= 0:
            return 0.0

        # TTC 계산
        relative_speed = np.linalg.norm(relative_vel)
        if relative_speed < 0.1:
            return 0.0

        distance = np.linalg.norm(relative_pos)
        ttc = distance / relative_speed

        if ttc <= self.thresholds['critical_ttc']:
            return 1.0  # 최대 위험
        elif ttc >= self.thresholds['safe_ttc']:
            return 0.0  # 안전
        else:
            # TTC에 반비례하는 위험도
            normalized_ttc = (ttc - self.thresholds['critical_ttc']) / (
                self.thresholds['safe_ttc'] - self.thresholds['critical_ttc']
            )
            return 1.0 - normalized_ttc

    def _estimate_collision_point(self, id1, id2):
        """
        충돌 예상 지점 계산
        """
        pos1 = self.objects[id1]['cart_positions'][-1]
        pos2 = self.objects[id2]['cart_positions'][-1]
        vel1 = np.array(self.objects[id1]['velocity'])
        vel2 = np.array(self.objects[id2]['velocity'])

        # 간단한 선형 예측으로 교차점 찾기
        # 두 직선의 교점 계산
        try:
            # 시간 t에서의 위치: pos + vel * t
            # 교점 조건: pos1 + vel1 * t1 = pos2 + vel2 * t2

            # 가장 가까워지는 시점을 찾기
            relative_pos = np.array(pos2) - np.array(pos1)
            relative_vel = vel2 - vel1

            if np.linalg.norm(relative_vel) < 0.1:
                # 상대속도가 거의 0이면 중점 반환
                collision_cart = ((pos1[0] + pos2[0]) / 2, (pos1[1] + pos2[1]) / 2)
            else:
                # 최근접 시간 계산
                t = -np.dot(relative_pos, relative_vel) / np.dot(relative_vel, relative_vel)
                t = max(0, min(t, 10))  # 0-10초 범위로 제한

                # 교점 계산 (두 예측 위치의 중점)
                future_pos1 = np.array(pos1) + vel1 * t
                future_pos2 = np.array(pos2) + vel2 * t
                collision_cart = ((future_pos1[0] + future_pos2[0]) / 2,
                                (future_pos1[1] + future_pos2[1]) / 2)

            # 카르테시안 좌표를 위도/경도로 변환
            return cartesian_to_latlon(
                collision_cart[0], collision_cart[1],
                self.reference_position[0], self.reference_position[1]
            )
        except:
            # 계산 오류 시 중점 반환
            return cartesian_to_latlon(
                (pos1[0] + pos2[0]) / 2, (pos1[1] + pos2[1]) / 2,
                self.reference_position[0], self.reference_position[1]
            )

    def clean_inactive_objects(self, current_time, max_inactive_time=3.0):
        """비활성 객체 제거"""
        inactive_ids = []
        for obj_id, obj_data in self.objects.items():
            if len(obj_data['timestamps']) > 0:
                last_seen = obj_data['timestamps'][-1]
                if current_time - last_seen > max_inactive_time:
                    inactive_ids.append(obj_id)

        for obj_id in inactive_ids:
            del self.objects[obj_id]

    def get_object_info(self, obj_id):
        """특정 객체의 정보 반환"""
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
        """모든 객체의 정보 반환"""
        objects_info = {}
        for obj_id in self.objects:
            objects_info[obj_id] = self.get_object_info(obj_id)
        return objects_info

    def get_risk_summary(self):
        """
        현재 위험도 요약 정보 반환
        """
        if not self.risk_details:
            return {"status": "safe", "max_risk": 0, "warning_count": 0}

        max_risk = max(details['total_risk'] for details in self.risk_details.values())
        warning_count = len(self.collision_warnings)

        if max_risk >= 90:
            status = "critical"
        elif max_risk >= 70:
            status = "high"
        elif max_risk >= 50:
            status = "medium"
        else:
            status = "low"

        return {
            "status": status,
            "max_risk": max_risk,
            "warning_count": warning_count,
            "risk_details": self.risk_details
        }