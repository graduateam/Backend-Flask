"""
모바일 디바이스 세션 관리 시스템
Device ID 기반 익명 사용자 추적 및 위치 이력 관리
"""
import time
import math
import re
from collections import deque, defaultdict
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass
from app.utils.logger import setup_logger
from app.utils.coord_utils import calculate_bearing, calculate_distance

# 로거 설정
logger = setup_logger(__name__)

@dataclass
class LocationPoint:
    """위치 정보 데이터 클래스"""
    latitude: float
    longitude: float
    timestamp: float
    accuracy: Optional[float] = None

@dataclass
class MotionData:
    """모션 계산 결과 데이터 클래스"""
    speed: float  # m/s
    speed_kph: float  # km/h
    heading: float  # 0-360도
    acceleration: Optional[float] = None  # m/s²

class MobileDeviceSession:
    """개별 모바일 디바이스 세션 관리"""
    
    def __init__(self, device_id: str, history_size: int = 10):
        self.device_id = device_id
        self.created_at = time.time()
        self.last_update = time.time()
        self.location_history = deque(maxlen=history_size)
        self.current_motion = None
        self.session_active = True
        
    def add_location(self, location: LocationPoint) -> MotionData:
        """
        새로운 위치 정보 추가 및 모션 데이터 계산
        
        Parameters:
        location: LocationPoint - 새로운 위치 정보
        
        Returns:
        MotionData - 계산된 모션 정보
        """
        self.location_history.append(location)
        self.last_update = time.time()
        
        # 모션 데이터 계산
        self.current_motion = self._calculate_motion()
        return self.current_motion
    
    def _calculate_motion(self) -> MotionData:
        """위치 이력을 기반으로 속도와 방향 계산"""
        if len(self.location_history) < 2:
            return MotionData(speed=0.0, speed_kph=0.0, heading=0.0)
        
        # 최근 두 점을 사용하여 즉시 속도 계산
        current = self.location_history[-1]
        previous = self.location_history[-2]
        
        # 거리 계산 (미터)
        distance = calculate_distance(
            previous.latitude, previous.longitude,
            current.latitude, current.longitude
        )
        
        # 시간 차이 (초)
        time_diff = current.timestamp - previous.timestamp
        
        # 속도 계산 (m/s)
        speed = distance / time_diff if time_diff > 0 else 0.0
        speed_kph = speed * 3.6
        
        # 방향 계산 (0-360도)
        heading = calculate_bearing(
            previous.latitude, previous.longitude,
            current.latitude, current.longitude
        )
        
        # 가속도 계산 (옵션)
        acceleration = None
        if len(self.location_history) >= 3 and self.current_motion:
            prev_speed = self.current_motion.speed
            acceleration = (speed - prev_speed) / time_diff if time_diff > 0 else 0.0
        
        return MotionData(
            speed=speed,
            speed_kph=speed_kph,
            heading=heading,
            acceleration=acceleration
        )
    
    def get_current_position(self) -> Optional[LocationPoint]:
        """현재 위치 반환"""
        return self.location_history[-1] if self.location_history else None
    
    def is_active(self, timeout_seconds: int = 30) -> bool:
        """세션 활성 상태 확인 (30초 이내 업데이트 여부)"""
        return (time.time() - self.last_update) < timeout_seconds
    
    def get_session_info(self) -> Dict[str, Any]:
        """세션 정보 반환"""
        current_pos = self.get_current_position()
        return {
            'device_id': self.device_id,
            'created_at': self.created_at,
            'last_update': self.last_update,
            'location_count': len(self.location_history),
            'current_position': {
                'latitude': current_pos.latitude,
                'longitude': current_pos.longitude,
                'timestamp': current_pos.timestamp
            } if current_pos else None,
            'current_motion': {
                'speed': self.current_motion.speed,
                'speed_kph': self.current_motion.speed_kph,
                'heading': self.current_motion.heading,
                'acceleration': self.current_motion.acceleration
            } if self.current_motion else None,
            'is_active': self.is_active()
        }

class DeviceManager:
    """모바일 디바이스 세션 통합 관리자"""
    
    def __init__(self, session_timeout: int = 300, cleanup_interval: int = 60):
        """
        DeviceManager 초기화
        
        Parameters:
        session_timeout: int - 세션 타임아웃 (초, 기본 5분)
        cleanup_interval: int - 정리 작업 간격 (초, 기본 1분)
        """
        self.sessions: Dict[str, MobileDeviceSession] = {}
        self.session_timeout = session_timeout
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()
        
        # 통계 정보
        self.stats = {
            'total_sessions_created': 0,
            'total_locations_processed': 0,
            'active_sessions': 0,
            'last_cleanup_time': time.time()
        }
        
        logger.info("DeviceManager 초기화 완료")
    
    def validate_device_id(self, device_id: str) -> bool:
        """
        Device ID 형식 검증
        Format: device_{timestamp}_{random_string}
        """
        if not device_id or not isinstance(device_id, str):
            return False
        
        # 정규표현식으로 형식 검증
        pattern = r'^device_\d{10}_[a-zA-Z0-9]{12}$'
        return bool(re.match(pattern, device_id))
    
    def get_or_create_session(self, device_id: str) -> Optional[MobileDeviceSession]:
        """디바이스 세션 조회 또는 생성"""
        if not self.validate_device_id(device_id):
            logger.warning(f"잘못된 Device ID 형식: {device_id}")
            return None
        
        # 기존 세션 조회
        if device_id in self.sessions:
            session = self.sessions[device_id]
            if session.is_active():
                return session
            else:
                # 비활성 세션 제거 후 새로 생성
                logger.info(f"비활성 세션 제거 후 재생성: {device_id}")
                del self.sessions[device_id]
        
        # 새 세션 생성
        session = MobileDeviceSession(device_id)
        self.sessions[device_id] = session
        self.stats['total_sessions_created'] += 1
        
        logger.info(f"새로운 디바이스 세션 생성: {device_id}")
        return session
    
    def update_location(self, device_id: str, latitude: float, longitude: float, 
                       timestamp: Optional[float] = None, accuracy: Optional[float] = None) -> Tuple[bool, Optional[MotionData], str]:
        """
        디바이스 위치 업데이트
        
        Parameters:
        device_id: str - 디바이스 ID
        latitude: float - 위도
        longitude: float - 경도
        timestamp: float - 타임스탬프 (선택적, 기본값: 현재 시간)
        accuracy: float - GPS 정확도 (선택적)
        
        Returns:
        Tuple[bool, Optional[MotionData], str] - (성공여부, 모션데이터, 메시지)
        """
        try:
            # 입력 검증
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return False, None, "위도/경도 범위 오류"
            
            session = self.get_or_create_session(device_id)
            if not session:
                return False, None, "유효하지 않은 Device ID"
            
            # 위치 정보 생성
            location = LocationPoint(
                latitude=latitude,
                longitude=longitude,
                timestamp=timestamp or time.time(),
                accuracy=accuracy
            )
            
            # 위치 추가 및 모션 계산
            motion_data = session.add_location(location)
            self.stats['total_locations_processed'] += 1
            
            # 정기 정리 작업
            self._periodic_cleanup()
            
            return True, motion_data, "위치 업데이트 성공"
            
        except Exception as e:
            logger.error(f"위치 업데이트 오류 {device_id}: {str(e)}")
            return False, None, f"내부 오류: {str(e)}"
    
    def get_active_sessions(self) -> List[MobileDeviceSession]:
        """활성 세션 목록 반환"""
        active_sessions = [session for session in self.sessions.values() if session.is_active()]
        self.stats['active_sessions'] = len(active_sessions)
        return active_sessions
    
    def get_all_mobile_objects(self) -> Dict[str, Dict[str, Any]]:
        """
        충돌 예측 시스템과 연동을 위한 모바일 객체 정보 반환
        CollisionPredictor와 호환되는 형식으로 반환
        """
        mobile_objects = {}
        
        for session in self.get_active_sessions():
            current_pos = session.get_current_position()
            if current_pos and session.current_motion:
                mobile_objects[session.device_id] = {
                    'position': (current_pos.latitude, current_pos.longitude),
                    'speed': session.current_motion.speed,
                    'heading': session.current_motion.heading,
                    'timestamp': current_pos.timestamp,
                    'type': 'mobile_user',
                    'source': 'mobile_device'
                }
        
        return mobile_objects
    
    def _periodic_cleanup(self):
        """정기적으로 비활성 세션 정리"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        # 비활성 세션 제거
        inactive_sessions = []
        for device_id, session in self.sessions.items():
            if not session.is_active(self.session_timeout):
                inactive_sessions.append(device_id)
        
        for device_id in inactive_sessions:
            del self.sessions[device_id]
            logger.info(f"비활성 세션 제거: {device_id}")
        
        self.last_cleanup = current_time
        self.stats['last_cleanup_time'] = current_time
        
        if inactive_sessions:
            logger.info(f"정리 완료: {len(inactive_sessions)}개 비활성 세션 제거")
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        self.stats['active_sessions'] = len(self.get_active_sessions())
        self.stats['total_sessions'] = len(self.sessions)
        return self.stats.copy()
    
    def get_session_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """특정 세션 정보 반환"""
        session = self.sessions.get(device_id)
        return session.get_session_info() if session else None

# 전역 DeviceManager 인스턴스
device_manager = DeviceManager()