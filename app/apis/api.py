"""
API 엔드포인트 정의
데이터 API 요청을 처리하는 모듈
"""
from flask import Blueprint, jsonify
from app.services.video_processor import video_processor
from app.utils.coord_utils import CoordinateTransformer
from app.utils.logger import setup_logger
import config

# 로거 설정
logger = setup_logger(__name__)

# API 블루프린트 생성 (URL 접두사 추가)
api_bp = Blueprint('api', __name__, url_prefix='/api')

def register_api_blueprint(app):
    """
    API 블루프린트 등록 함수

    Parameters:
    flask_app: Flask - Flask 애플리케이션 인스턴스
    """
    app.register_blueprint(api_bp)
    logger.info('API 블루프린트 등록 완료')

# 좌표 변환기 초기화
transformer = CoordinateTransformer(
    image_points=config.IMAGE_POINTS,
    world_points=config.WORLD_POINTS
)

@api_bp.route('/status')
def status():
    """처리 상태 정보 엔드포인트"""
    return jsonify(video_processor.get_status())

@api_bp.route('/video-bounds')
def get_video_bounds():
    """비디오 프레임의 경계를 위도, 경도 좌표로 반환"""
    try:
        # 비디오 해상도 가져오기 (기본값 설정)
        width, height = 640, 480
        if video_processor.cap is not None:
            width = int(video_processor.cap.get(1))
            height = int(video_processor.cap.get(2))

        # 비디오 프레임의 4개 모서리 좌표
        corners = [
            (0, 0),
            (width, 0),
            (width, height),
            (0, height)
        ]

        # 각 모서리를 위도, 경도로 변환
        geo_corners = []
        for x, y in corners:
            try:
                lat, lon = transformer.image_to_world((x, y))
                geo_corners.append([lat, lon])
            except Exception as e:
                logger.error(f"좌표 변환 오류: {str(e)}")
                # 변환 실패 시 기본값은 None으로 설정하여 클라이언트 측에서 처리
                geo_corners.append(None)

        return jsonify({
            'success': True,
            'video_size': {'width': width, 'height': height},
            'corners': geo_corners
        })
    except Exception as e:
        logger.error(f"비디오 경계 계산 오류: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@api_bp.route('/start-processing')
def start_processing():
    """비디오 처리 시작 엔드포인트"""
    try:
        result = video_processor.start_processing()
        return jsonify(result)
    except Exception as e:
        error_msg = f"처리 시작 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({'success': False, 'message': error_msg})

@api_bp.route('/stop-processing')
def stop_processing():
    """비디오 처리 중지 엔드포인트"""
    try:
        result = video_processor.stop_processing()
        return jsonify(result)
    except Exception as e:
        error_msg = f"처리 중지 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({'success': False, 'message': error_msg})