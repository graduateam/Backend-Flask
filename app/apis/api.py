"""
API 엔드포인트 정의
데이터 API 요청을 처리하는 모듈
"""
from flask import Blueprint, jsonify, request
from app.services.video_processor import video_processor
from app.services.streaming import video_stream
from app.utils.coord_utils import CoordinateTransformer
from app.utils.logger import setup_logger
import config
import cv2
import numpy as np
import base64

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

@api_bp.route('/camera-sources')
def get_camera_sources():
    """
    사용 가능한 카메라 소스 목록 반환
    """
    sources = [
        {
            'id': source_id,
            'name': config.CAMERA_NAMES.get(source_id, source_id),
            'path': config.CAMERA_SOURCES[source_id]
        }
        for source_id in config.CAMERA_SOURCES
    ]

    return jsonify({
        'success': True,
        'sources': sources,
        'current_source': video_processor.current_source
    })

@api_bp.route('/video-bounds')
def get_video_bounds():
    """비디오 프레임의 경계를 위도, 경도 좌표로 반환"""
    try:
        # 비디오 해상도 가져오기 (기본값 설정)
        width, height = 640, 480
        if video_processor.cap is not None:
            width = int(video_processor.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(video_processor.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

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

@api_bp.route('/change-source', methods=['POST'])
def change_source():
    """
    비디오 소스 변경 엔드포인트
    """
    try:
        data = request.get_json()
        if not data or 'source' not in data:
            return jsonify({'success': False, 'message': '소스 정보가 없습니다'}), 400

        source = data['source']

        # 유효한 소스인지 확인
        if source not in config.CAMERA_SOURCES:
            return jsonify({'success': False, 'message': f'유효하지 않은 소스: {source}'}), 400

        # 처리 중지
        video_processor.stop_processing()

        # 소스 변경
        video_processor.set_camera_source(source)

        # 처리 재시작
        result = video_processor.start_processing()

        return jsonify({
            'success': True,
            'message': f'비디오 소스가 {config.CAMERA_NAMES.get(source, source)}로 변경되었습니다',
            'source_info': {
                'id': source,
                'name': config.CAMERA_NAMES.get(source, source),
                'path': config.CAMERA_SOURCES[source]
            }
        })
    except Exception as e:
        error_msg = f"소스 변경 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({'success': False, 'message': error_msg}), 500


@api_bp.route('/receive_camera_frame', methods=['POST'])
def receive_camera_frame():
    """
    외부 카메라에서 전송된 프레임을 수신
    """
    try:
        data = request.get_json()
        if not data or 'frame' not in data:
            return jsonify({'success': False, 'message': '프레임 데이터가 없습니다'}), 400

        # 카메라 ID 확인 (기본값: camera_0)
        camera_id = data.get('camera_id', 'camera_0')

        # 유효한 카메라 ID인지 확인
        if camera_id not in config.CAMERA_SOURCES or camera_id == 'file':
            return jsonify({
                'success': False,
                'message': f'유효하지 않은 카메라 ID: {camera_id}'
            }), 400

        # 현재 활성화된 소스인 경우만 프레임 처리
        is_active = video_processor.current_source == camera_id

        # 현재 활성화된 소스가 아니면 프레임 처리 스킵 (선택적으로 저장)
        if not is_active:
            return jsonify({
                'success': True,
                'message': f'카메라 {camera_id}가 현재 활성화되지 않음',
                'is_active': False
            })

        # 현재 활성화된 소스인 경우 프레임 처리
        # Base64 인코딩된 프레임 디코딩
        frame_base64 = data['frame']
        img_data = base64.b64decode(frame_base64)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({'success': False, 'message': '프레임 디코딩 실패'}), 400

        # 해당 카메라 프레임 업데이트
        logger.info(f"프레임 수신 및 처리: {camera_id}, 크기: {frame.shape}")
        result = video_processor.set_camera_frame(camera_id, frame)

        if not result:
            return jsonify({
                'success': False,
                'message': f'카메라 {camera_id} 프레임 업데이트 실패'
            }), 500

        return jsonify({
            'success': True,
            'message': f'카메라 {camera_id} 프레임 수신 및 처리 완료',
            'is_active': True
        })
    except Exception as e:
        logger.error(f"카메라 프레임 수신 오류: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500