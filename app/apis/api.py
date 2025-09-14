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
import time

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
    status_info = video_processor.get_status()

    # 위험도 요약 정보 추가
    if hasattr(video_processor, 'predictor') and video_processor._is_initialized:
        try:
            risk_summary = video_processor.predictor.get_risk_summary()
            status_info['risk_summary'] = risk_summary
        except Exception as e:
            logger.error(f"위험도 요약 정보 가져오기 오류: {str(e)}")
            status_info['risk_summary'] = {
                'status': 'unknown',
                'max_risk': 0,
                'warning_count': 0
            }

    return jsonify(status_info)

@api_bp.route('/risk-summary')
def get_risk_summary():
    """
    현재 위험도 요약 정보 반환
    """
    try:
        if not video_processor._is_initialized:
            return jsonify({
                'success': False,
                'message': '시스템이 초기화되지 않았습니다'
            }), 400

        # 위험도 요약 정보 가져오기
        risk_summary = video_processor.predictor.get_risk_summary()

        # 추가 통계 정보
        current_objects = len(video_processor.detected_objects) if video_processor.detected_objects else 0

        enhanced_summary = {
            'success': True,
            'timestamp': time.time(),
            'current_objects': current_objects,
            'risk_summary': risk_summary,
            'system_status': {
                'is_processing': video_processor.is_processing,
                'current_source': video_processor.current_source,
                'source_name': config.CAMERA_NAMES.get(video_processor.current_source, video_processor.current_source)
            }
        }

        return jsonify(enhanced_summary)

    except Exception as e:
        error_msg = f"위험도 요약 정보 조회 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({'success': False, 'message': error_msg}), 500

@api_bp.route('/risk-settings', methods=['GET', 'POST'])
def risk_settings():
    """
    위험도 설정 조회 및 수정
    """
    try:
        if request.method == 'GET':
            # 현재 설정 반환
            settings = {
                'risk_threshold': getattr(config, 'RISK_THRESHOLD', 60.0),
                'weights': getattr(config, 'ADJUSTABLE_WEIGHTS', {
                    'relative_speed': 0.35,
                    'distance': 0.30,
                    'direction_convergence': 0.20,
                    'time_based': 0.15
                }),
                'narrow_road_settings': getattr(config, 'NARROW_ROAD_SETTINGS', {
                    'enabled': True,
                    'distance_threshold_reduction': 0.7,
                    'speed_sensitivity_increase': 1.5,
                    'direction_weight_increase': 1.3
                })
            }

            return jsonify({
                'success': True,
                'settings': settings
            })

        elif request.method == 'POST':
            # 설정 업데이트
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': '설정 데이터가 없습니다'}), 400

            # 위험도 임계값 업데이트
            if 'risk_threshold' in data:
                new_threshold = float(data['risk_threshold'])
                if 0 <= new_threshold <= 100:
                    if video_processor._is_initialized:
                        video_processor.predictor.risk_threshold = new_threshold
                        logger.info(f"위험도 임계값이 {new_threshold}로 업데이트됨")
                else:
                    return jsonify({'success': False, 'message': '위험도 임계값은 0-100 사이여야 합니다'}), 400

            # 가중치 업데이트
            if 'weights' in data:
                weights = data['weights']
                # 가중치 합이 1.0인지 확인
                total_weight = sum(weights.values())
                if abs(total_weight - 1.0) > 0.01:
                    return jsonify({'success': False, 'message': '가중치 합이 1.0이어야 합니다'}), 400

                if video_processor._is_initialized:
                    video_processor.predictor.weights.update(weights)
                    logger.info(f"가중치가 업데이트됨: {weights}")

            return jsonify({
                'success': True,
                'message': '설정이 성공적으로 업데이트되었습니다'
            })

    except Exception as e:
        error_msg = f"위험도 설정 처리 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({'success': False, 'message': error_msg}), 500

@api_bp.route('/risk-history')
def get_risk_history():
    """
    위험도 이력 정보 반환 (최근 1시간)
    """
    try:
        # 간단한 구현: 현재 상태만 반환 (실제로는 데이터베이스나 파일에 저장된 이력 사용)
        if not video_processor._is_initialized:
            return jsonify({
                'success': False,
                'message': '시스템이 초기화되지 않았습니다'
            })

        current_risk = video_processor.predictor.get_risk_summary()

        # 샘플 이력 데이터 (실제로는 시계열 데이터베이스에서 가져와야 함)
        history = [{
            'timestamp': time.time(),
            'max_risk': current_risk.get('max_risk', 0),
            'warning_count': current_risk.get('warning_count', 0),
            'status': current_risk.get('status', 'safe')
        }]

        return jsonify({
            'success': True,
            'history': history,
            'period': '1hour'
        })

    except Exception as e:
        error_msg = f"위험도 이력 조회 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({'success': False, 'message': error_msg}), 500

@api_bp.route('/camera-sources')
def get_camera_sources():
    """사용 가능한 카메라 소스 목록 반환"""
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
        # 🆕 고정된 CCTV 바운더리 좌표 (위도, 경도 순서)
        geo_corners = [
            [37.33878879, 126.73490515],  # 좌상단
            [37.33918109, 126.73423283],  # 우상단
            [37.33945957, 126.73488587],  # 우하단
            [37.33934605, 126.73508427]   # 좌하단
        ]

        return jsonify({
            'success': True,
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
    """비디오 소스 변경 엔드포인트"""
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
    """외부 카메라에서 전송된 프레임을 수신"""
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

        # 현재 활성화된 소스가 아니면 프레임 처리 스킵
        if not is_active:
            return jsonify({
                'success': True,
                'message': f'카메라 {camera_id}가 현재 활성화되지 않음',
                'is_active': False
            })

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

        # 현재 위험도 요약 정보 포함
        response_data = {
            'success': True,
            'message': f'카메라 {camera_id} 프레임 수신 및 처리 완료',
            'is_active': True,
            'timestamp': time.time()
        }

        # 위험도 정보 추가 (선택적)
        if video_processor._is_initialized:
            try:
                risk_summary = video_processor.predictor.get_risk_summary()
                response_data['current_risk'] = risk_summary
            except Exception as e:
                logger.warning(f"위험도 정보 추가 중 오류: {str(e)}")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"카메라 프레임 수신 오류: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/export-risk-data')
def export_risk_data():
    """
    위험도 데이터 내보내기 (CSV 형식)
    """
    try:
        if not video_processor._is_initialized:
            return jsonify({
                'success': False,
                'message': '시스템이 초기화되지 않았습니다'
            }), 400

        # 현재 위험도 정보 수집
        current_objects = video_processor.get_all_objects_info() if hasattr(video_processor, 'get_all_objects_info') else {}
        risk_summary = video_processor.predictor.get_risk_summary()

        # CSV 데이터 생성
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # 헤더 작성
        writer.writerow([
            'timestamp', 'object_id', 'lat', 'lon', 'speed_ms', 'speed_kph',
            'heading', 'risk_score', 'risk_level', 'is_collision_risk'
        ])

        # 데이터 작성
        timestamp = time.time()
        for obj_id, obj_info in current_objects.items():
            if obj_info and 'position' in obj_info and obj_info['position']:
                lat, lon = obj_info['position']
                speed_ms = obj_info.get('speed', 0)
                speed_kph = speed_ms * 3.6
                heading = obj_info.get('heading', 0)

                # 해당 객체의 위험도 찾기
                risk_score = 0
                is_collision_risk = obj_id in video_processor.collision_risk_ids

                if hasattr(video_processor, 'prediction_result') and video_processor.prediction_result:
                    collisions = video_processor.prediction_result.get('collisions', {})
                    for (id1, id2), score in collisions.items():
                        if obj_id == id1 or obj_id == id2:
                            risk_score = max(risk_score, score)

                # 위험도 레벨 결정
                if risk_score >= 85:
                    risk_level = 'critical'
                elif risk_score >= 70:
                    risk_level = 'high'
                elif risk_score >= 55:
                    risk_level = 'medium'
                elif risk_score >= 40:
                    risk_level = 'low'
                else:
                    risk_level = 'safe'

                writer.writerow([
                    timestamp, obj_id, lat, lon, speed_ms, speed_kph,
                    heading, risk_score, risk_level, is_collision_risk
                ])

        csv_content = output.getvalue()
        output.close()

        return jsonify({
            'success': True,
            'data': csv_content,
            'filename': f'risk_data_{int(timestamp)}.csv',
            'record_count': len(current_objects)
        })

    except Exception as e:
        error_msg = f"위험도 데이터 내보내기 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({'success': False, 'message': error_msg}), 500