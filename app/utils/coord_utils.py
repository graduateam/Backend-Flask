"""
좌표 변환 및 계산을 위한 유틸리티 함수
"""
import cv2
import numpy as np
import math


class CoordinateTransformer:
    def __init__(self, image_points, world_points):
        """
        좌표 변환기 초기화

        Parameters:
        image_points: np.array - 이미지 상의 픽셀 좌표
        world_points: np.array - 실제 세계 좌표 (위도, 경도)
        """
        self.image_points = np.array(image_points, dtype=np.float32)
        self.world_points = np.array(world_points, dtype=np.float32)

        # Homography 행렬 계산
        self.H, _ = cv2.findHomography(self.image_points, self.world_points)
        self.H_inv = np.linalg.inv(self.H)

    def image_to_world(self, image_coords):
        """
        이미지 좌표를 실세계 좌표로 변환

        Parameters:
        image_coords: tuple - 이미지 픽셀 좌표 (x, y)

        Returns:
        tuple - 실세계 좌표 (위도, 경도)
        """
        image_coords_homogeneous = np.array([image_coords[0], image_coords[1], 1]).reshape(3, 1)
        world_coords_homogeneous = np.dot(self.H, image_coords_homogeneous)
        world_coords = world_coords_homogeneous / world_coords_homogeneous[2]
        lat = world_coords[0][0]
        lon = world_coords[1][0]
        return lat, lon

    def world_to_image(self, world_coords):
        """
        실세계 좌표를 이미지 좌표로 변환

        Parameters:
        world_coords: tuple - 실세계 좌표 (위도, 경도)

        Returns:
        tuple - 이미지 픽셀 좌표 (x, y)
        """
        world_coords_homogeneous = np.array([world_coords[0], world_coords[1], 1]).reshape(3, 1)
        image_coords_homogeneous = np.dot(self.H_inv, world_coords_homogeneous)
        image_coords = image_coords_homogeneous / image_coords_homogeneous[2]
        x = int(image_coords[0][0])
        y = int(image_coords[1][0])
        return x, y


# 위도/경도 -> 실제 거리로 변환하는 함수 (기존에 사용하다가 로직 수정하면서 더이상 쓰이지 않는 함수. 지우지 않고 일단 유지)
def calculate_distance(lat1, lon1, lat2, lon2):
    """
    위도, 경도 좌표 간 거리 계산 (Haversine 공식)

    Parameters:
    lat1, lon1: float - 첫 번째 좌표
    lat2, lon2: float - 두 번째 좌표

    Returns:
    float - 거리 (미터)
    """
    # 지구 반경 (미터)
    R = 6371000.0

    # 위도, 경도를 라디안으로 변환
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine 공식
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c

    return distance


def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    두 좌표 사이의 방위각 계산

    Parameters:
    lat1, lon1: float - 첫 번째 좌표
    lat2, lon2: float - 두 번째 좌표

    Returns:
    float - 방위각 (도, 북쪽이 0도, 시계방향)
    """
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    y = math.sin(lon2_rad - lon1_rad) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(
        lon2_rad - lon1_rad)
    bearing = math.atan2(y, x)

    # 라디안에서 도로 변환 (0-360도)
    bearing_deg = math.degrees(bearing)
    if bearing_deg < 0:
        bearing_deg += 360

    return bearing_deg


def calculate_offset_coordinates(lat, lon, distance_meters, bearing_deg):
    """
    위도, 경도 기준점에서 특정 거리와 방향으로 떨어진 좌표 계산

    Parameters:
    lat, lon: float - 기준 좌표
    distance_meters: float - 오프셋 거리 (미터)
    bearing_deg: float - 방향 (도, 북쪽이 0도, 시계방향)

    Returns:
    tuple - 새 좌표 (위도, 경도)
    """
    R = 6371000  # 지구 반경 (미터)

    distance_km = distance_meters / 1000.0

    # 도를 라디안으로 변환
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing_deg)

    # 새 위도 계산
    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(distance_km / R) +
        math.cos(lat_rad) * math.sin(distance_km / R) * math.cos(bearing_rad)
    )

    # 새 경도 계산
    new_lon_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(distance_km / R) * math.cos(lat_rad),
        math.cos(distance_km / R) - math.sin(lat_rad) * math.sin(new_lat_rad)
    )

    # 라디안에서 도로 변환
    new_lat = math.degrees(new_lat_rad)
    new_lon = math.degrees(new_lon_rad)

    return new_lat, new_lon