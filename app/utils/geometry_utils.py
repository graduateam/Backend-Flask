"""
기하학 관련 유틸리티 함수 및 클래스
충돌 예측에 사용되는 기하학적 계산 도구 모음
"""
import math
from app.utils.coord_utils import calculate_offset_coordinates
from app.utils.logger import setup_logger
from config import CAR_LENGTH, CAR_WIDTH

# 로거 설정
logger = setup_logger(__name__)

class VehicleRectangle:
    def __init__(self, center_lat, center_lon, heading_deg, length=CAR_LENGTH, width=CAR_WIDTH):
        """
        차량을 나타내는 직사각형 객체

        Parameters:
        center_lat, center_lon: float - 차량 중심 좌표 (위도, 경도)
        heading_deg: float - 차량 진행 방향 (도, 북쪽이 0도, 시계방향)
        length: float - 차량 길이 (미터, 기본값 4.5m)
        width: float - 차량 너비 (미터, 기본값 2.0m)
        """
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.heading_deg = heading_deg
        self.length = length
        self.width = width

        # 차량 직사각형의 네 모서리 좌표 계산
        self.corners = self._calculate_corners()

    def _calculate_corners(self):
        """차량 직사각형의 네 모서리 좌표 계산"""
        # 차량 전후좌우 방향으로의 반 길이/너비
        half_length = self.length / 2
        half_width = self.width / 2

        # 전방 좌/우 모서리 (forward left/right)
        fl_lat, fl_lon = calculate_offset_coordinates(
            self.center_lat, self.center_lon,
            math.sqrt(half_length ** 2 + half_width ** 2),
            (self.heading_deg + math.degrees(math.atan2(half_width, half_length))) % 360
        )

        fr_lat, fr_lon = calculate_offset_coordinates(
            self.center_lat, self.center_lon,
            math.sqrt(half_length ** 2 + half_width ** 2),
            (self.heading_deg - math.degrees(math.atan2(half_width, half_length))) % 360
        )

        # 후방 좌/우 모서리 (backward left/right)
        bl_lat, bl_lon = calculate_offset_coordinates(
            self.center_lat, self.center_lon,
            math.sqrt(half_length ** 2 + half_width ** 2),
            (self.heading_deg + 180 - math.degrees(math.atan2(half_width, half_length))) % 360
        )

        br_lat, br_lon = calculate_offset_coordinates(
            self.center_lat, self.center_lon,
            math.sqrt(half_length ** 2 + half_width ** 2),
            (self.heading_deg + 180 + math.degrees(math.atan2(half_width, half_length))) % 360
        )

        return [(fl_lat, fl_lon), (fr_lat, fr_lon), (br_lat, br_lon), (bl_lat, bl_lon)]


def latlon_to_cartesian(lat, lon, ref_lat, ref_lon):
    """
    위도/경도를 기준점으로부터의 미터 단위 좌표로 변환

    Parameters:
    lat, lon: 변환할 좌표
    ref_lat, ref_lon: 기준점 좌표

    Returns:
    (x, y): 미터 단위의 카르테시안 좌표
    """
    # 위도 1도 = 약 111,320m (지구 반경 * π/180)
    # 경도 1도 = 약 111,320m * cos(위도) (적도에서 멀어질수록 감소)
    lat_meters = 111320
    lon_meters = 111320 * math.cos(math.radians(ref_lat))

    x = (lon - ref_lon) * lon_meters
    y = (lat - ref_lat) * lat_meters

    return (x, y)


def cartesian_to_latlon(x, y, ref_lat, ref_lon):
    """
    카르테시안 좌표(미터 단위)를 위도/경도 좌표로 변환

    Parameters:
    x, y: float - 카르테시안 좌표 (미터)
    ref_lat, ref_lon: float - 기준점 좌표 (위도, 경도)

    Returns:
    (lat, lon): tuple - 변환된 위도, 경도 좌표
    """
    # 위도 1도 = 약 111,320m
    # 경도 1도 = 약 111,320m * cos(위도) (적도에서 멀어질수록 감소)
    lat_meters = 111320
    lon_meters = 111320 * math.cos(math.radians(ref_lat))

    # 미터 단위에서 도 단위로 변환
    lat = ref_lat + y / lat_meters
    lon = ref_lon + x / lon_meters

    return (lat, lon)


def do_segments_intersect(p1, p2, p3, p4):
    """
    두 선분 p1-p2와 p3-p4가 교차하는지 확인
    """

    # 선분 p1-p2를 기준으로 p3와 p4의 방향 확인
    def direction(p1, p2, p):
        return (p[0] - p1[0]) * (p2[1] - p1[1]) - (p2[0] - p1[0]) * (p[1] - p1[1])

    d1 = direction(p3, p4, p1)
    d2 = direction(p3, p4, p2)
    d3 = direction(p1, p2, p3)
    d4 = direction(p1, p2, p4)

    # 두 선분이 교차하는 경우
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
            ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True

    # 한 선분의 끝점이 다른 선분 위에 있는 경우
    if d1 == 0 and is_point_on_segment(p3, p4, p1):
        return True
    if d2 == 0 and is_point_on_segment(p3, p4, p2):
        return True
    if d3 == 0 and is_point_on_segment(p1, p2, p3):
        return True
    if d4 == 0 and is_point_on_segment(p1, p2, p4):
        return True

    return False


def is_point_on_segment(p1, p2, p):
    """
    점 p가 선분 p1-p2 위에 있는지 확인
    """
    return (p[0] <= max(p1[0], p2[0]) and p[0] >= min(p1[0], p2[0]) and
            p[1] <= max(p1[1], p2[1]) and p[1] >= min(p1[1], p2[1]))


def do_rectangles_intersect(rect1_corners, rect2_corners):
    """
    두 직사각형이 교차하는지 확인

    Parameters:
    rect1_corners, rect2_corners: list - 각 직사각형의 모서리 좌표 리스트 [(lat1, lon1), (lat2, lon2), ...]

    Returns:
    bool: 교차 여부
    """
    # 각 직사각형의 변들을 확인
    # 첫 번째 직사각형의 변들
    edges1 = [
        (rect1_corners[0], rect1_corners[1]),
        (rect1_corners[1], rect1_corners[2]),
        (rect1_corners[2], rect1_corners[3]),
        (rect1_corners[3], rect1_corners[0])
    ]

    # 두 번째 직사각형의 변들
    edges2 = [
        (rect2_corners[0], rect2_corners[1]),
        (rect2_corners[1], rect2_corners[2]),
        (rect2_corners[2], rect2_corners[3]),
        (rect2_corners[3], rect2_corners[0])
    ]

    # 모든 변 조합에 대해 교차 확인
    for edge1 in edges1:
        for edge2 in edges2:
            if do_segments_intersect(edge1[0], edge1[1], edge2[0], edge2[1]):
                return True

    # 한 직사각형이 다른 직사각형 내부에 완전히 포함되는 경우 확인
    # 한 직사각형의 모서리가 다른 직사각형 내부에 있는지 확인
    def is_point_in_rectangle(p, rect_corners):
        # 점이 직사각형 내부에 있는지 확인 (ray casting 알고리즘)
        x, y = p
        inside = False
        j = len(rect_corners) - 1
        for i in range(len(rect_corners)):
            if ((rect_corners[i][1] > y) != (rect_corners[j][1] > y)) and \
                    (x < rect_corners[i][0] + (rect_corners[j][0] - rect_corners[i][0]) *
                     (y - rect_corners[i][1]) / (rect_corners[j][1] - rect_corners[i][1])):
                inside = not inside
            j = i
        return inside

    # 첫 번째 직사각형의 모서리가 두 번째 직사각형 내부에 있는지
    for corner in rect1_corners:
        if is_point_in_rectangle(corner, rect2_corners):
            return True

    # 두 번째 직사각형의 모서리가 첫 번째 직사각형 내부에 있는지
    for corner in rect2_corners:
        if is_point_in_rectangle(corner, rect1_corners):
            return True

    return False