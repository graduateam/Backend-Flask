"""
애플리케이션 설정 파일
"""

# 지도 API 키 설정
MAP_API_KEY = "19qidy68bi"  # 네이버맵 클라이언트 ID

# 좌표 변환을 위한 설정
# 이미지 좌표 (픽셀 좌표)
IMAGE_POINTS = [
    [77, 432],
    [232, 84],
    [553, 166],
    [544, 329]
]

# 실제 세계 좌표 (위도, 경도)
WORLD_POINTS = [
    [37.33934640, 126.73506978],
    [37.33905404, 126.73476155],
    [37.33933618, 126.73464326],
    [37.33942127, 126.73483341]
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
DEFAULT_CAMERA_SOURCE = "camera_0"

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

# 중복 객체 탐지 설정
DUPLICATE_DETECTION_SETTINGS = {
    'enabled': True,                       # 중복 객체 탐지 활성화
    'distance_threshold': 5.0,             # 중복 판정 거리 임계값 (미터)
    'gps_priority': True                   # GPS 위치를 카메라 탐지보다 우선시
}

# 고급 매칭 검증 설정
ADVANCED_MATCHING_SETTINGS = {
    'enabled': True,                       # 고급 매칭 검증 활성화
    'validation_interval': 1.0,            # 검증 주기 (초) - 성능 최적화
    'confidence_threshold': 0.7,           # 재매칭 트리거 신뢰도 임계값
    'rematch_cooldown': 1.5,               # 재매칭 쿨다운 (초) - 빠른 반응
    'max_history_entries': 5,              # 매칭 히스토리 최대 보관 개수 - 메모리 최적화
    'inactive_user_cleanup_interval': 300, # 비활성 사용자 정리 간격 (초)
    
    # 검증 가중치
    'validation_weights': {
        'distance_consistency': 0.5,       # 거리 일관성 가중치 (높임)
        'movement_pattern': 0.3,           # 움직임 패턴 가중치 (낮춤)
        'object_persistence': 0.2          # 객체 지속성 가중치
    },
    
    # 움직임 패턴 허용 오차
    'movement_tolerances': {
        'speed_diff_threshold': 3.0,       # 속도 차이 허용 오차 (m/s) - GPS 노이즈 고려
        'heading_diff_threshold': 45.0,    # 방향 차이 허용 오차 (도) - 더 관대하게
        'min_speed_for_heading': 1.0       # 방향 검증 최소 속도 (m/s)
    },
    
    # 거리 일관성 검증 (단순화)
    'distance_validation': {
        'max_jump_threshold': 5.0,         # 최대 허용 거리 점프 (미터) - GPS 정확도 고려
        'gps_noise_threshold': 3.0         # GPS 노이즈 허용 범위 (미터)
    },
    
    # 객체 지속성 검증
    'persistence_validation': {
        'min_detection_time': 1.0,         # 최소 탐지 시간 (초)
        'disappear_penalty': 0.3,          # 객체 사라짐 페널티
        'new_object_penalty': 0.2          # 새 객체 페널티
    },
    
    # 점수 기본값 (하드코딩 값들을 설정으로 이동)
    'scoring_defaults': {
        'initial_high_score': 0.8,         # 초기 매칭 시 높은 점수
        'distance_jump_penalty': 0.2,      # 거리 점프 감지 시 점수
        'default_confidence': 0.5,         # 기본 신뢰도
        'no_history_score': 0.7,          # 히스토리 없을 때 점수
        'persistence_full_score': 1.0      # 완전한 지속성 점수
    }
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