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

# 카메라 소스 설정
CAMERA_SOURCES = {
    "file": "app/static/videos/ilsan_12fps.mp4",  # 저장된 영상
    "camera_0": 0,  # 라즈베리파이 카메라 (ID 0)
    "camera_1": 1,  # 두 번째 카메라 (ID 1)
    # 추가 카메라는 여기에 정의...
    # "camera_2": 2,
    # "camera_3": "rtsp://username:password@ip:port/stream"  # RTSP 스트림도 가능
}

# 카메라 소스 이름
CAMERA_NAMES = {
    "file": "저장된 영상",
    "camera_0": "라즈베리파이 카메라",
    # "camera_1": "카메라 1",
    # "camera_2": "카메라 2",
    # "camera_3": "카메라 3"
}

# 기본 카메라 소스
DEFAULT_CAMERA_SOURCE = "file"

# 차량 설정
CAR_LENGTH = 4.5  # 차량 길이 (미터)
CAR_WIDTH = 2.0   # 차량 너비 (미터)

# 기존 충돌 예측 설정
TTC_THRESHOLD = 4.0  # TTC 임계값 (초)

# 새로운 점수 기반 충돌 예측 설정
RISK_THRESHOLD = 60.0  # 위험도 점수 임계값 (0-100점, 60점 이상 시 경고)

# 위험도 레벨 설정
RISK_LEVELS = {
    'SAFE': {'min': 0, 'max': 40, 'color': '#28a745'},      # 초록색
    'LOW': {'min': 40, 'max': 55, 'color': '#ffc107'},      # 노란색
    'MEDIUM': {'min': 55, 'max': 70, 'color': '#fd7e14'},   # 주황색
    'HIGH': {'min': 70, 'max': 85, 'color': '#dc3545'},     # 빨간색
    'CRITICAL': {'min': 85, 'max': 100, 'color': '#6f42c1'} # 보라색
}

# 골목길 특화 설정
NARROW_ROAD_SETTINGS = {
    'enabled': True,                    # 골목길 모드 활성화
    'distance_threshold_reduction': 0.7, # 감지 거리 임계값 70%로 감소
    'speed_sensitivity_increase': 1.5,   # 속도 민감도 1.5배 증가
    'direction_weight_increase': 1.3     # 방향 수렴도 가중치 1.3배 증가
}

# 실시간 조정 가능한 가중치
ADJUSTABLE_WEIGHTS = {
    'relative_speed': 0.35,    # 상대속도 위험도 - 35%
    'distance': 0.30,          # 거리 기반 위험도 - 30%
    'direction_convergence': 0.20,  # 방향 수렴도 위험도 - 20%
    'time_based': 0.15         # 시간 기반 위험도(TTC) - 15%
}

# 로깅 레벨 설정
LOGGING_LEVEL = {
    'collision_prediction': 'INFO',  # 충돌 예측 모듈 로깅 레벨
    'video_processing': 'INFO',      # 비디오 처리 모듈 로깅 레벨
    'risk_analysis': 'DEBUG'         # 위험도 분석 상세 로깅
}

# 성능 최적화 설정
PERFORMANCE_SETTINGS = {
    'max_objects_per_frame': 20,      # 프레임당 최대 추적 객체 수
    'prediction_update_interval': 0.1, # 예측 업데이트 간격 (초)
    'risk_calculation_threads': 2,     # 위험도 계산 스레드 수
    'enable_gpu_acceleration': True    # GPU 가속 활성화
}

# 디버그 모드
DEBUG = True

# Flask 앱 비밀키
SECRET_KEY = 'collision_prediction_secret_key'

# 알림 설정
NOTIFICATION_SETTINGS = {
    'enable_sound_alerts': True,        # 소리 알림 활성화
    'enable_visual_alerts': True,       # 시각적 알림 활성화
    'alert_duration': 5.0,             # 알림 지속 시간 (초)
    'high_risk_alert_interval': 1.0,   # 고위험 상황 반복 알림 간격 (초)
    'critical_risk_alert_interval': 0.5 # 치명적 위험 반복 알림 간격 (초)
}