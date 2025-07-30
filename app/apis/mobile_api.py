"""
모바일 앱 전용 API 엔드포인트
Device ID 기반 익명 시스템으로 위치 추적 및 충돌 경고 제공
"""
from flask import Blueprint, jsonify, request
from app.services.device_manager import device_manager
from app.services.video_processor import video_processor
from app.utils.logger import setup_logger
import time
import config
from datetime import datetime

# 로거 설정
logger = setup_logger(__name__)

# 모바일 API 블루프린트 생성
mobile_api_bp = Blueprint('mobile_api', __name__, url_prefix='/api')

def register_mobile_api_blueprint(app):
    """
    모바일 API 블루프린트 등록 함수
    
    Parameters:
    app: Flask - Flask 애플리케이션 인스턴스
    """
    app.register_blueprint(mobile_api_bp)
    logger.info('모바일 API 블루프린트 등록 완료')

# CCTV 커버리지 샘플 데이터 (실제로는 데이터베이스나 설정에서 로드)
SAMPLE_CCTV_DATA = [
    {
        "cctv_id": "cctv_001",
        "name": "일산호수공원_동문",
        "location": {
            "latitude": 37.67675942,
            "longitude": 126.74583666
        },
        "coverage_area": {
            "type": "polygon",
            "coordinates": [[
                [126.7455, 37.6765],
                [126.7465, 37.6765],
                [126.7465, 37.6775],
                [126.7455, 37.6775],
                [126.7455, 37.6765]
            ]]
        }
    },
    {
        "cctv_id": "cctv_002", 
        "name": "일산호수공원_서문",
        "location": {
            "latitude": 37.67696082,
            "longitude": 126.74597894
        },
        "coverage_area": {
            "type": "polygon",
            "coordinates": [[
                [126.7450, 37.6760],
                [126.7470, 37.6760],
                [126.7470, 37.6780],
                [126.7450, 37.6780],
                [126.7450, 37.6760]
            ]]
        }
    }
]

@mobile_api_bp.route('/location', methods=['POST'])
def update_location():
    """
    모바일 앱에서 위치 정보 전송 및 충돌 경고 통합 응답
    
    Request Body:
    {
        "device_id": "device_1643095800_abc123def456",
        "timestamp": "2025-01-25T10:30:00.000Z",
        "location": {
            "latitude": 37.5666102,
            "longitude": 126.9783881
        }
    }
    
    Response:
    성공 시 - 충돌 경고 정보 포함된 통합 응답
    실패 시 - 오류 정보
    """
    try:
        # 요청 데이터 파싱
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'LOCATION_DATA_MISSING',
                    'message': '요청 데이터가 없습니다'
                },
                'timestamp': datetime.now().isoformat() + 'Z'
            }), 400

        # 필수 필드 검증
        device_id = data.get('device_id')
        location_data = data.get('location', {})
        
        if not device_id:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_DEVICE_ID',
                    'message': 'Device ID가 필요합니다'
                },
                'timestamp': datetime.now().isoformat() + 'Z'
            }), 400

        latitude = location_data.get('latitude')
        longitude = location_data.get('longitude')
        
        if latitude is None or longitude is None:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'LOCATION_DATA_MISSING',
                    'message': '위치 정보가 누락되었습니다'
                },
                'timestamp': datetime.now().isoformat() + 'Z'
            }), 400

        # 타임스탬프 파싱 (선택적)
        timestamp = data.get('timestamp')
        if timestamp:
            try:
                # ISO 8601 형식 파싱을 단순화
                import datetime
                dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.timestamp()
            except:
                timestamp = time.time()
        else:
            timestamp = time.time()

        # 디바이스 매니저를 통한 위치 업데이트
        success, motion_data, message = device_manager.update_location(
            device_id=device_id,
            latitude=latitude,
            longitude=longitude,
            timestamp=timestamp
        )

        if not success:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'LOCATION_UPDATE_FAILED',
                    'message': message
                },
                'timestamp': datetime.now().isoformat() + 'Z'
            }), 400

        # 충돌 경고 계산
        collision_warning = _calculate_collision_warning(device_id, latitude, longitude, motion_data)

        # 성공 응답
        server_timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        response_data = {
            'success': True,
            'message': '위치 정보 업데이트 완료',
            'server_timestamp': server_timestamp,
            'assigned_id': device_id,
            'collision_warning': collision_warning
        }

        # 디버그 정보 추가 (개발 환경에서만)
        if config.DEBUG:
            response_data['debug_info'] = {
                'calculated_motion': {
                    'speed': motion_data.speed,
                    'speed_kph': motion_data.speed_kph,
                    'heading': motion_data.heading
                } if motion_data else None,
                'active_sessions': len(device_manager.get_active_sessions())
            }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"위치 업데이트 처리 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'SERVER_ERROR',
                'message': '서버 내부 오류가 발생했습니다'
            },
            'timestamp': datetime.now().isoformat() + 'Z'
        }), 500

@mobile_api_bp.route('/cctv', methods=['GET'])
def get_cctv_coverage():
    """
    CCTV 커버리지 영역 정보 조회
    모바일 앱 접속 시 최초 1회 호출하여 전체 CCTV 정보를 받음
    
    Response:
    CCTV 위치 및 관측 영역 정보 배열
    """
    try:
        server_timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        response_data = {
            'success': True,
            'server_timestamp': server_timestamp,
            'total_count': len(SAMPLE_CCTV_DATA),
            'cctv_coverage': SAMPLE_CCTV_DATA
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"CCTV 정보 조회 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'CCTV 정보를 가져오는데 실패했습니다'
            },
            'timestamp': datetime.now().isoformat() + 'Z'
        }), 500

@mobile_api_bp.route('/vehicles/nearby', methods=['GET'])
def get_nearby_vehicles():
    """
    주변 차량 정보 조회 (참고용 API)
    
    Query Parameters:
    - lat: 위도
    - lng: 경도
    - radius: 반경 (미터, 기본값: 500)
    """
    try:
        # 쿼리 파라미터 파싱
        latitude = request.args.get('lat', type=float)
        longitude = request.args.get('lng', type=float)
        radius = request.args.get('radius', default=500, type=int)

        if latitude is None or longitude is None:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'LOCATION_DATA_MISSING',
                    'message': '위도와 경도가 필요합니다'
                },
                'timestamp': datetime.now().isoformat() + 'Z'
            }), 400

        # 카메라에서 감지된 차량 정보 가져오기 (기존 시스템 활용)
        vehicles = []
        if video_processor._is_initialized and video_processor.detected_objects:
            for obj_info in video_processor.detected_objects:
                if obj_info and obj_info.get('class_name') in ['car', 'truck', 'bus', 'motorcycle']:
                    coords = obj_info.get('coords')
                    if coords:
                        vehicles.append({
                            'id': obj_info.get('id'),
                            'type': 'vehicle',
                            'latitude': coords[0],
                            'longitude': coords[1],
                            'heading': 0,  # 방향 정보는 별도 계산 필요
                            'speed': 0,    # 속도 정보는 별도 계산 필요
                            'speed_kph': 0,
                            'timestamp': datetime.now().isoformat() + 'Z',
                            'is_collision_risk': obj_info.get('id') in video_processor.collision_risk_ids,
                            'ttc': None,
                            'source': 'camera_detection'
                        })

        response_data = {
            'success': True,
            'data': {
                'vehicles': vehicles,
                'timestamp': datetime.now().isoformat() + 'Z',
                'total_count': len(vehicles)
            }
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"주변 차량 조회 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'SERVER_ERROR',
                'message': '주변 차량 정보를 가져오는데 실패했습니다'
            },
            'timestamp': datetime.now().isoformat() + 'Z'
        }), 500

@mobile_api_bp.route('/people/nearby', methods=['GET'])
def get_nearby_people():
    """
    주변 보행자 정보 조회 (참고용 API)
    
    Query Parameters:
    - lat: 위도
    - lng: 경도
    - radius: 반경 (미터, 기본값: 500)
    """
    try:
        # 쿼리 파라미터 파싱
        latitude = request.args.get('lat', type=float)
        longitude = request.args.get('lng', type=float)
        radius = request.args.get('radius', default=500, type=int)

        if latitude is None or longitude is None:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'LOCATION_DATA_MISSING',
                    'message': '위도와 경도가 필요합니다'
                },
                'timestamp': datetime.now().isoformat() + 'Z'
            }), 400

        # 카메라에서 감지된 보행자 정보 가져오기
        people = []
        if video_processor._is_initialized and video_processor.detected_objects:
            for obj_info in video_processor.detected_objects:
                if obj_info and obj_info.get('class_name') == 'person':
                    coords = obj_info.get('coords')
                    if coords:
                        people.append({
                            'id': obj_info.get('id'),
                            'type': 'person',
                            'latitude': coords[0],
                            'longitude': coords[1],
                            'heading': 0,  # 방향 정보는 별도 계산 필요
                            'speed': 0,    # 속도 정보는 별도 계산 필요
                            'speed_kph': 0,
                            'timestamp': datetime.now().isoformat() + 'Z',
                            'is_collision_risk': obj_info.get('id') in video_processor.collision_risk_ids,
                            'ttc': None
                        })

        response_data = {
            'success': True,
            'data': {
                'people': people,
                'timestamp': datetime.now().isoformat() + 'Z',
                'total_count': len(people)
            }
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"주변 보행자 조회 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'SERVER_ERROR',
                'message': '주변 보행자 정보를 가져오는데 실패했습니다'
            },
            'timestamp': datetime.now().isoformat() + 'Z'
        }), 500

@mobile_api_bp.route('/collision/warning', methods=['POST'])
def get_collision_warning():
    """
    충돌 경고 정보 조회 (참고용 API)
    일반적으로는 /api/location에서 통합 응답으로 제공
    
    Request Body:
    {
        "device_id": "device_1643095800_abc123def456",
        "latitude": 37.5666102,
        "longitude": 126.9783881
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'REQUEST_DATA_MISSING',
                    'message': '요청 데이터가 없습니다'
                },
                'timestamp': datetime.now().isoformat() + 'Z'
            }), 400

        device_id = data.get('device_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if not all([device_id, latitude is not None, longitude is not None]):
            return jsonify({
                'success': False,
                'error': {
                    'code': 'REQUIRED_FIELDS_MISSING',
                    'message': '필수 필드가 누락되었습니다'
                },
                'timestamp': datetime.now().isoformat() + 'Z'
            }), 400

        # 세션에서 모션 데이터 가져오기
        session = device_manager.sessions.get(device_id)
        motion_data = session.current_motion if session else None

        # 충돌 경고 계산
        collision_warning = _calculate_collision_warning(device_id, latitude, longitude, motion_data)

        response_data = {
            'success': True,
            'data': collision_warning
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"충돌 경고 조회 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'SERVER_ERROR',
                'message': '충돌 경고 정보를 가져오는데 실패했습니다'
            },
            'timestamp': datetime.now().isoformat() + 'Z'
        }), 500

def _calculate_collision_warning(device_id, latitude, longitude, motion_data):
    """
    충돌 경고 계산 (내부 함수)
    
    Parameters:
    device_id: str - 디바이스 ID
    latitude: float - 위도
    longitude: float - 경도
    motion_data: MotionData - 모션 정보
    
    Returns:
    dict - 충돌 경고 정보
    """
    try:
        # 충돌 예측 시스템이 초기화되지 않은 경우
        if not video_processor._is_initialized or not hasattr(video_processor, 'predictor'):
            return {
                'hasWarning': False,
                'message': '충돌 예측 시스템이 초기화되지 않았습니다'
            }

        # 모바일 통합기를 사용하여 정교한 충돌 경고 계산
        if motion_data:
            from app.services.mobile_integration import mobile_integrator
            
            # 모바일 사용자 통합 및 충돌 경고 계산
            warning_info = mobile_integrator.get_collision_warning_for_mobile_user(
                device_id, video_processor
            )
            
            if warning_info:
                return {
                    'hasWarning': True,
                    'warning': warning_info
                }

        # 충돌 위험 없음
        return {
            'hasWarning': False
        }

    except Exception as e:
        logger.error(f"충돌 경고 계산 오류: {str(e)}")
        return {
            'hasWarning': False,
            'error': '충돌 경고 계산 중 오류 발생'
        }

# 상태 확인용 엔드포인트 (디버그용)
@mobile_api_bp.route('/status', methods=['GET'])
def get_mobile_api_status():
    """모바일 API 상태 확인 (디버그용)"""
    try:
        stats = device_manager.get_stats()
        active_sessions = device_manager.get_active_sessions()
        
        response_data = {
            'success': True,
            'timestamp': datetime.now().isoformat() + 'Z',
            'mobile_api_status': 'active',
            'device_manager_stats': stats,
            'active_sessions_count': len(active_sessions),
            'video_processor_status': {
                'initialized': video_processor._is_initialized,
                'processing': video_processor.is_processing,
                'current_source': video_processor.current_source
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"모바일 API 상태 확인 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'SERVER_ERROR',
                'message': '상태 확인 중 오류가 발생했습니다'
            },
            'timestamp': datetime.now().isoformat() + 'Z'
        }), 500