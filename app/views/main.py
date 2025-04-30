"""
메인 웹 페이지 뷰 - HTML 템플릿 렌더링 엔드포인트
"""
from flask import Blueprint, render_template, Response, request, jsonify
import base64
import cv2
import numpy as np
from app.services.streaming import generate_frames, video_stream
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

@main_bp.route('/receive_camera_frame', methods=['POST'])
def receive_camera_frame():
    """
    라즈베리파이 카메라에서 전송된 프레임을 수신
    """
    try:
        data = request.get_json()
        if not data or 'frame' not in data:
            return jsonify({'success': False, 'message': '프레임 데이터가 없습니다'}), 400

        # Base64 인코딩된 프레임 디코딩
        frame_base64 = data['frame']
        img_data = base64.b64decode(frame_base64)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({'success': False, 'message': '프레임 디코딩 실패'}), 400

        # video_stream 객체에 프레임 업데이트
        video_stream.update(frame)

        return jsonify({'success': True, 'message': '프레임 수신 완료'})

    except Exception as e:
        logger.error(f"카메라 프레임 수신 오류: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500