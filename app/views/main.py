"""
메인 웹 페이지 뷰 - HTML 템플릿 렌더링 엔드포인트
"""
from flask import Blueprint, render_template, Response
from app.services.streaming import generate_frames
from app.utils.logger import setup_logger
import config

# 로거 설정
logger = setup_logger(__name__)

# 블루프린트 생성
main_bp = Blueprint('main', __name__)

def register_main_blueprint(app):
    """
    메인 블루프린트 등록 함수

    Parameters:
    flask_app: Flask - Flask 애플리케이션 인스턴스
    """
    app.register_blueprint(main_bp)
    logger.info('메인 블루프린트 등록 완료')

@main_bp.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html',
                          api_key=config.MAP_API_KEY,
                          map_center=config.DEFAULT_MAP_CENTER)

@main_bp.route('/video_feed')
def video_feed():
    """비디오 스트림 엔드포인트"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')