"""
모바일 사용자 데이터와 YOLO 충돌 예측 시스템 통합
"""
import time
from typing import Dict, List, Any, Optional
from app.services.device_manager import device_manager
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class MobileCollisionIntegrator:
    """모바일 사용자와 카메라 감지 객체를 통합하여 충돌 예측을 수행하는 클래스"""
    
    def __init__(self):
        self.mobile_objects_cache = {}  # 모바일 객체 캐시
        self.last_update = time.time()
        
    def integrate_mobile_users_with_predictor(self, video_processor):
        """
        모바일 사용자 데이터를 비디오 프로세서의 충돌 예측 시스템에 통합
        
        Parameters:
        video_processor: VideoProcessor - 비디오 처리기 인스턴스
        """
        try:
            if not video_processor._is_initialized or not hasattr(video_processor, 'predictor'):
                return
            
            # 활성 모바일 세션에서 객체 정보 가져오기
            mobile_objects = device_manager.get_all_mobile_objects()
            
            if not mobile_objects:
                return
                
            # 모바일 객체를 충돌 예측기에 추가
            for device_id, obj_data in mobile_objects.items():
                try:
                    # 충돌 예측기의 객체 추가 메서드 호출
                    video_processor.predictor.add_object(
                        obj_id=device_id,
                        position=obj_data['position'],
                        speed=obj_data['speed'],
                        heading=obj_data['heading'],
                        timestamp=obj_data['timestamp'],
                        obj_type='mobile_user'
                    )
                    
                except Exception as e:
                    logger.error(f"모바일 객체 {device_id} 추가 오류: {str(e)}")
            
            self.mobile_objects_cache = mobile_objects
            self.last_update = time.time()
            
            logger.debug(f"모바일 사용자 {len(mobile_objects)}명 충돌 예측 시스템에 통합 완료")
            
        except Exception as e:
            logger.error(f"모바일 사용자 통합 오류: {str(e)}")
    
    def get_collision_warning_for_mobile_user(self, device_id: str, video_processor) -> Optional[Dict[str, Any]]:
        """
        특정 모바일 사용자에 대한 충돌 경고 계산
        
        Parameters:
        device_id: str - 디바이스 ID
        video_processor: VideoProcessor - 비디오 처리기 인스턴스
        
        Returns:
        Optional[Dict] - 충돌 경고 정보 또는 None
        """
        try:
            if not video_processor._is_initialized or not hasattr(video_processor, 'predictor'):
                return None
            
            # 모바일 사용자 데이터 통합
            self.integrate_mobile_users_with_predictor(video_processor)
            
            # 충돌 예측 수행
            predictions = video_processor.predictor.predict_collisions()
            
            if not predictions or 'collisions' not in predictions:
                return None
            
            # 해당 모바일 사용자가 관련된 충돌 위험 찾기
            user_collision_risks = []
            collisions = predictions['collisions']
            
            for (obj_id1, obj_id2), risk_score in collisions.items():
                if device_id == obj_id1 or device_id == obj_id2:
                    # 상대방 객체 ID 찾기
                    other_obj_id = obj_id2 if device_id == obj_id1 else obj_id1
                    
                    user_collision_risks.append({
                        'other_object_id': other_obj_id,
                        'risk_score': risk_score,
                        'collision_pair': (obj_id1, obj_id2)
                    })
            
            if not user_collision_risks:
                return None
            
            # 가장 위험한 충돌 선택
            highest_risk = max(user_collision_risks, key=lambda x: x['risk_score'])
            
            # 상대방 객체 정보 가져오기
            other_obj_info = self._get_object_info(highest_risk['other_object_id'], video_processor)
            
            if not other_obj_info:
                return None
            
            # 모바일 사용자 정보 가져오기
            mobile_session = device_manager.sessions.get(device_id)
            if not mobile_session or not mobile_session.current_motion:
                return None
            
            # 충돌 경고 정보 구성
            warning_info = self._build_collision_warning(
                mobile_session=mobile_session,
                other_obj_info=other_obj_info,
                risk_score=highest_risk['risk_score'],
                predictions=predictions
            )
            
            return warning_info
            
        except Exception as e:
            logger.error(f"모바일 사용자 {device_id} 충돌 경고 계산 오류: {str(e)}")
            return None
    
    def _get_object_info(self, obj_id: str, video_processor) -> Optional[Dict[str, Any]]:
        """객체 정보 가져오기 (카메라 감지 객체 또는 모바일 사용자)"""
        try:
            # 카메라 감지 객체에서 찾기
            if hasattr(video_processor, 'detected_objects') and video_processor.detected_objects:
                if obj_id in video_processor.detected_objects:
                    return video_processor.detected_objects[obj_id]
            
            # 모바일 사용자에서 찾기
            if obj_id in self.mobile_objects_cache:
                return self.mobile_objects_cache[obj_id]
            
            return None
            
        except Exception as e:
            logger.error(f"객체 정보 조회 오류 {obj_id}: {str(e)}")
            return None
    
    def _build_collision_warning(self, mobile_session, other_obj_info: Dict, 
                                risk_score: float, predictions: Dict) -> Dict[str, Any]:
        """충돌 경고 정보 구성"""
        try:
            # 상대방 객체 타입 결정
            other_obj_type = other_obj_info.get('type', 'vehicle')
            if other_obj_type == 'mobile_user':
                other_obj_type = 'person'  # 모바일 사용자는 보행자로 분류
            
            # 거리 계산
            mobile_pos = mobile_session.get_current_position()
            other_pos = other_obj_info.get('position')
            
            distance = 0.0
            if mobile_pos and other_pos:
                from app.utils.coord_utils import calculate_distance
                distance = calculate_distance(
                    mobile_pos.latitude, mobile_pos.longitude,
                    other_pos[0], other_pos[1]
                )
            
            # TTC 계산
            mobile_speed = mobile_session.current_motion.speed
            other_speed = other_obj_info.get('speed', 0)
            relative_speed = abs(mobile_speed - other_speed)
            ttc = distance / max(relative_speed, 0.1) if distance > 0 else float('inf')
            
            # 방향 계산 (간단화된 버전)
            relative_direction = self._calculate_relative_direction(
                mobile_session.current_motion.heading,
                other_obj_info.get('heading', 0)
            )
            
            # 위험도 레벨 결정
            severity = self._get_severity_level(risk_score)
            
            # 충돌 확률 계산 (위험도 점수를 기반으로)
            collision_probability = min(risk_score / 100.0, 1.0)
            
            warning_info = {
                'objectType': other_obj_type,
                'relativeDirection': relative_direction,
                'speed_kph': other_obj_info.get('speed', 0) * 3.6,
                'distance': distance,
                'ttc': ttc if ttc != float('inf') else 999.9,
                'collisionProbability': collision_probability,
                'severity': severity,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            }
            
            return warning_info
            
        except Exception as e:
            logger.error(f"충돌 경고 정보 구성 오류: {str(e)}")
            return {
                'objectType': 'unknown',
                'relativeDirection': 'front',
                'speed_kph': 0,
                'distance': 0,
                'ttc': 999.9,
                'collisionProbability': 0.5,
                'severity': 'medium',
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            }
    
    def _calculate_relative_direction(self, mobile_heading: float, other_heading: float) -> str:
        """상대적 방향 계산 (간단화된 버전)"""
        try:
            # 방향 차이 계산
            heading_diff = abs(mobile_heading - other_heading)
            if heading_diff > 180:
                heading_diff = 360 - heading_diff
            
            # 8방향으로 분류
            if heading_diff < 22.5:
                return 'front'
            elif heading_diff < 67.5:
                return 'front-right' if other_heading > mobile_heading else 'front-left'
            elif heading_diff < 112.5:
                return 'right' if other_heading > mobile_heading else 'left'
            elif heading_diff < 157.5:
                return 'rear-right' if other_heading > mobile_heading else 'rear-left'
            else:
                return 'rear'
                
        except:
            return 'front'  # 기본값
    
    def _get_severity_level(self, risk_score: float) -> str:
        """위험도 점수를 기반으로 심각도 레벨 결정"""
        if risk_score >= 85:
            return 'critical'
        elif risk_score >= 70:
            return 'high'
        elif risk_score >= 55:
            return 'medium'
        elif risk_score >= 40:
            return 'low'
        else:
            return 'low'
    
    def get_stats(self) -> Dict[str, Any]:
        """통합기 통계 정보 반환"""
        return {
            'mobile_objects_count': len(self.mobile_objects_cache),
            'last_update': self.last_update,
            'integration_active': bool(self.mobile_objects_cache)
        }

# 전역 통합기 인스턴스
mobile_integrator = MobileCollisionIntegrator()