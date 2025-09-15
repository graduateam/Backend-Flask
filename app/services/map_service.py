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
        self.risk_details_cache = {}     # 위험도 세부 정보 캐시

    def generate_map_data(self, detected_objects, predictor, video_stream, prediction_result=None):
        """
        지도 업데이트를 위한 데이터 생성

        Parameters:
        detected_objects: list - 감지된 객체 목록
        predictor: UpgradedCollisionPredictor - 충돌 예측기 객체
        video_stream: VideoStream - 비디오 스트림 객체
        prediction_result: dict - 이미 계산된 예측 결과

        Returns:
        dict or None - 지도 데이터 딕셔너리 또는 None
        """
        if not detected_objects or not predictor:
            return None

        try:
            # 이미 계산된 예측 결과가 있으면 사용하고, 없으면 새로 계산
            if prediction_result is None:
                prediction_result = predictor.update_from_detection(detected_objects)

            # 결과 추출
            objects = prediction_result['objects']
            collisions = prediction_result['collisions']
            collision_points = prediction_result['collision_points']
            risk_details = prediction_result.get('risk_details', {})

            # 위험도 세부 정보 캐시 업데이트
            self.risk_details_cache = risk_details

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
                width, height = 480, 360

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
                    'coordinates': [[coord[1], coord[0]] for coord in geo_corners]
                },
                'properties': {
                    'type': 'camera_boundary',
                    'timestamp': time.time()
                }
            }

            # 차량 GeoJSON 데이터 생성
            for obj_id, obj_info in objects.items():
                # 해당 객체의 최대 위험도 및 세부 정보 찾기
                max_risk_score = 0
                detailed_risk_info = None

                for (id1, id2), risk_score in collisions.items():
                    if obj_id == id1 or obj_id == id2:
                        if risk_score > max_risk_score:
                            max_risk_score = risk_score
                            # 위험도 세부 정보 가져오기
                            pair_key = (min(id1, id2), max(id1, id2))
                            detailed_risk_info = risk_details.get(pair_key, {})

                # 차량 GeoJSON 생성
                vehicle_geojson = create_enhanced_vehicle_geojson(
                    vehicle_id=obj_id,
                    lat=obj_info['coords'][0],
                    lon=obj_info['coords'][1],
                    heading=float(obj_info['heading']),
                    speed=float(obj_info['speed']),
                    rectangle_coords=obj_info['rectangle'],
                    is_collision_risk=obj_id in self.collision_risk_ids,
                    risk_score=max_risk_score,
                    risk_details=detailed_risk_info
                )
                vehicles_geojson.append(vehicle_geojson)

                # 경로 GeoJSON 생성
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
            for (id1, id2), risk_score in collisions.items():
                if (id1, id2) in collision_points:
                    collision_point = collision_points[(id1, id2)]

                    # 위험도 세부 정보 가져오기
                    detailed_risk = risk_details.get((id1, id2), {})

                    collision_geojson = create_enhanced_collision_geojson(
                        collision_id=f"{id1}_{id2}",
                        vehicle_ids=[id1, id2],
                        collision_point=collision_point,
                        risk_score=risk_score,
                        risk_details=detailed_risk
                    )
                    collisions_geojson.append(collision_geojson)

            # 클라이언트에 전송할 데이터 패키지 생성
            map_data = create_enhanced_map_data_payload(
                vehicles_geojson,
                collisions_geojson,
                paths_geojson,
                video_boundary_geojson,
                risk_details  # 위험도 세부 정보 추가
            )

            return map_data

        except Exception as e:
            logger.error(f"지도 데이터 생성 오류: {str(e)}")
            return None

    def get_risk_summary(self):
        """
        현재 위험도 요약 정보 반환

        Returns:
        dict - 위험도 요약 정보
        """
        if not self.risk_details_cache:
            return {
                'status': 'safe',
                'max_risk': 0,
                'warning_count': 0,
                'risk_distribution': {'safe': 0, 'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
            }

        # 최대 위험도 및 분포 계산
        risk_scores = [details.get('total_risk', 0) for details in self.risk_details_cache.values()]
        max_risk = max(risk_scores) if risk_scores else 0
        warning_count = len([r for r in risk_scores if r >= 60])

        # 위험도 분포 계산
        risk_distribution = {'safe': 0, 'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        for score in risk_scores:
            if score < 40:
                risk_distribution['safe'] += 1
            elif score < 55:
                risk_distribution['low'] += 1
            elif score < 70:
                risk_distribution['medium'] += 1
            elif score < 85:
                risk_distribution['high'] += 1
            else:
                risk_distribution['critical'] += 1

        # 상태 결정
        if max_risk >= 85:
            status = 'critical'
        elif max_risk >= 70:
            status = 'high'
        elif max_risk >= 55:
            status = 'medium'
        elif max_risk >= 40:
            status = 'low'
        else:
            status = 'safe'

        return {
            'status': status,
            'max_risk': max_risk,
            'warning_count': warning_count,
            'risk_distribution': risk_distribution,
            'total_pairs': len(self.risk_details_cache)
        }


def create_enhanced_vehicle_geojson(vehicle_id, lat, lon, heading, speed, rectangle_coords=None,
                                  is_collision_risk=False, risk_score=0, risk_details=None):
    """
    위험도 정보가 포함된 차량 GeoJSON 생성

    Parameters:
    vehicle_id: int - 차량 ID
    lat, lon: float - 차량 중심 좌표
    heading: float - 차량 진행 방향 (도)
    speed: float - 차량 속도 (m/s)
    rectangle_coords: list - 차량 직사각형 모서리 좌표
    is_collision_risk: bool - 충돌 위험 여부
    risk_score: float - 위험도 점수 (0-100)
    risk_details: dict - 위험도 세부 정보

    Returns:
    dict - 향상된 GeoJSON 형식 데이터
    """
    properties = {
        'id': vehicle_id,
        'type': 'vehicle',
        'heading': float(heading),
        'speed': float(speed),
        'speed_kph': round(speed * 3.6, 1),
        'timestamp': time.time(),
        'is_collision_risk': is_collision_risk,
        'risk_score': float(risk_score)
    }

    # 위험도 레벨 결정
    if risk_score >= 85:
        risk_level = 'critical'
    elif risk_score >= 70:
        risk_level = 'high'
    elif risk_score >= 55:
        risk_level = 'medium'
    elif risk_score >= 40:
        risk_level = 'low'
    else:
        risk_level = 'safe'

    properties['risk_level'] = risk_level

    # 위험도 세부 정보 추가
    if risk_details:
        properties['risk_breakdown'] = {
            'distance_risk': float(risk_details.get('distance_risk', 0)),
            'relative_speed_risk': float(risk_details.get('relative_speed_risk', 0)),
            'convergence_risk': float(risk_details.get('convergence_risk', 0)),
            'time_risk': float(risk_details.get('time_risk', 0)),
            'distance_meters': float(risk_details.get('distance_meters', 0))
        }

    # 기본 포인트 피처
    geojson = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [lon, lat]
        },
        'properties': properties
    }

    # 직사각형 좌표가 있는 경우 폴리곤 추가
    if rectangle_coords:
        polygon_coords = [[coord[1], coord[0]] for coord in rectangle_coords]
        polygon_coords.append([polygon_coords[0][0], polygon_coords[0][1]])

        geojson['rectangle'] = {
            'type': 'Feature',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [polygon_coords]
            }
        }

    return geojson


def create_enhanced_collision_geojson(collision_id, vehicle_ids, collision_point, risk_score, risk_details=None):
    """
    위험도 정보가 포함된 충돌 예측 GeoJSON 생성

    Parameters:
    collision_id: str - 충돌 ID
    vehicle_ids: list - 충돌 관련 차량 ID 목록
    collision_point: tuple - 충돌 예상 지점 (위도, 경도)
    risk_score: float - 위험도 점수 (0-100)
    risk_details: dict - 위험도 세부 정보

    Returns:
    dict - 향상된 GeoJSON 형식 데이터
    """
    # 기존 TTC 계산 (하위 호환성)
    ttc = risk_details.get('time_risk', 0) if risk_details else 0
    if ttc > 0:
        # 시간 위험도를 TTC로 역산 (근사치)
        ttc = max(0.1, (100 - ttc) / 20)  # 대략적인 변환

    properties = {
        'id': collision_id,
        'type': 'collision',
        'vehicle_ids': vehicle_ids,
        'risk_score': float(risk_score),
        'ttc': float(ttc),  # 하위 호환성을 위해 유지
        'timestamp': time.time()
    }

    # 위험도 레벨 결정
    if risk_score >= 85:
        risk_level = 'critical'
    elif risk_score >= 70:
        risk_level = 'high'
    elif risk_score >= 55:
        risk_level = 'medium'
    elif risk_score >= 40:
        risk_level = 'low'
    else:
        risk_level = 'safe'

    properties['risk_level'] = risk_level

    # 위험도 세부 정보 추가
    if risk_details:
        properties['risk_breakdown'] = {
            'distance_risk': float(risk_details.get('distance_risk', 0)),
            'relative_speed_risk': float(risk_details.get('relative_speed_risk', 0)),
            'convergence_risk': float(risk_details.get('convergence_risk', 0)),
            'time_risk': float(risk_details.get('time_risk', 0)),
            'distance_meters': float(risk_details.get('distance_meters', 0))
        }

    return {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [collision_point[1], collision_point[0]]
        },
        'properties': properties
    }


def create_enhanced_map_data_payload(vehicles, collisions, paths=None, video_boundary=None, risk_details=None):
    """
    향상된 지도 데이터를 클라이언트에 전송할 형식으로 변환

    Parameters:
    vehicles: list - 차량 GeoJSON 객체 목록
    collisions: list - 충돌 GeoJSON 객체 목록
    paths: list - 경로 GeoJSON 객체 목록
    video_boundary: dict - 비디오 프레임 경계 GeoJSON
    risk_details: dict - 위험도 세부 정보

    Returns:
    dict - 향상된 JSON 데이터
    """
    payload = {
        'vehicles': vehicles,
        'collisions': collisions,
        'timestamp': time.time()
    }

    if paths:
        payload['paths'] = paths

    if video_boundary:
        payload['video_boundary'] = video_boundary

    # 위험도 세부 정보 추가 (클라이언트에서 상세 분석용)
    if risk_details:
        # 키를 문자열로 변환 (JSON 직렬화를 위해)
        formatted_risk_details = {}
        for (id1, id2), details in risk_details.items():
            key = f"{id1},{id2}"
            formatted_risk_details[key] = details
        payload['risk_details'] = formatted_risk_details

    # 전체 위험도 요약 추가
    if risk_details:
        risk_scores = [details.get('total_risk', 0) for details in risk_details.values()]
        max_risk = max(risk_scores) if risk_scores else 0
        warning_count = len([r for r in risk_scores if r >= 60])

        payload['risk_summary'] = {
            'max_risk': max_risk,
            'warning_count': warning_count,
            'active_pairs': len(risk_details)
        }
    else:
        payload['risk_summary'] = {
            'max_risk': 0,
            'warning_count': 0,
            'active_pairs': 0
        }

    return payload