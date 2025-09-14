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

# CCTV 커버리지 데이터는 실제 비디오 경계에서 동적으로 생성됨
def _get_real_cctv_coverage_data():
    """
    웹에서 사용하는 /api/video-bounds와 동일한 실제 비디오 경계 데이터를 
    CCTV 커버리지 형식으로 변환하여 반환
    """
    try:
        from app.utils.coord_utils import CoordinateTransformer
        import cv2
        
        # 좌표 변환기 초기화 (api.py와 동일)
        transformer = CoordinateTransformer(
            image_points=config.IMAGE_POINTS,
            world_points=config.WORLD_POINTS
        )
        
        # 비디오 해상도 가져오기
        width, height = 640, 480
        if video_processor.cap is not None:
            width = int(video_processor.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(video_processor.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 비디오 프레임의 4개 모서리 좌표 (시계방향)
        corners = [
            (0, 0),           # 좌상단
            (width, 0),       # 우상단  
            (width, height),  # 우하단
            (0, height)       # 좌하단
        ]

        # 각 모서리를 위도, 경도로 변환
        geo_corners = []
        center_lat, center_lon = 0, 0
        valid_corners = 0
        
        for x, y in corners:
            try:
                lat, lon = transformer.image_to_world((x, y))
                geo_corners.append([lon, lat])  # GeoJSON 형식: [경도, 위도]
                center_lat += lat
                center_lon += lon
                valid_corners += 1
            except Exception as e:
                logger.error(f"좌표 변환 오류: {str(e)}")
                # 실패시 기본값 사용
                geo_corners.append([126.9783881, 37.5666102])
                center_lat += 37.5666102
                center_lon += 126.9783881
                valid_corners += 1

        # 폴리곤을 닫기 위해 첫 번째 점을 마지막에 추가
        if geo_corners:
            geo_corners.append(geo_corners[0])
        
        # 중심점 계산
        if valid_corners > 0:
            center_lat /= valid_corners
            center_lon /= valid_corners
        else:
            center_lat, center_lon = 37.5666102, 126.9783881

        # CCTV 데이터 형식으로 변환
        cctv_data = [{
            "cctv_id": "cctv_001",
            "name": "실시간_카메라_커버리지",
            "location": {
                "latitude": center_lat,
                "longitude": center_lon
            },
            "coverage_area": {
                "type": "polygon",
                "coordinates": [geo_corners]
            }
        }]
        
        logger.info(f"실시간 CCTV 커버리지 생성 완료: {len(geo_corners)}개 좌표점")
        return cctv_data
        
    except Exception as e:
        logger.error(f"실시간 CCTV 커버리지 생성 오류: {str(e)}")
        # 오류 시 기본 샘플 데이터 반환
        return [{
            "cctv_id": "cctv_001",
            "name": "기본_커버리지",
            "location": {
                "latitude": 37.5666102,
                "longitude": 126.9783881
            },
            "coverage_area": {
                "type": "polygon", 
                "coordinates": [[
                    [126.9783881, 37.5666102],
                    [126.9785881, 37.5666102],
                    [126.9785881, 37.5668102],
                    [126.9783881, 37.5668102],
                    [126.9783881, 37.5666102]
                ]]
            }
        }]

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
                from datetime import datetime as dt_class
                dt = dt_class.fromisoformat(timestamp.replace('Z', '+00:00'))
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

        # 🆕 감지된 모든 객체 정보 수집 (사용자 중심 위험도 계산)
        all_detected_objects = _get_all_detected_objects(mobile_user_id=device_id)

        # 성공 응답
        server_timestamp = datetime.now().isoformat() + 'Z'
        response_data = {
            'success': True,
            'message': '위치 정보 업데이트 완료',
            'server_timestamp': server_timestamp,
            'assigned_id': device_id,
            'collision_warning': collision_warning,
            'all_detected_objects': all_detected_objects  # 🆕 감지된 모든 객체 정보 추가
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
    CCTV 커버리지 영역 정보 조회 (실제 비디오 경계 데이터 사용)
    모바일 앱 접속 시 최초 1회 호출하여 전체 CCTV 정보를 받음
    
    Response:
    CCTV 위치 및 관측 영역 정보 배열 (웹의 /api/video-bounds와 동일한 실제 데이터)
    """
    try:
        server_timestamp = datetime.now().isoformat() + 'Z'
        
        # 실제 비디오 경계 데이터를 CCTV 형식으로 변환
        real_cctv_data = _get_real_cctv_coverage_data()
        
        response_data = {
            'success': True,
            'server_timestamp': server_timestamp,
            'total_count': len(real_cctv_data),
            'cctv_coverage': real_cctv_data
        }

        logger.info(f"실시간 CCTV 커버리지 API 응답: {len(real_cctv_data)}개 CCTV")
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
        # 충돌 예측 시스템 자동 초기화 (앱 메인 동작을 위해 필수)
        logger.info(f"[AUTO-INIT] 초기화 상태 확인: _is_initialized={getattr(video_processor, '_is_initialized', False)}, is_processing={getattr(video_processor, 'is_processing', False)}")
        
        # 모델이 초기화되지 않은 경우 초기화
        if not getattr(video_processor, '_is_initialized', False):
            logger.info("[AUTO-INIT] 모델 초기화 시작...")
            try:
                video_processor.initialize_models()
                logger.info("[AUTO-INIT] 모델 초기화 완료")
            except Exception as e:
                logger.error(f"[AUTO-INIT] 모델 초기화 실패: {str(e)}")
        
        # 비디오 처리가 시작되지 않은 경우 시작
        if not getattr(video_processor, 'is_processing', False):
            logger.info("[AUTO-INIT] 비디오 처리 시작...")
            try:
                result = video_processor.start_processing()
                if result.get('success'):
                    logger.info("[AUTO-INIT] 비디오 처리 자동 시작 완료")
                else:
                    logger.warning(f"[AUTO-INIT] 비디오 처리 시작 실패: {result.get('message')}")
            except Exception as e:
                logger.error(f"[AUTO-INIT] 비디오 처리 시작 실패: {str(e)}")
        
        # 최종 확인: 여전히 초기화되지 않은 경우에만 오류 반환
        if not getattr(video_processor, '_is_initialized', False) or not hasattr(video_processor, 'predictor'):
            logger.error("[AUTO-INIT] 자동 초기화 실패 - 충돌 예측 시스템 사용 불가")
            return {
                'hasWarning': False,
                'message': '충돌 예측 시스템 자동 초기화 실패'
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

# 라즈베리파이 프레임 수신 엔드포인트
@mobile_api_bp.route('/camera/frame', methods=['POST'])
def receive_camera_frame():
    """라즈베리파이에서 전송한 프레임 수신"""
    try:
        # 멀티파트 폼 데이터에서 이미지 파일 받기
        if 'frame' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No frame data'
            }), 400
        
        file = request.files['frame']
        camera_id = request.form.get('camera_id', 'camera_0')
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'Empty frame data'
            }), 400
        
        # 이미지 파일을 numpy 배열로 변환
        import numpy as np
        import cv2
        
        # 파일을 바이트로 읽기
        file_bytes = file.read()
        # numpy 배열로 변환
        nparr = np.frombuffer(file_bytes, np.uint8)
        # OpenCV 이미지로 디코딩
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({
                'success': False,
                'error': 'Invalid frame data'
            }), 400
        
        # video_processor에 프레임 설정
        success = video_processor.set_camera_frame(camera_id, frame)
        
        if success:
            logger.info(f"[FRAME-RX] 라즈베리파이에서 프레임 수신: {camera_id}, 크기: {frame.shape}")
            return jsonify({
                'success': True,
                'message': 'Frame received successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to set camera frame'
            }), 500
            
    except Exception as e:
        logger.error(f"프레임 수신 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Frame processing failed'
        }), 500

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
            'current_source': video_processor.current_source,  # 라즈베리파이 호환성을 위해 추가
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

def _get_all_detected_objects(mobile_user_id=None):
    """
    라즈베리파이 카메라로 감지된 모든 객체 정보를 프론트엔드 형식으로 변환
    사용자 중심 충돌 예측: 모바일 사용자와 직접 관련된 충돌 위험만 반영
    
    Parameters:
    mobile_user_id: str - 모바일 사용자 ID (위험도 계산 기준)
    
    Returns:
    list - 프론트엔드 DetectedObject 형식의 객체 목록
    """
    try:
        # video_processor 초기화 확인
        if not getattr(video_processor, '_is_initialized', False) or not hasattr(video_processor, 'detected_objects'):
            logger.info("[DETECTED_OBJECTS] 비디오 프로세서가 초기화되지 않았거나 감지된 객체가 없음")
            return []
        
        # 감지된 객체가 없는 경우
        if not video_processor.detected_objects:
            logger.info("[DETECTED_OBJECTS] 현재 감지된 객체 없음")
            return []
        
        # 기존 예측 결과 활용
        prediction_result = video_processor.prediction_result
        risk_summary = video_processor.risk_summary
        
        # 백엔드 detected_objects를 프론트엔드 형식으로 변환
        frontend_objects = []
        current_time = datetime.now().isoformat() + 'Z'
        
        for idx, obj in enumerate(video_processor.detected_objects):
            if not obj:
                continue
                
            # 객체 기본 정보
            obj_id = obj.get('id', idx)
            backend_class_name = obj.get('class_name', 'unknown')
            object_type, subtype = _map_object_type(backend_class_name)
            
            # 사용자 중심 충돌 예측: 모바일 사용자와 직접 관련된 위험도만 반영
            risk_level, collision_probability, ttc = _get_risk_from_prediction(obj_id, prediction_result, risk_summary, mobile_user_id)
            
            # 상대 방향 계산 (기존 predictor 객체 정보 활용)
            relative_direction = _calculate_relative_direction_from_prediction(obj_id, prediction_result)
            
            # 거리 계산 (GPS 좌표 기반)
            distance_m = _calculate_distance_from_coords(obj.get('coords'))
            
            # 속도 정보 (기존 추적 시스템에서 가져오기)
            speed_kph, direction_degrees, is_stationary, is_approaching = _get_motion_from_prediction(obj_id, prediction_result)
            
            # 프론트엔드 DetectedObject 형식으로 변환
            frontend_object = {
                'id': f"obj_{backend_class_name}_{obj_id:03d}",
                'type': object_type,
                'subtype': subtype,
                'position': {
                    'relativeDirection': relative_direction,
                    'distance_m': distance_m,
                    'coordinates': {
                        'latitude': obj.get('coords', (0, 0))[0] if obj.get('coords') else 37.5666102,
                        'longitude': obj.get('coords', (0, 0))[1] if obj.get('coords') else 126.9783881
                    }
                },
                'motion': {
                    'speed_kph': speed_kph,
                    'direction_degrees': direction_degrees,
                    'is_stationary': is_stationary,
                    'is_approaching': is_approaching
                },
                'risk_assessment': {
                    'risk_level': risk_level,
                    'collision_probability': collision_probability,
                    'ttc': ttc if ttc and ttc > 0 else None
                },
                'metadata': {
                    'detection_confidence': obj.get('confidence', 0.85),  # YOLO confidence 사용
                    'first_seen': current_time,  # 실제로는 추적 시작 시간
                    'last_updated': current_time,
                    'camera_id': 'raspberry_pi_cam',
                    'tracking_id': f"track_{backend_class_name}_{obj_id:03d}"
                }
            }
            
            frontend_objects.append(frontend_object)
        
        logger.info(f"[DETECTED_OBJECTS] {len(frontend_objects)}개 객체를 프론트엔드 형식으로 변환 완료")
        return frontend_objects
        
    except Exception as e:
        logger.error(f"감지된 객체 정보 수집 오류: {str(e)}")
        return []

def _map_object_type(backend_class_name):
    """백엔드 클래스명을 프론트엔드 타입으로 매핑 (차량 전용)"""
    mapping = {
        'car': ('vehicle', 'car'),
        # 추후 객체탐지 모델 업그레이드 시 추가 가능:
        # 'truck': ('vehicle', 'truck'), 
        # 'bus': ('vehicle', 'bus'),
        # 'motorcycle': ('vehicle', 'motorcycle'),
        # 'person': ('person', 'adult'),
        # 'bicycle': ('bicycle', 'bicycle'),
    }
    # 차량 전용 모델이므로 기본값도 vehicle로 설정
    return mapping.get(backend_class_name, ('vehicle', 'car'))

def _get_risk_from_prediction(obj_id, prediction_result, risk_summary, mobile_user_id=None):
    """
    사용자 중심 충돌 예측: 모바일 사용자와 직접 충돌 위험이 있는 차량만 위험도 반영
    """
    try:
        # 🎯 모바일 사용자가 있는 경우, 해당 사용자와의 충돌만 확인
        if mobile_user_id and hasattr(video_processor, 'predictor'):
            # 모바일 사용자 전용 충돌 예측 결과 확인
            mobile_collisions = video_processor.predictor.predict_mobile_user_collisions(mobile_user_id)
            
            # 현재 객체가 모바일 사용자와 충돌 위험이 있는지 확인
            for collision_pair, risk_score in mobile_collisions.items():
                user_id, other_id = collision_pair
                # 현재 객체가 충돌 쌍에 포함되어 있는지 확인
                if (user_id == mobile_user_id and other_id == obj_id) or (user_id == obj_id and other_id == mobile_user_id):
                    # 위험도 점수에 따른 레벨 결정
                    if risk_score >= 85:
                        return 'critical', min(risk_score / 100.0, 1.0), 1.0
                    elif risk_score >= 70:
                        return 'high', min(risk_score / 100.0, 1.0), 2.0
                    elif risk_score >= 55:
                        return 'medium', min(risk_score / 100.0, 1.0), 4.0
                    else:
                        return 'low', min(risk_score / 100.0, 1.0), 8.0
        
        # 모바일 사용자와 직접적인 충돌 위험이 없는 경우 모든 차량은 안전 상태로 표시
        return 'low', 0.02, None
        
    except Exception as e:
        logger.warning(f"위험도 계산 오류 (obj_id={obj_id}): {str(e)}")
        return 'low', 0.02, None

def _calculate_relative_direction_from_prediction(obj_id, prediction_result):
    """기존 예측 시스템의 방향 정보를 활용하여 상대 방향 계산"""
    try:
        # prediction_result에서 방향 정보 추출
        if prediction_result and hasattr(video_processor, 'predictor'):
            predictor = video_processor.predictor
            if hasattr(predictor, 'objects') and obj_id in predictor.objects:
                obj_data = predictor.objects[obj_id]
                # 객체의 방향과 사용자(모바일) 방향을 비교하여 상대 방향 계산
                # 실제 구현에서는 bearing 계산 등을 활용
                return 'front'  # 임시값
        
        return 'front'  # 기본값
        
    except Exception as e:
        logger.error(f"상대 방향 계산 오류: {str(e)}")
        return 'front'

def _calculate_distance_from_coords(coords):
    """GPS 좌표를 기반으로 실제 거리 계산"""
    try:
        if not coords or len(coords) < 2:
            return 25.0  # 기본값
        
        lat, lon = coords
        # 사용자 위치와의 거리 계산 (간단한 구현)
        # 실제로는 device_manager에서 사용자 위치를 가져와서 계산해야 함
        user_lat, user_lon = 37.5666102, 126.9783881  # 임시 사용자 위치
        
        # 간단한 거리 계산 (Haversine 공식 등 사용)
        import math
        R = 6371000  # 지구 반지름 (미터)
        
        lat1, lon1 = math.radians(user_lat), math.radians(user_lon)
        lat2, lon2 = math.radians(lat), math.radians(lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        distance = R * c
        return float(distance)
        
    except Exception as e:
        logger.error(f"거리 계산 오류: {str(e)}")
        return 25.0

def _get_motion_from_prediction(obj_id, prediction_result):
    """기존 예측 시스템에서 움직임 정보 추출"""
    try:
        # prediction_result에서 속도/방향 정보 추출
        if prediction_result and hasattr(video_processor, 'predictor'):
            predictor = video_processor.predictor
            if hasattr(predictor, 'objects') and obj_id in predictor.objects:
                obj_data = predictor.objects[obj_id]
                # 실제 구현에서는 속도, 방향, 정지 여부 등을 계산
                return 30.0, 90, False, False  # 임시값
        
        return 0.0, 0, True, False  # 기본값 (정지 상태)
        
    except Exception as e:
        logger.error(f"움직임 정보 추출 오류: {str(e)}")
        return 0.0, 0, True, False
