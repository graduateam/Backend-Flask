"""
지도 데이터 처리 서비스
지도 업데이트를 위한 데이터 생성 및 변환 담당
"""
import time
from app.utils.logger import setup_logger
from app.utils.map_utils import create_vehicle_geojson, create_collision_geojson, create_path_geojson, \
    create_map_data_payload

# 로거 설정
logger = setup_logger(__name__)


class MapDataService:
    """지도 데이터 생성 및 관리 서비스"""

    def __init__(self, transformer=None):
        """
        지도 데이터 서비스 초기화

        Parameters:
        transformer: CoordinateTransformer - 좌표 변환기 객체
        """
        self.transformer = transformer
        self.collision_risk_ids = set()  # 충돌 위험이 있는 객체 ID 저장

    def generate_map_data(self, detected_objects, predictor, video_stream, prediction_result=None):
        """
        지도 업데이트를 위한 데이터 생성

        Parameters:
        detected_objects: list - 감지된 객체 목록
        predictor: CollisionPredictor - 충돌 예측기 객체
        video_stream: VideoStream - 비디오 스트림 객체
        prediction_result: dict - 이미 계산된 예측 결과 (있는 경우)

        Returns:
        dict or None - 지도 데이터 딕셔너리 또는 None
        """
        if not detected_objects or not predictor:
            return None

        try:
            # 이미 계산된 예측 결과가 있으면 사용하고, 없으면 새로 계산
            if prediction_result is None:
                # 충돌 예측 수행 (새로 계산)
                prediction_result = predictor.update_from_detection(detected_objects)

            # 결과 추출
            objects = prediction_result['objects']
            collisions = prediction_result['collisions']
            collision_points = prediction_result['collision_points']

            # 충돌 위험 객체 ID 업데이트
            self.collision_risk_ids.clear()
            for (id1, id2) in collisions.keys():
                self.collision_risk_ids.add(id1)
                self.collision_risk_ids.add(id2)

            # 예측 결과가 있는 경우에만 데이터 생성
            if not objects:
                return None

            # 지도 데이터 준비
            vehicles_geojson = []
            collisions_geojson = []
            paths_geojson = []

            # 비디오 프레임 경계 계산
            frame = video_stream.get_frame()
            if frame is not None:
                height, width = frame.shape[:2]
            else:
                width, height = 640, 480

            # 프레임 모서리 좌표
            frame_corners = [
                [0, 0],
                [width, 0],
                [width, height],
                [0, height]
            ]

            # 경계 좌표를 지리적 좌표로 변환
            geo_corners = []
            for corner in frame_corners:
                try:
                    if self.transformer:
                        lat, lon = self.transformer.image_to_world(corner)
                        geo_corners.append([lat, lon])
                except Exception as e:
                    logger.error(f"좌표 변환 오류: {str(e)}")

            # 폴리곤을 닫기 위해 첫 번째 점을 다시 추가
            if geo_corners:
                geo_corners.append(geo_corners[0])

            # 비디오 프레임 경계 GeoJSON 생성
            video_boundary_geojson = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[coord[1], coord[0]] for coord in geo_corners]  # GeoJSON은 [경도, 위도] 순서
                },
                'properties': {
                    'type': 'camera_boundary',
                    'timestamp': time.time()
                }
            }

            # 차량 GeoJSON 데이터 생성
            for obj_id, obj_info in objects.items():
                # 충돌 위험 여부 확인
                is_collision_risk = False
                min_ttc = float('inf')

                for (id1, id2), ttc in collisions.items():
                    if obj_id == id1 or obj_id == id2:
                        is_collision_risk = True
                        if ttc < min_ttc:
                            min_ttc = ttc

                # 차량 GeoJSON 생성
                vehicle_geojson = create_vehicle_geojson(
                    vehicle_id=obj_id,
                    lat=obj_info['coords'][0],
                    lon=obj_info['coords'][1],
                    heading=float(obj_info['heading']),
                    speed=float(obj_info['speed']),
                    rectangle_coords=obj_info['rectangle'],
                    is_collision_risk=is_collision_risk,
                    ttc=min_ttc if is_collision_risk else None
                )
                vehicles_geojson.append(vehicle_geojson)

                # 경로 GeoJSON 생성 (위치 이력 및 예측 경로)
                if 'predicted_position_3s' in obj_info and obj_info['predicted_position_3s']:
                    path_points = [obj_info['coords']]
                    predicted_points = [obj_info['predicted_position_3s']]
                    path_geojson = create_path_geojson(
                        vehicle_id=obj_id,
                        path_points=path_points,
                        predicted_points=predicted_points
                    )
                    paths_geojson.append(path_geojson)

            # 충돌 GeoJSON 데이터 생성
            for (id1, id2), ttc in collisions.items():
                if (id1, id2) in collision_points:
                    collision_point = collision_points[(id1, id2)]
                    collision_geojson = create_collision_geojson(
                        collision_id=f"{id1}_{id2}",
                        vehicle_ids=[id1, id2],
                        collision_point=collision_point,
                        ttc=ttc
                    )
                    collisions_geojson.append(collision_geojson)

            # 클라이언트에 전송할 데이터 패키지 생성
            map_data = create_map_data_payload(
                vehicles_geojson,
                collisions_geojson,
                paths_geojson,
                video_boundary_geojson
            )

            return map_data

        except Exception as e:
            logger.error(f"지도 데이터 생성 오류: {str(e)}")
            return None