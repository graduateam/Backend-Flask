"""
Flask 애플리케이션 초기화
애플리케이션 팩토리 패턴 구현
"""
from flask import Flask
from flask_socketio import SocketIO
from app.utils.logger import setup_logger, setup_root_logger

# 로거 설정
logger = setup_logger(__name__)

# 전역으로 사용할 socketio 객체 생성
socketio = SocketIO(cors_allowed_origins="*")

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
    확장 모듈 등록

    Parameters:
    flask_app: Flask - Flask 애플리케이션 인스턴스
    """
    # Socket.IO 초기화
    socketio.init_app(app)

def register_blueprints(app):
    """
    블루프린트 등록

    Parameters:
    flask_app: Flask - Flask 애플리케이션 인스턴스
    """
    # 메인 뷰 블루프린트
    from app.views.main import register_main_blueprint
    register_main_blueprint(app)

    # API 블루프린트
    from app.apis.api import register_api_blueprint
    register_api_blueprint(app)

    logger.info('모든 블루프린트 등록 완료')

def register_socketio_handlers():
    """Socket.IO 이벤트 핸들러 등록"""
    from app.socket import events
    logger.info('Socket.IO 이벤트 핸들러 등록 완료')