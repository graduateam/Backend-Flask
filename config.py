"""
애플리케이션 설정 파일
"""

# 지도 API 키 설정
MAP_API_KEY = "19qidy68bi"  # 네이버맵 클라이언트 ID

# 좌표 변환을 위한 설정
# 이미지 좌표 (픽셀 좌표)
IMAGE_POINTS = [
    [335, 102],
    [23, 251],
    [584, 234],
    [146, 404]
]

# 실제 세계 좌표 (위도, 경도)
WORLD_POINTS = [
    [37.67675942, 126.74583666],
    [37.67696082, 126.74597894],
    [37.67687015, 126.74558537],
    [37.67703350, 126.74581464]
]

# 초기 지도 중심 좌표 (첫 번째 좌표를 기본값으로 사용)
DEFAULT_MAP_CENTER = {"lat": WORLD_POINTS[0][0], "lng": WORLD_POINTS[0][1]}

# YOLO 모델 경로
MODEL_PATH = 'app/static/yolo_models/0317_best.pt'

# 비디오 소스 설정
VIDEO_SOURCE = 'app/static/videos/ilsan_12fps.mp4'  # 파일 경로 또는 카메라 ID (0, 1, ...)

# 차량 설정
CAR_LENGTH = 4.5  # 차량 길이 (미터)
CAR_WIDTH = 2.0   # 차량 너비 (미터)

# 충돌 예측 설정
TTC_THRESHOLD = 4.0  # 충돌 경고 임계값 (초)

# 디버그 모드
DEBUG = True

# Flask 앱 비밀키
SECRET_KEY = 'collision_prediction_secret_key'