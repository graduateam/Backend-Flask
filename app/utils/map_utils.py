"""
지도 관련 유틸리티 함수
"""
import json
from datetime import datetime


def create_vehicle_geojson(vehicle_id, lat, lon, heading, speed, rectangle_coords=None, is_collision_risk=False, ttc=None):
    """
    차량 객체를 GeoJSON 형식으로 변환

    Parameters:
    vehicle_id: int - 차량 ID
    lat, lon: float - 차량 중심 좌표
    heading: float - 차량 진행 방향 (도)
    speed: float - 차량 속도 (m/s)
    rectangle_coords: list - 차량 직사각형 모서리 좌표 [(lat1, lon1), ...] (선택 사항)
    is_collision_risk: bool - 충돌 위험 여부
    ttc: float - 충돌 예상 시간 (초, 선택 사항)

    Returns:
    dict - GeoJSON 형식 데이터
    """
    properties = {
        'id': vehicle_id,
        'type': 'vehicle',
        'heading': float(heading),
        'speed': float(speed),
        'speed_kph': round(speed * 3.6, 1),  # m/s를 km/h로 변환
        'timestamp': datetime.now().isoformat(),
        'is_collision_risk': is_collision_risk
    }

    if ttc is not None:
        properties['ttc'] = ttc

    # 기본 포인트 피처
    geojson = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [lon, lat]  # GeoJSON은 [경도, 위도] 순서
        },
        'properties': properties
    }

    # 직사각형 좌표가 있는 경우 폴리곤 추가
    if rectangle_coords:
        # GeoJSON 형식에 맞게 변환 [경도, 위도] 순서로 변경하고 첫 점을 마지막에 반복
        polygon_coords = [[coord[1], coord[0]] for coord in rectangle_coords]
        polygon_coords.append([polygon_coords[0][0], polygon_coords[0][1]])  # 폴리곤 닫기

        geojson['rectangle'] = {
            'type': 'Feature',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [polygon_coords]
            }
        }

    return geojson


def create_collision_geojson(collision_id, vehicle_ids, collision_point, ttc):
    """
    충돌 예측 정보를 GeoJSON 형식으로 변환

    Parameters:
    collision_id: str - 충돌 ID (예: '1_2'는 차량 1과 2 사이의 충돌)
    vehicle_ids: list - 충돌 관련 차량 ID 목록
    collision_point: tuple - 충돌 예상 지점 (위도, 경도)
    ttc: float - 충돌 예상 시간 (초)

    Returns:
    dict - GeoJSON 형식 데이터
    """
    return {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [collision_point[1], collision_point[0]]  # GeoJSON은 [경도, 위도] 순서
        },
        'properties': {
            'id': collision_id,
            'type': 'collision',
            'vehicle_ids': vehicle_ids,
            'ttc': ttc,
            'timestamp': datetime.now().isoformat()
        }
    }


def create_path_geojson(vehicle_id, path_points, predicted_points=None):
    """
    차량 경로를 GeoJSON 형식으로 변환

    Parameters:
    vehicle_id: int - 차량 ID
    path_points: list - 경로 좌표 목록 [(위도1, 경도1), (위도2, 경도2), ...]
    predicted_points: list - 예측 경로 좌표 목록 (선택 사항)

    Returns:
    dict - GeoJSON 형식 데이터
    """
    # 좌표 순서 변환 (위도, 경도) -> (경도, 위도)
    line_coords = [[point[1], point[0]] for point in path_points]

    geojson = {
        'type': 'Feature',
        'geometry': {
            'type': 'LineString',
            'coordinates': line_coords
        },
        'properties': {
            'id': f'path_{vehicle_id}',
            'vehicle_id': vehicle_id,
            'type': 'path'
        }
    }

    # 예측 경로가 있는 경우 추가
    if predicted_points:
        predicted_coords = [[point[1], point[0]] for point in predicted_points]
        geojson['predicted_path'] = {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': predicted_coords
            }
        }

    return geojson


def create_map_data_payload(vehicles, collisions, paths=None, video_boundary=None):
    """
    지도 데이터를 클라이언트에 전송할 형식으로 변환

    Parameters:
    vehicles: list - 차량 GeoJSON 객체 목록
    collisions: list - 충돌 GeoJSON 객체 목록
    paths: list - 경로 GeoJSON 객체 목록 (선택 사항)
    video_boundary: dict - 비디오 프레임 경계 GeoJSON (선택 사항)

    Returns:
    str - JSON 문자열
    """
    payload = {
        'vehicles': vehicles,
        'collisions': collisions
    }

    if paths:
        payload['paths'] = paths

    if video_boundary:
        payload['video_boundary'] = video_boundary

    return json.dumps(payload)