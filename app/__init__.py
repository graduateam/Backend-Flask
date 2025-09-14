"""
Flask 애플리케이션 초기화
애플리케이션 팩토리 패턴 구현
"""
from flask import Flask
from flask_socketio import SocketIO
from app.utils.logger import setup_logger, setup_root_logger

# 로거 설정
logger = setup_logger(__name__)

# 전역으로 사용할 socketio 객체 생성 (Threading 모드로 강제)
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

def create_app(config_object='config'):
    """
    Flask 애플리케이션 생성 및 초기화

    Parameters:
    config_object: str - 설정 객체 경로

    Returns:
    Flask - 초기화된 Flask 애플리케이션
    """
    # 앱 생성
    app = Flask(__name__)

    # 루트 로거 설정
    setup_root_logger()

    # 설정 로드
    app.config.from_object(config_object)
    app.secret_key = app.config['SECRET_KEY']

    # 모듈 등록
    register_extensions(app)
    register_blueprints(app)
    register_socketio_handlers()

    # 초기화 로그
    logger.info('Flask 애플리케이션 초기화 완료')

    return app

def register_extensions(app):
    """
    확장 모듈 등록 - 모바일 최적화 모드

    Parameters:
    flask_app: Flask - Flask 애플리케이션 인스턴스
    """
    # 🚫 Socket.IO 비활성화 (웹 실시간 통신 불필요, 모바일 성능 최적화)
    # Socket.IO 초기화
    # socketio.init_app(app)
    pass

def register_blueprints(app):
    """
    블루프린트 등록 - 환경 변수 기반 선택적 활성화

    Parameters:
    flask_app: Flask - Flask 애플리케이션 인스턴스
    """
    import os
    
    # 🎛️ 환경 변수로 웹 인터페이스 활성화 여부 결정
    enable_web = os.environ.get('ENABLE_WEB_INTERFACE', 'false').lower() in ('true', '1', 't', 'yes')
    
    if enable_web:
        # 🌐 디버그/개발 모드: 웹 인터페이스 활성화 (비디오 확인용)
        from app.views.main import register_main_blueprint
        register_main_blueprint(app)
        
        # 필요시 관리자 API도 활성화
        from app.apis.api import register_api_blueprint
        register_api_blueprint(app)
        
        logger.info('🌐 개발 모드: 웹 인터페이스 + 모바일 API 활성화')
        print("🌐 비디오 스트림: http://localhost:5000/video_feed")
        print("🌐 웹 인터페이스: http://localhost:5000/")
    else:
        logger.info('📱 운영 모드: 모바일 API 전용 (최고 성능)')
        print("📱 모바일 전용 모드 (웹 비활성화)")

    # ✅ 모바일 API는 항상 활성화
    from app.apis.mobile_api import register_mobile_api_blueprint
    register_mobile_api_blueprint(app)

def register_socketio_handlers():
    """Socket.IO 이벤트 핸들러 등록 - 모바일 최적화로 비활성화"""
    # 🚫 Socket.IO 핸들러 비활성화 (웹 실시간 통신 불필요)
    # from app.socket import events
    # logger.info('Socket.IO 이벤트 핸들러 등록 완료')
    pass