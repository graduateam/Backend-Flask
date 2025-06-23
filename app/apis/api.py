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
import math
import random
import time
from datetime import datetime

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

# Mock 데이터 생성을 위한 전역 변수
request_counter = 0  # 7번째마다 충돌 경고 생성용 카운터
mock_vehicles_cache = {}  # 차량 정보 캐시 (일관성 유지)

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
        # 비디오 해상도 가져오기
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


# ===========================================
# 모바일 앱 연동을 위한 Mock API 구현
# ===========================================

def generate_mock_vehicles(center_lat, center_lng, count=5):
    """
    가짜 차량 데이터 생성
    
    Parameters:
    center_lat, center_lng: float - 중심 좌표 (사용자 위치)
    count: int - 생성할 차량 수
    
    Returns:
    list - 가짜 차량 데이터 목록
    """
    global mock_vehicles_cache
    current_time = datetime.now().isoformat()
    
    vehicles = []
    
    for i in range(count):
        vehicle_id = f"vehicle_{i+1}"
        
        # 기존 차량이 있으면 위치를 약간 업데이트, 없으면 새로 생성
        if vehicle_id in mock_vehicles_cache:
            # 기존 차량 위치에서 약간 이동 (실제 이동 시뮬레이션)
            prev_vehicle = mock_vehicles_cache[vehicle_id]
            
            # 이전 방향으로 약간 이동 (속도에 비례)
            speed_factor = prev_vehicle['speed'] / 111000  # m/s to degrees 근사치
            heading_rad = math.radians(prev_vehicle['heading'])
            
            lat_offset = speed_factor * math.sin(heading_rad) * 0.1  # 0.1초 간격 가정
            lng_offset = speed_factor * math.cos(heading_rad) * 0.1
            
            new_lat = prev_vehicle['latitude'] + lat_offset
            new_lng = prev_vehicle['longitude'] + lng_offset
            
            # 방향과 속도는 약간 변화
            new_heading = (prev_vehicle['heading'] + random.uniform(-10, 10)) % 360
            new_speed = max(5, min(25, prev_vehicle['speed'] + random.uniform(-2, 2)))
            
        else:
            # 새 차량 생성: 중심점 주변 500m 반경 내
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(50, 500) / 111000  # 미터를 도 단위로 근사 변환
            
            new_lat = center_lat + distance * math.cos(angle)
            new_lng = center_lng + distance * math.sin(angle)
            new_heading = random.uniform(0, 360)
            new_speed = random.uniform(8, 20)  # 8-20 m/s (약 30-70 km/h)
        
        vehicle = {
            "id": vehicle_id,
            "type": "vehicle",
            "latitude": new_lat,
            "longitude": new_lng,
            "heading": new_heading,
            "speed": new_speed,
            "speed_kph": new_speed * 3.6,
            "timestamp": current_time,
            "is_collision_risk": False,  # 기본값, 충돌 경고 생성 시 업데이트
            "ttc": None,
            "source": "camera_detection"
        }
        
        vehicles.append(vehicle)
        mock_vehicles_cache[vehicle_id] = vehicle
    
    return vehicles

def generate_mock_people(center_lat, center_lng, count=3):
    """
    가짜 보행자 데이터 생성
    
    Parameters:
    center_lat, center_lng: float - 중심 좌표
    count: int - 생성할 보행자 수
    
    Returns:
    list - 가짜 보행자 데이터 목록
    """
    current_time = datetime.now().isoformat()
    people = []
    
    for i in range(count):
        # 중심점 주변 200m 반경 내 (보행자는 차량보다 가까운 범위)
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(20, 200) / 111000  # 미터를 도 단위로 근사 변환
        
        lat = center_lat + distance * math.cos(angle)
        lng = center_lng + distance * math.sin(angle)
        heading = random.uniform(0, 360)
        speed = random.uniform(0.8, 2.0)  # 보행 속도 0.8-2.0 m/s
        
        person = {
            "id": f"person_{i+1}",
            "type": "person", 
            "latitude": lat,
            "longitude": lng,
            "heading": heading,
            "speed": speed,
            "speed_kph": speed * 3.6,
            "timestamp": current_time,
            "is_collision_risk": False,
            "ttc": None
        }
        
        people.append(person)
    
    return people

def generate_mock_collision_warning(vehicles):
    """
    가짜 충돌 경고 생성 (7번째 요청마다)
    
    Parameters:
    vehicles: list - 차량 목록
    
    Returns:
    dict - 충돌 경고 데이터 또는 None
    """
    if not vehicles:
        return None
    
    # 임의의 차량 선택
    target_vehicle = random.choice(vehicles)
    
    # 충돌 위험으로 마킹
    target_vehicle["is_collision_risk"] = True
    
    # 상대 방향 목록
    relative_directions = ["front", "front-left", "front-right", "left", "right"]
    
    # Mock 충돌 경고 데이터
    warning = {
        "objectId": target_vehicle["id"],
        "objectType": "vehicle",
        "direction": target_vehicle["heading"],
        "relativeDirection": random.choice(relative_directions),
        "speed": target_vehicle["speed"],
        "speed_kph": target_vehicle["speed_kph"],
        "distance": random.uniform(15, 50),  # 15-50m
        "ttc": random.uniform(1.5, 3.5),     # 1.5-3.5초
        "severity": random.choice(["medium", "high", "critical"]),
        "timestamp": datetime.now().isoformat()
    }
    
    return warning

def calculate_mock_motion(request_data):
    """
    가짜 모션 데이터 계산 (사용자의 속도/방향)
    
    Parameters:
    request_data: dict - 요청 데이터
    
    Returns:
    dict - 계산된 모션 정보
    """
    # TODO: 실제 구현 시 이 함수를 실제 로직으로 교체
    # 실제로는 이전 위치와 현재 위치를 비교하여 속도/방향 계산
    
    return {
        "speed": random.uniform(0, 16.67),  # 0-60 km/h in m/s
        "speed_kph": random.uniform(0, 60),
        "heading": random.uniform(0, 360)
    }

@api_bp.route('/location/update', methods=['POST'])
def location_update():
    """
    통합 위치 업데이트 API (Mock 구현)
    
    TODO: 실제 구현 시 다음 부분들을 실제 로직으로 교체:
    1. calculate_mock_motion() → 실제 속도/방향 계산 로직
    2. generate_mock_vehicles() → 실제 카메라 감지 차량 데이터
    3. generate_mock_people() → 실제 카메라 감지 보행자 데이터  
    4. generate_mock_collision_warning() → 실제 충돌 예측 로직
    """
    global request_counter
    
    try:
        # 요청 데이터 검증
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "요청 데이터가 없습니다"
            }), 400
        
        # 필수 필드 검증
        required_fields = ['device_id', 'timestamp', 'location', 'device_info']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "message": f"필수 필드 누락: {field}"
                }), 400
        
        # 위치 정보 추출
        location = data['location']
        user_lat = location['latitude']
        user_lng = location['longitude']
        
        # 요청 카운터 증가
        request_counter += 1
        
        # ===========================================
        # TODO: 실제 구현 시 아래 Mock 함수들을 교체
        # ===========================================
        
        # 1. 사용자 모션 계산 (Mock)
        calculated_motion = calculate_mock_motion(data)
        
        # 2. 주변 차량 데이터 생성 (Mock) 
        mock_vehicles = generate_mock_vehicles(user_lat, user_lng, count=5)
        
        # 3. 주변 보행자 데이터 생성 (Mock)
        mock_people = generate_mock_people(user_lat, user_lng, count=3)
        
        # 4. 충돌 경고 생성 (7번째 요청마다)
        collision_warning_data = None
        has_warning = False
        
        if request_counter % 7 == 0:  # 7번째마다 충돌 경고
            collision_warning_data = generate_mock_collision_warning(mock_vehicles)
            has_warning = collision_warning_data is not None
            
            logger.info(f"충돌 경고 생성됨 (요청 #{request_counter}): {collision_warning_data}")
        
        # ===========================================
        # 응답 데이터 구성
        # ===========================================
        
        response = {
            "success": True,
            "message": "위치 정보 업데이트 완료 (Mock 모드)",
            "server_timestamp": datetime.now().isoformat(),
            "assigned_id": f"mobile_user_{data['device_id']}",
            "calculated_motion": calculated_motion,
            "nearby_vehicles": {
                "vehicles": mock_vehicles,
                "total_count": len(mock_vehicles)
            },
            "nearby_people": {
                "people": mock_people,
                "total_count": len(mock_people)
            },
            "collision_warning": {
                "hasWarning": has_warning,
                "warning": collision_warning_data if has_warning else None
            }
        }
        
        # 디버그 로그
        logger.info(f"위치 업데이트 요청 처리 완료 (#{request_counter}): "
                   f"디바이스={data['device_id']}, 위치=({user_lat:.6f}, {user_lng:.6f}), "
                   f"차량={len(mock_vehicles)}대, 보행자={len(mock_people)}명, "
                   f"충돌경고={'있음' if has_warning else '없음'}")
        
        return jsonify(response)
        
    except Exception as e:
        error_msg = f"위치 업데이트 처리 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            "success": False,
            "message": error_msg
        }), 500


# ===========================================
# 개별 API들 (참고용 - 필요시 구현)
# ===========================================

@api_bp.route('/vehicles/nearby', methods=['GET'])
def get_nearby_vehicles():
    """
    주변 차량 조회 API (Mock 구현)
    
    TODO: 실제 구현 시 실제 차량 감지 로직으로 교체
    """
    try:
        # 쿼리 파라미터 추출
        lat = float(request.args.get('latitude', 37.5666102))
        lng = float(request.args.get('longitude', 126.9783881))
        radius = int(request.args.get('radius', 500))
        
        # Mock 차량 데이터 생성
        mock_vehicles = generate_mock_vehicles(lat, lng, count=5)
        
        return jsonify({
            "success": True,
            "data": {
                "vehicles": mock_vehicles,
                "timestamp": datetime.now().isoformat(),
                "total_count": len(mock_vehicles)
            }
        })
        
    except Exception as e:
        error_msg = f"주변 차량 조회 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            "success": False,
            "message": error_msg
        }), 500

@api_bp.route('/people/nearby', methods=['GET'])  
def get_nearby_people():
    """
    주변 보행자 조회 API (Mock 구현)
    
    TODO: 실제 구현 시 실제 보행자 감지 로직으로 교체
    """
    try:
        # 쿼리 파라미터 추출
        lat = float(request.args.get('latitude', 37.5666102))
        lng = float(request.args.get('longitude', 126.9783881))
        radius = int(request.args.get('radius', 500))
        
        # Mock 보행자 데이터 생성
        mock_people = generate_mock_people(lat, lng, count=3)
        
        return jsonify({
            "success": True,
            "data": {
                "people": mock_people,
                "timestamp": datetime.now().isoformat(),
                "total_count": len(mock_people)
            }
        })
        
    except Exception as e:
        error_msg = f"주변 보행자 조회 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            "success": False,
            "message": error_msg
        }), 500

@api_bp.route('/collision/warning', methods=['POST'])
def get_collision_warning():
    """
    충돌 경고 조회 API (Mock 구현)
    
    TODO: 실제 구현 시 실제 충돌 예측 로직으로 교체
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "요청 데이터가 없습니다"
            }), 400
        
        # Mock 충돌 경고 생성 (30% 확률)
        has_warning = random.random() < 0.3
        warning_data = None
        
        if has_warning:
            # 임시 차량 데이터로 경고 생성
            mock_vehicles = generate_mock_vehicles(
                data.get('latitude', 37.5666102),
                data.get('longitude', 126.9783881),
                count=1
            )
            warning_data = generate_mock_collision_warning(mock_vehicles)
        
        return jsonify({
            "success": True,
            "data": {
                "warning": warning_data,
                "hasWarning": has_warning
            }
        })
        
    except Exception as e:
        error_msg = f"충돌 경고 조회 오류: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            "success": False,
            "message": error_msg
        }), 500


# ===========================================
# 실제 구현 시 교체할 함수들의 인터페이스 예시
# ===========================================

"""
실제 구현 시 다음과 같은 함수들로 교체하면 됩니다:

def calculate_real_motion(device_id, current_location, timestamp):
    '''
    실제 사용자 모션 계산
    - 이전 위치 데이터와 비교하여 실제 속도/방향 계산
    - 데이터베이스나 메모리에서 위치 이력 조회
    '''
    pass

def get_real_nearby_vehicles(lat, lng, radius):
    '''
    실제 카메라 감지 차량 데이터 조회
    - YOLO 객체 감지 결과에서 차량 정보 추출
    - 좌표 변환 적용하여 GPS 좌표로 변환
    '''
    pass

def get_real_nearby_people(lat, lng, radius):
    '''
    실제 카메라 감지 보행자 데이터 조회
    - YOLO 객체 감지 결과에서 보행자 정보 추출
    '''
    pass

def predict_real_collision(user_location, nearby_objects):
    '''
    실제 충돌 예측 로직
    - CollisionPredictor 클래스 활용
    - 벡터 기반 충돌 예측 수행
    '''
    pass
"""