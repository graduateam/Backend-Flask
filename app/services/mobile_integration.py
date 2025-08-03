"""
모바일 사용자 데이터와 YOLO 충돌 예측 시스템 통합
"""
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import deque
from app.services.device_manager import device_manager
from app.utils.logger import setup_logger
from app.utils.coord_utils import calculate_distance
from config import DUPLICATE_DETECTION_SETTINGS, ADVANCED_MATCHING_SETTINGS

logger = setup_logger(__name__)

class MatchingHistory:
    """매칭 히스토리 추적 클래스 - 최적화된 메모리 관리"""
    
    def __init__(self, max_entries=None):
        self.max_entries = max_entries or ADVANCED_MATCHING_SETTINGS['max_history_entries']
        self.history = {}  # {device_id: deque([MatchEntry, ...])}
        self.last_cleanup = time.time()
        self.cleanup_interval = ADVANCED_MATCHING_SETTINGS['inactive_user_cleanup_interval']
        
    def add_entry(self, device_id: str, matched_object_id: str, confidence: float, 
                  distance: float, user_speed: float, user_heading: float, timestamp: float):
        """매칭 히스토리 엔트리 추가 (입력 검증 포함)"""
        # 입력 검증
        if not device_id or not matched_object_id:
            return
        
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            confidence = ADVANCED_MATCHING_SETTINGS['scoring_defaults']['default_confidence']
            
        if not isinstance(distance, (int, float)) or distance < 0:
            distance = 0.0
        
        if device_id not in self.history:
            self.history[device_id] = deque(maxlen=self.max_entries)
            
        entry = {
            'matched_object_id': matched_object_id,
            'confidence': confidence,
            'distance': distance,
            'user_speed': max(0, user_speed) if isinstance(user_speed, (int, float)) else 0,
            'user_heading': user_heading % 360 if isinstance(user_heading, (int, float)) else 0,
            'timestamp': timestamp
        }
        
        self.history[device_id].append(entry)
        
        # 주기적 정리 실행
        self._periodic_cleanup()
    
    def get_recent_entries(self, device_id: str, count: int = 3) -> List[Dict]:
        """최근 매칭 엔트리 조회"""
        if device_id not in self.history:
            return []
        entries = list(self.history[device_id])
        return entries[-count:] if count > 0 else entries
    
    def get_distance_history(self, device_id: str, window: int = 3) -> List[float]:
        """거리 히스토리 조회"""
        entries = self.get_recent_entries(device_id, window)
        return [entry['distance'] for entry in entries]
    
    def get_speed_history(self, device_id: str, window: int = 3) -> List[float]:
        """속도 히스토리 조회"""
        entries = self.get_recent_entries(device_id, window)
        return [entry['user_speed'] for entry in entries]
    
    def clear_user_history(self, device_id: str):
        """특정 사용자 히스토리 초기화"""
        if device_id in self.history:
            del self.history[device_id]
            logger.debug(f"[MEMORY-CLEANUP] 사용자 {device_id} 히스토리 정리")
    
    def _periodic_cleanup(self):
        """주기적 비활성 사용자 정리"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        inactive_users = []
        for device_id, entries in self.history.items():
            if not entries:
                inactive_users.append(device_id)
                continue
                
            last_entry_time = entries[-1]['timestamp']
            if current_time - last_entry_time > self.cleanup_interval:
                inactive_users.append(device_id)
        
        for device_id in inactive_users:
            del self.history[device_id]
        
        if inactive_users:
            logger.info(f"[MEMORY-CLEANUP] 비활성 사용자 {len(inactive_users)}명 정리: {inactive_users}")
        
        self.last_cleanup = current_time
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """메모리 사용 통계"""
        total_entries = sum(len(entries) for entries in self.history.values())
        return {
            'active_users': len(self.history),
            'total_entries': total_entries,
            'avg_entries_per_user': total_entries / len(self.history) if self.history else 0,
            'last_cleanup': self.last_cleanup
        }

class MatchingValidator:
    """매칭 검증 클래스"""
    
    def __init__(self, history: MatchingHistory):
        self.history = history
        self.settings = ADVANCED_MATCHING_SETTINGS
        self.last_validation = {}
        self.last_rematch = {}  # 재매칭 쿨다운 추적
        
    def should_validate(self, device_id: str) -> bool:
        """검증이 필요한지 확인"""
        current_time = time.time()
        last_time = self.last_validation.get(device_id, 0)
        return current_time - last_time >= self.settings['validation_interval']
    
    def validate_match(self, device_id: str, mobile_obj: Dict, matched_object: Dict, 
                      detected_objects: List[Dict]) -> float:
        """매칭 신뢰도 검증"""
        try:
            current_time = time.time()
            self.last_validation[device_id] = current_time
            
            # 거리 일관성 점수
            distance_score = self._validate_distance_consistency(device_id, mobile_obj, matched_object)
            
            # 움직임 패턴 점수
            movement_score = self._validate_movement_pattern(device_id, mobile_obj, matched_object)
            
            # 객체 지속성 점수
            persistence_score = self._validate_object_persistence(matched_object, detected_objects)
            
            # 가중 평균 계산
            weights = self.settings['validation_weights']
            confidence = (
                distance_score * weights['distance_consistency'] +
                movement_score * weights['movement_pattern'] +
                persistence_score * weights['object_persistence']
            )
            
            # 히스토리에 기록
            position = mobile_obj.get('position', [0, 0])
            distance = calculate_distance(
                position[0], position[1],
                matched_object.get('coords', [0, 0])[0],
                matched_object.get('coords', [0, 0])[1]
            ) if len(position) == 2 and matched_object.get('coords') else 0
            
            self.history.add_entry(
                device_id, matched_object.get('id', ''),
                confidence, distance,
                mobile_obj.get('speed', 0),
                mobile_obj.get('heading', 0),
                current_time
            )
            
            logger.debug(f"[MATCHING-VALIDATION] {device_id}: 신뢰도={confidence:.3f} "
                        f"(거리={distance_score:.3f}, 움직임={movement_score:.3f}, 지속성={persistence_score:.3f})")
            
            return confidence
            
        except Exception as e:
            logger.error(f"[MATCHING-VALIDATION] {device_id} 검증 오류: {str(e)}")
            return 0.5  # 기본값
    
    def _validate_distance_consistency(self, device_id: str, mobile_obj: Dict, matched_object: Dict) -> float:
        """거리 일관성 검증 (단순화됨)"""
        try:
            position = mobile_obj.get('position')
            obj_coords = matched_object.get('coords')
            
            if not position or not obj_coords or len(position) != 2 or len(obj_coords) != 2:
                return self.settings['scoring_defaults']['default_confidence']
            
            current_distance = calculate_distance(
                position[0], position[1],
                obj_coords[0], obj_coords[1]
            )
            
            distance_history = self.history.get_distance_history(device_id, 3)
            
            if len(distance_history) < 2:
                return self.settings['scoring_defaults']['no_history_score']
            
            # 단순한 거리 점프 검증 (복잡한 예측 알고리즘 제거)
            max_jump = self.settings['distance_validation']['max_jump_threshold']
            gps_noise = self.settings['distance_validation']['gps_noise_threshold']
            last_distance = distance_history[-1]
            distance_jump = abs(current_distance - last_distance)
            
            # GPS 노이즈 범위 내에서는 높은 점수
            if distance_jump <= gps_noise:
                return self.settings['scoring_defaults']['initial_high_score']
            
            # 큰 점프는 페널티
            if distance_jump > max_jump:
                logger.warning(f"[DISTANCE-VALIDATION] {device_id}: 거리 점프 {distance_jump:.2f}m > {max_jump}m")
                return self.settings['scoring_defaults']['distance_jump_penalty']
            
            # 중간 범위는 거리에 비례하여 점수 감소
            jump_ratio = (distance_jump - gps_noise) / (max_jump - gps_noise)
            score = self.settings['scoring_defaults']['initial_high_score'] * (1 - jump_ratio * 0.6)
            return max(score, self.settings['scoring_defaults']['distance_jump_penalty'])
            
        except Exception as e:
            logger.error(f"[DISTANCE-VALIDATION] {device_id} 오류: {str(e)}")
            return self.settings['scoring_defaults']['default_confidence']
    
    def _validate_movement_pattern(self, device_id: str, mobile_obj: Dict, matched_object: Dict) -> float:
        """움직임 패턴 검증 (수정됨: 사용자 vs 매칭된 객체 비교)"""
        try:
            user_speed = mobile_obj.get('speed', 0)
            user_heading = mobile_obj.get('heading', 0)
            
            # 매칭된 객체의 움직임 데이터 추정
            obj_speed = self._estimate_object_speed(matched_object, device_id)
            obj_heading = self._estimate_object_heading(matched_object, device_id)
            
            tolerances = self.settings['movement_tolerances']
            speed_threshold = tolerances['speed_diff_threshold']
            heading_threshold = tolerances['heading_diff_threshold']
            min_speed = tolerances['min_speed_for_heading']
            
            # 0으로 나누기 방지
            if speed_threshold <= 0:
                speed_threshold = 3.0  # 기본값
            if heading_threshold <= 0:
                heading_threshold = 45.0  # 기본값
            
            # 속도 일관성 검증 (사용자 vs 매칭된 객체)
            speed_diff = abs(user_speed - obj_speed)
            speed_score = max(0, 1 - speed_diff / speed_threshold)
            
            # 방향 일관성 검증 (최소 속도 이상일 때만)
            heading_score = self.settings['scoring_defaults']['initial_high_score']  # 기본값
            
            if user_speed >= min_speed and obj_speed >= min_speed:
                heading_diff = min(abs(user_heading - obj_heading), 
                                 360 - abs(user_heading - obj_heading))
                heading_score = max(0, 1 - heading_diff / heading_threshold)
            else:
                # 속도가 낮으면 방향 검증은 덜 중요
                heading_score = self.settings['scoring_defaults']['no_history_score']
            
            movement_score = (speed_score + heading_score) / 2
            
            logger.debug(f"[MOVEMENT-VALIDATION] {device_id}: 사용자속도={user_speed:.1f} vs 객체속도={obj_speed:.1f}, "
                        f"속도점수={speed_score:.3f}, 방향점수={heading_score:.3f}, 종합={movement_score:.3f}")
            
            return movement_score
            
        except Exception as e:
            logger.error(f"[MOVEMENT-VALIDATION] {device_id} 오류: {str(e)}")
            return self.settings['scoring_defaults']['default_confidence']
    
    def _estimate_object_speed(self, matched_object: Dict, device_id: str) -> float:
        """매칭된 객체의 속도 추정"""
        try:
            # 히스토리에서 최근 위치 변화로 속도 추정
            recent_entries = self.history.get_recent_entries(device_id, 2)
            if len(recent_entries) < 2:
                return 0.0  # 히스토리 부족시 정지 상태로 가정
            
            prev_entry = recent_entries[-2]
            curr_entry = recent_entries[-1]
            
            time_diff = curr_entry['timestamp'] - prev_entry['timestamp']
            if time_diff <= 0:
                return 0.0
            
            distance_diff = abs(curr_entry['distance'] - prev_entry['distance'])
            estimated_speed = distance_diff / time_diff
            
            return min(estimated_speed, 30.0)  # 최대 30m/s로 제한
            
        except Exception:
            return 0.0
    
    def _estimate_object_heading(self, matched_object: Dict, device_id: str) -> float:
        """매칭된 객체의 방향 추정"""
        try:
            # 단순화: 사용자의 평균 과거 방향 사용
            # 실제로는 객체의 위치 변화로 방향을 계산해야 하지만
            # 현재 구조에서는 제한적이므로 보수적 접근
            recent_entries = self.history.get_recent_entries(device_id, 3)
            if len(recent_entries) < 2:
                return 0.0
            
            headings = [entry['user_heading'] for entry in recent_entries]
            avg_heading = sum(headings) / len(headings)
            return avg_heading % 360
            
        except Exception:
            return 0.0
    
    def _validate_object_persistence(self, matched_object: Dict, detected_objects: List[Dict]) -> float:
        """객체 지속성 검증 (단순화됨)"""
        try:
            obj_id = matched_object.get('id')
            if not obj_id:
                return self.settings['scoring_defaults']['default_confidence']
            
            # 중복 검사 제거: detected_objects에서 온 객체이므로 당연히 존재
            # 대신 객체의 탐지 시간만 확인
            detection_time = matched_object.get('detection_time')
            if detection_time is None:
                # detection_time이 없으면 현재 시간으로 가정 (새 객체)
                penalty = self.settings['persistence_validation']['new_object_penalty']
                return self.settings['scoring_defaults']['persistence_full_score'] - penalty
            
            min_time = self.settings['persistence_validation']['min_detection_time']
            time_since_detection = time.time() - detection_time
            
            if time_since_detection < min_time:
                # 새로 나타난 객체는 페널티
                penalty = self.settings['persistence_validation']['new_object_penalty']
                return self.settings['scoring_defaults']['persistence_full_score'] - penalty
            
            return self.settings['scoring_defaults']['persistence_full_score']  # 안정적으로 탐지되는 객체
            
        except Exception as e:
            logger.error(f"[PERSISTENCE-VALIDATION] 오류: {str(e)}")
            return self.settings['scoring_defaults']['default_confidence']
    
    def should_rematch(self, device_id: str, confidence: float) -> bool:
        """재매칭이 필요한지 판단"""
        if confidence >= self.settings['confidence_threshold']:
            return False
        
        # 쿨다운 확인
        current_time = time.time()
        last_rematch_time = self.last_rematch.get(device_id, 0)
        cooldown = self.settings['rematch_cooldown']
        
        if current_time - last_rematch_time < cooldown:
            logger.debug(f"[REMATCH] {device_id}: 쿨다운 중 ({cooldown - (current_time - last_rematch_time):.1f}초 남음)")
            return False
        
        logger.info(f"[REMATCH] {device_id}: 신뢰도 부족({confidence:.3f} < {self.settings['confidence_threshold']}) - 재매칭 필요")
        self.last_rematch[device_id] = current_time
        return True

class DuplicateObjectResolver:
    """모바일 사용자와 카메라 탐지 객체 간 중복 해결 클래스"""
    
    def __init__(self, distance_threshold=None):
        """
        중복 객체 해결기 초기화
        
        Parameters:
        distance_threshold: float - 중복 판정 거리 임계값 (미터, None시 config에서 가져옴)
        """
        self.distance_threshold = distance_threshold or DUPLICATE_DETECTION_SETTINGS['distance_threshold']
        self.enabled = DUPLICATE_DETECTION_SETTINGS['enabled']
        self.gps_priority = DUPLICATE_DETECTION_SETTINGS['gps_priority']
        
        # 고급 검증 시스템 초기화
        self.advanced_enabled = ADVANCED_MATCHING_SETTINGS['enabled']
        self.history = MatchingHistory()
        self.validator = MatchingValidator(self.history)
        self.current_matches = {}  # {device_id: matched_object_id}
        
        logger.info(f"[DUPLICATE-RESOLVER] 초기화: 임계값={self.distance_threshold}m, "
                   f"기본={self.enabled}, 고급={self.advanced_enabled}")
        
        if self.advanced_enabled:
            logger.info("[ADVANCED-MATCHING] 고급 매칭 시스템 활성화: "
                       "즉시 매칭 + 지속적 검증 + 자동 재매칭")
        
    def find_duplicate_objects(self, mobile_users, detected_objects):
        """
        모바일 사용자와 탐지된 객체들 간 중복 찾기 (일대일 매칭)
        
        Parameters:
        mobile_users: dict - 모바일 사용자 딕셔너리 {device_id: obj_data}
        detected_objects: list - 카메라로 탐지된 객체 리스트
        
        Returns:
        dict - 중복 매칭 정보 {mobile_device_id: detected_object_id}
        """
        duplicate_matches = {}
        
        # 중복 탐지가 비활성화된 경우 빈 결과 반환
        if not self.enabled:
            logger.info("[DUPLICATE-RESOLVER] 중복 탐지 기능이 비활성화됨")
            return duplicate_matches
        
        if not mobile_users or not detected_objects:
            return duplicate_matches
        
        # 🔧 일대일 매칭을 위한 개선: 이미 매칭된 탐지 객체 추적
        already_matched_objects = set()
        
        # 🔧 최적 매칭을 위해 (거리, 모바일_사용자, 탐지_객체) 튜플 리스트 생성
        potential_matches = []
        
        for device_id, mobile_obj in mobile_users.items():
            mobile_pos = mobile_obj.get('position')
            if not mobile_pos or len(mobile_pos) != 2:
                continue
                
            mobile_lat, mobile_lon = mobile_pos
            
            # 탐지된 객체들과 거리 비교
            for detected_obj in detected_objects:
                if not detected_obj or not detected_obj.get('coords'):
                    continue
                    
                detected_coords = detected_obj.get('coords')
                if len(detected_coords) != 2:
                    continue
                
                detected_id = detected_obj.get('id')
                if not detected_id:
                    continue
                    
                detected_lat, detected_lon = detected_coords
                
                # 거리 계산
                distance = calculate_distance(
                    mobile_lat, mobile_lon,
                    detected_lat, detected_lon
                )
                
                # 임계값 이내의 경우 후보로 추가
                if distance <= self.distance_threshold:
                    potential_matches.append((distance, device_id, detected_id, detected_obj))
        
        # 🔧 거리순으로 정렬하여 가장 가까운 매칭부터 처리 (일대일 보장)
        potential_matches.sort(key=lambda x: x[0])
        
        for distance, device_id, detected_id, detected_obj in potential_matches:
            # 이미 매칭된 객체는 건너뛰기
            if detected_id in already_matched_objects:
                continue
                
            # 이미 매칭된 사용자는 건너뛰기 (가장 가까운 것만 유지)
            if device_id in duplicate_matches:
                continue
                
            # 매칭 성공
            duplicate_matches[device_id] = detected_id
            already_matched_objects.add(detected_id)
            logger.info(f"[DUPLICATE-DETECTION] 모바일 사용자 {device_id}와 탐지 객체 {detected_id} 매칭 (거리: {distance:.2f}m)")
        
        return duplicate_matches
    
    def filter_detected_objects(self, detected_objects, excluded_object_ids):
        """
        탐지된 객체 리스트에서 중복 객체들 제거
        
        Parameters:
        detected_objects: list - 원본 탐지 객체 리스트
        excluded_object_ids: list - 제외할 객체 ID 리스트
        
        Returns:
        list - 필터링된 탐지 객체 리스트
        """
        if not excluded_object_ids:
            return detected_objects
            
        # 🔧 성능 최적화: set을 사용하여 O(1) 조회
        excluded_set = set(excluded_object_ids)
        
        filtered_objects = []
        for obj in detected_objects:
            if obj and obj.get('id') not in excluded_set:
                filtered_objects.append(obj)
        
        logger.info(f"[DUPLICATE-FILTERING] {len(detected_objects)}개 객체 중 {len(excluded_object_ids)}개 중복 제거, {len(filtered_objects)}개 유지")
        return filtered_objects
    
    def validate_existing_matches(self, mobile_users, detected_objects):
        """
        기존 매칭에 대한 지속적 검증 및 재매칭
        
        Parameters:
        mobile_users: dict - 모바일 사용자 딕셔너리
        detected_objects: list - 탐지된 객체 리스트
        
        Returns:
        dict - 업데이트된 매칭 정보 {device_id: matched_object_id}
        """
        if not self.advanced_enabled:
            return self.current_matches
        
        updated_matches = {}
        rematch_needed = []
        
        for device_id, matched_obj_id in self.current_matches.items():
            if device_id not in mobile_users:
                # 사용자가 더 이상 활성화되지 않음
                continue
            
            mobile_obj = mobile_users[device_id]
            
            # 매칭된 객체 찾기
            matched_object = None
            for obj in detected_objects:
                if obj and obj.get('id') == matched_obj_id:
                    matched_object = obj
                    break
            
            if not matched_object:
                # 매칭된 객체가 사라짐 - 재매칭 필요
                logger.warning(f"[VALIDATION] {device_id}: 매칭된 객체 {matched_obj_id} 사라짐")
                rematch_needed.append(device_id)
                continue
            
            # 검증이 필요한지 확인
            if not self.validator.should_validate(device_id):
                updated_matches[device_id] = matched_obj_id
                continue
            
            # 신뢰도 검증
            confidence = self.validator.validate_match(
                device_id, mobile_obj, matched_object, detected_objects
            )
            
            # 재매칭 필요 여부 확인
            if self.validator.should_rematch(device_id, confidence):
                rematch_needed.append(device_id)
                # 히스토리 초기화
                self.history.clear_user_history(device_id)
            else:
                updated_matches[device_id] = matched_obj_id
        
        # 재매칭 수행
        if rematch_needed:
            rematch_users = {device_id: mobile_users[device_id] 
                           for device_id in rematch_needed if device_id in mobile_users}
            
            logger.info(f"[REMATCH] {len(rematch_needed)}명 사용자 재매칭 시작: {rematch_needed}")
            new_matches = self.find_duplicate_objects(rematch_users, detected_objects)
            updated_matches.update(new_matches)
        
        self.current_matches = updated_matches
        return updated_matches
    
    def find_duplicate_objects_with_confidence(self, mobile_users, detected_objects):
        """
        신뢰도를 포함한 중복 객체 매칭
        
        Returns:
        dict - 매칭 정보와 신뢰도 {device_id: {'object_id': str, 'confidence': float}}
        """
        # 기본 매칭 수행
        basic_matches = self.find_duplicate_objects(mobile_users, detected_objects)
        
        if not self.advanced_enabled:
            # 기본 신뢰도로 반환
            return {device_id: {'object_id': obj_id, 'confidence': 0.8} 
                   for device_id, obj_id in basic_matches.items()}
        
        enhanced_matches = {}
        
        for device_id, matched_obj_id in basic_matches.items():
            mobile_obj = mobile_users.get(device_id)
            if not mobile_obj:
                continue
            
            # 매칭된 객체 찾기
            matched_object = None
            for obj in detected_objects:
                if obj and obj.get('id') == matched_obj_id:
                    matched_object = obj
                    break
            
            if matched_object:
                # 즉시 신뢰도 계산 (새 매칭의 경우)
                confidence = self._calculate_initial_confidence(mobile_obj, matched_object)
                enhanced_matches[device_id] = {
                    'object_id': matched_obj_id,
                    'confidence': confidence
                }
                
                # 현재 매칭 업데이트
                self.current_matches[device_id] = matched_obj_id
                
                logger.info(f"[NEW-MATCH] {device_id} → {matched_obj_id}, 초기 신뢰도: {confidence:.3f}")
        
        return enhanced_matches
    
    def _calculate_initial_confidence(self, mobile_obj: Dict, matched_object: Dict) -> float:
        """
        새 매칭에 대한 초기 신뢰도 계산 (설정 기반)
        
        Returns:
        float - 초기 신뢰도 (0.0-1.0)
        """
        try:
            position = mobile_obj.get('position', [0, 0])
            obj_coords = matched_object.get('coords', [0, 0])
            
            if len(position) != 2 or len(obj_coords) != 2:
                return ADVANCED_MATCHING_SETTINGS['scoring_defaults']['default_confidence']
            
            # 거리 기반 신뢰도
            distance = calculate_distance(
                position[0], position[1],
                obj_coords[0], obj_coords[1]
            )
            
            # 거리가 가까울수록 높은 신뢰도
            max_distance = self.distance_threshold * 2  # 임계값의 2배를 최대로 설정
            if max_distance <= 0:
                max_distance = 10.0  # 기본값
                
            distance_confidence = max(0, 1 - distance / max_distance)
            
            # 초기 매칭은 거리만 고려 (속도 정보 부족)
            initial_confidence = distance_confidence * ADVANCED_MATCHING_SETTINGS['scoring_defaults']['initial_high_score']
            
            # 설정 범위로 제한
            min_conf = ADVANCED_MATCHING_SETTINGS['scoring_defaults']['distance_jump_penalty']
            max_conf = ADVANCED_MATCHING_SETTINGS['scoring_defaults']['initial_high_score']
            
            return min(max(initial_confidence, min_conf), max_conf)
            
        except Exception as e:
            logger.error(f"[INITIAL-CONFIDENCE] 계산 오류: {str(e)}")
            return ADVANCED_MATCHING_SETTINGS['scoring_defaults']['default_confidence']
    
    def get_match_status(self, device_id: str) -> Optional[Dict]:
        """
        특정 사용자의 매칭 상태 조회
        
        Returns:
        dict - 매칭 상태 정보 또는 None
        """
        if device_id not in self.current_matches:
            return None
        
        matched_obj_id = self.current_matches[device_id]
        recent_entries = self.history.get_recent_entries(device_id, 1)
        
        confidence = recent_entries[0]['confidence'] if recent_entries else 0.5
        
        return {
            'matched_object_id': matched_obj_id,
            'confidence': confidence,
            'history_count': len(self.history.history.get(device_id, [])),
            'last_validation': self.validator.last_validation.get(device_id, 0)
        }

# 전역 중복 해결기 인스턴스
duplicate_resolver = DuplicateObjectResolver()

class MobileCollisionIntegrator:
    """모바일 사용자와 카메라 감지 객체를 통합하여 충돌 예측을 수행하는 클래스"""
    
    def __init__(self):
        self.mobile_objects_cache = {}  # 모바일 객체 캐시
        self.last_update = time.time()
        
    def integrate_mobile_users_with_predictor(self, video_processor, target_device_id=None):
        """
        모바일 사용자 데이터를 비디오 프로세서의 충돌 예측 시스템에 통합
        중복 객체 탐지 및 제거 로직 포함
        
        Parameters:
        video_processor: VideoProcessor - 비디오 처리기 인스턴스
        target_device_id: str - 특정 사용자만 처리할 경우 해당 디바이스 ID (성능 최적화용)
        """
        try:
            if not video_processor._is_initialized or not hasattr(video_processor, 'predictor'):
                logger.warning("[MOBILE-INTEGRATION] 비디오 프로세서가 초기화되지 않았거나 예측기가 없음")
                return
            
            # 🔧 성능 최적화: 특정 사용자만 처리하는 경우
            if target_device_id:
                mobile_objects = {}
                all_mobile_objects = device_manager.get_all_mobile_objects()
                if target_device_id in all_mobile_objects:
                    mobile_objects[target_device_id] = all_mobile_objects[target_device_id]
                    logger.debug(f"[MOBILE-INTEGRATION] 특정 사용자 처리: {target_device_id}")
                else:
                    logger.warning(f"[MOBILE-INTEGRATION] 요청된 사용자 {target_device_id}를 찾을 수 없음")
            else:
                # 모든 활성 모바일 세션에서 객체 정보 가져오기
                mobile_objects = device_manager.get_all_mobile_objects()
            
            if not mobile_objects:
                logger.debug("[MOBILE-INTEGRATION] 처리할 모바일 객체 없음")
                return
            
            # 🔧 고급 중복 객체 탐지 및 검증 로직 (지속적 검증 포함)
            detected_objects = getattr(video_processor, 'detected_objects', None)
            if detected_objects and len(detected_objects) > 0:
                try:
                    logger.info(f"[ADVANCED-DUPLICATE-RESOLVER] 고급 중복 탐지 시작: 모바일 사용자 {len(mobile_objects)}명, 탐지 객체 {len(detected_objects)}개")
                    
                    # 1단계: 기존 매칭 검증 및 재매칭
                    validated_matches = duplicate_resolver.validate_existing_matches(mobile_objects, detected_objects)
                    
                    # 2단계: 새로운 사용자에 대한 즉시 매칭
                    new_users = {device_id: obj for device_id, obj in mobile_objects.items() 
                               if device_id not in validated_matches}
                    
                    if new_users:
                        logger.debug(f"[ADVANCED-DUPLICATE-RESOLVER] 새 사용자 {len(new_users)}명 즉시 매칭")
                        new_matches_with_confidence = duplicate_resolver.find_duplicate_objects_with_confidence(
                            new_users, detected_objects
                        )
                        
                        # 새 매칭을 기존 매칭에 추가 (object_id만 추출)
                        for device_id, match_info in new_matches_with_confidence.items():
                            validated_matches[device_id] = match_info['object_id']
                    
                    # 3단계: 중복으로 매칭된 객체들 제외
                    if validated_matches:
                        excluded_object_ids = list(validated_matches.values())
                        
                        # 🔧 필터링된 객체로 충돌 예측 업데이트
                        filtered_objects = duplicate_resolver.filter_detected_objects(detected_objects, excluded_object_ids)
                        self._temporarily_update_predictor_objects(video_processor, filtered_objects)
                        
                        logger.info(f"[ADVANCED-DUPLICATE-RESOLVER] 매칭 완료: {len(validated_matches)}개 쌍")
                        
                        # 디버그: 매칭 상태 로깅
                        for device_id, matched_obj_id in validated_matches.items():
                            status = duplicate_resolver.get_match_status(device_id)
                            if status:
                                logger.debug(f"[MATCH-STATUS] {device_id} → {matched_obj_id}, "
                                           f"신뢰도: {status['confidence']:.3f}, "
                                           f"히스토리: {status['history_count']}개")
                    else:
                        logger.info("[ADVANCED-DUPLICATE-RESOLVER] 중복 객체 없음")
                        
                except Exception as duplicate_error:
                    logger.error(f"[ADVANCED-DUPLICATE-RESOLVER] 오류: {str(duplicate_error)}")
                    import traceback
                    logger.error(f"[ADVANCED-DUPLICATE-RESOLVER] 상세 오류: {traceback.format_exc()}")
                    
                    # 오류 발생 시 기본 로직으로 폴백
                    try:
                        logger.warning("[ADVANCED-DUPLICATE-RESOLVER] 기본 로직으로 폴백")
                        basic_matches = duplicate_resolver.find_duplicate_objects(mobile_objects, detected_objects)
                        if basic_matches:
                            excluded_ids = list(basic_matches.values())
                            filtered_objects = duplicate_resolver.filter_detected_objects(detected_objects, excluded_ids)
                            self._temporarily_update_predictor_objects(video_processor, filtered_objects)
                    except Exception as fallback_error:
                        logger.error(f"[DUPLICATE-RESOLVER] 폴백 로직도 실패: {str(fallback_error)}")
            else:
                logger.debug("[ADVANCED-DUPLICATE-RESOLVER] 감지된 객체 없음")
            
            # 🔧 모바일 객체를 충돌 예측기에 추가 (안전성 강화)
            added_count = 0
            for device_id, obj_data in mobile_objects.items():
                try:
                    # 데이터 유효성 검증
                    if not obj_data or not isinstance(obj_data, dict):
                        logger.warning(f"[MOBILE-INTEGRATION] 모바일 객체 {device_id}: 유효하지 않은 데이터")
                        continue
                        
                    position = obj_data.get('position')
                    if not position or len(position) != 2:
                        logger.warning(f"[MOBILE-INTEGRATION] 모바일 객체 {device_id}: 유효하지 않은 위치 데이터")
                        continue
                    
                    # 충돌 예측기의 객체 추가 메서드 호출
                    video_processor.predictor.add_object(
                        obj_id=device_id,
                        position=position,
                        speed=obj_data.get('speed', 0),
                        heading=obj_data.get('heading', 0),
                        timestamp=obj_data.get('timestamp', time.time()),
                        obj_type='mobile_user'
                    )
                    added_count += 1
                    
                except Exception as e:
                    logger.error(f"[MOBILE-INTEGRATION] 모바일 객체 {device_id} 추가 오류: {str(e)}")
                    # 개별 객체 추가 실패는 전체 프로세스를 중단하지 않음
                    continue
            
            # 🔧 캐시 및 상태 업데이트
            if target_device_id:
                # 특정 사용자만 처리한 경우, 해당 사용자만 캐시 업데이트
                if mobile_objects:
                    self.mobile_objects_cache.update(mobile_objects)
            else:
                # 전체 사용자 처리한 경우, 전체 캐시 교체
                self.mobile_objects_cache = mobile_objects
                
            self.last_update = time.time()
            
            logger.debug(f"[MOBILE-INTEGRATION] 모바일 사용자 {added_count}/{len(mobile_objects)}명 충돌 예측 시스템에 통합 완료")
            
        except Exception as e:
            logger.error(f"[MOBILE-INTEGRATION] 모바일 사용자 통합 오류: {str(e)}")
            import traceback
            logger.error(f"[MOBILE-INTEGRATION] 상세 오류: {traceback.format_exc()}")
            # 오류 발생 시에도 시스템이 계속 동작하도록 함
    
    def _temporarily_update_predictor_objects(self, video_processor, filtered_objects):
        """
        CollisionPredictor에 필터링된 객체들을 임시로 업데이트
        (원본 video_processor.detected_objects는 수정하지 않음)
        """
        try:
            if not hasattr(video_processor, 'predictor') or filtered_objects is None:
                logger.warning("[PREDICTOR-UPDATE] 예측기가 없거나 필터링된 객체가 None")
                return
            
            predictor = video_processor.predictor
            if not hasattr(predictor, 'objects'):
                logger.warning("[PREDICTOR-UPDATE] 예측기에 objects 속성이 없음")
                return
                
            # 예측기의 기존 카메라 감지 객체들을 제거하고 필터링된 객체들로 업데이트
            camera_object_ids = []
            try:
                # 기존 카메라 감지 객체들의 ID 수집 (mobile_user가 아닌 것들)
                for obj_id in list(predictor.objects.keys()):
                    # device_id 형태가 아닌 것들은 카메라 감지 객체로 간주
                    if not str(obj_id).startswith('device_'):
                        camera_object_ids.append(obj_id)
                
                # 기존 카메라 감지 객체들 제거
                removed_count = 0
                for obj_id in camera_object_ids:
                    try:
                        if obj_id in predictor.objects:
                            del predictor.objects[obj_id]
                            removed_count += 1
                    except Exception as remove_error:
                        logger.warning(f"[PREDICTOR-UPDATE] 객체 {obj_id} 제거 실패: {str(remove_error)}")
                        
            except Exception as cleanup_error:
                logger.error(f"[PREDICTOR-UPDATE] 기존 객체 정리 오류: {str(cleanup_error)}")
                
            # 필터링된 객체들을 예측기에 추가
            current_time = time.time()
            added_count = 0
            for obj in filtered_objects:
                try:
                    if not obj:
                        continue
                        
                    obj_id = obj.get('id')
                    coords = obj.get('coords')
                    
                    if not obj_id or not coords or len(coords) != 2:
                        logger.warning(f"[PREDICTOR-UPDATE] 유효하지 않은 객체 데이터: {obj}")
                        continue
                        
                    lat, lon = coords
                    predictor.update(obj_id, lat, lon, current_time)
                    added_count += 1
                    
                except Exception as add_error:
                    logger.warning(f"[PREDICTOR-UPDATE] 객체 추가 실패: {str(add_error)}")
                    continue
            
            logger.debug(f"[PREDICTOR-UPDATE] 카메라 객체 업데이트: 제거 {removed_count}개, 추가 {added_count}개")
                
        except Exception as e:
            logger.error(f"예측기 객체 업데이트 오류: {str(e)}")
    
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
            logger.info(f"[COLLISION-CHECK] 모바일 사용자 {device_id} 충돌 경고 계산 시작")
            
            if not video_processor._is_initialized or not hasattr(video_processor, 'predictor'):
                logger.warning(f"[COLLISION-CHECK] 비디오 프로세서 미초기화: initialized={getattr(video_processor, '_is_initialized', False)}")
                return None
            
            # 현재 감지된 객체 수 로깅
            detected_count = len(video_processor.detected_objects) if video_processor.detected_objects else 0
            logger.info(f"[COLLISION-CHECK] 현재 감지된 객체 수: {detected_count}")
            
            # 🔧 성능 최적화: 특정 모바일 사용자만 통합
            self.integrate_mobile_users_with_predictor(video_processor, target_device_id=device_id)
            
            # 모바일 사용자 전용 충돌 예측 수행 (성능 최적화)
            collisions = video_processor.predictor.predict_mobile_user_collisions(device_id)
            logger.info(f"[COLLISION-CHECK] 모바일 사용자 전용 충돌 예측 결과: {len(collisions) if collisions else 0}개 충돌 쌍")
            
            if not collisions:
                logger.info(f"[COLLISION-CHECK] {device_id}: 충돌 위험 없음")
                return None
            
            # 해당 모바일 사용자가 관련된 충돌 위험 찾기
            user_collision_risks = []
            
            for (obj_id1, obj_id2), risk_score in collisions.items():
                logger.debug(f"[COLLISION-CHECK] 충돌 쌍 확인: {obj_id1} <-> {obj_id2}, 위험도: {risk_score}")
                if device_id == obj_id1 or device_id == obj_id2:
                    # 상대방 객체 ID 찾기
                    other_obj_id = obj_id2 if device_id == obj_id1 else obj_id1
                    logger.info(f"[COLLISION-CHECK] 모바일 사용자 {device_id} 충돌 위험 발견: 상대방={other_obj_id}, 위험도={risk_score}")
                    
                    user_collision_risks.append({
                        'other_object_id': other_obj_id,
                        'risk_score': risk_score,
                        'collision_pair': (obj_id1, obj_id2)
                    })
            
            if not user_collision_risks:
                logger.info(f"[COLLISION-CHECK] {device_id}: 모바일 사용자와 관련된 충돌 위험 없음")
                return None
            
            # 가장 위험한 충돌 선택
            highest_risk = max(user_collision_risks, key=lambda x: x['risk_score'])
            logger.info(f"[COLLISION-CHECK] {device_id}: 최고 위험도 충돌 선택 - 위험도={highest_risk['risk_score']}, 상대방={highest_risk['other_object_id']}")
            
            # 상대방 객체 정보 가져오기
            other_obj_info = self._get_object_info(highest_risk['other_object_id'], video_processor)
            
            if not other_obj_info:
                logger.warning(f"[COLLISION-CHECK] {device_id}: 상대방 객체 정보를 찾을 수 없음: {highest_risk['other_object_id']}")
                return None
            
            # 모바일 사용자 정보 가져오기
            mobile_session = device_manager.sessions.get(device_id)
            if not mobile_session or not mobile_session.current_motion:
                logger.warning(f"[COLLISION-CHECK] {device_id}: 모바일 세션 또는 모션 데이터 없음")
                return None
            
            # 충돌 경고 정보 구성
            warning_info = self._build_collision_warning(
                mobile_session=mobile_session,
                other_obj_info=other_obj_info,
                risk_score=highest_risk['risk_score'],
                collisions=collisions
            )
            
            logger.info(f"[COLLISION-CHECK] {device_id}: 충돌 경고 생성 완료 - {warning_info['objectType']}, {warning_info['severity']}")
            return warning_info
            
        except Exception as e:
            logger.error(f"모바일 사용자 {device_id} 충돌 경고 계산 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _get_object_info(self, obj_id: str, video_processor) -> Optional[Dict[str, Any]]:
        """객체 정보 가져오기 (카메라 감지 객체 또는 모바일 사용자)"""
        try:
            if not obj_id:
                logger.warning("[OBJECT-INFO] 객체 ID가 None 또는 빈 문자열")
                return None
                
            # 카메라 감지 객체에서 찾기 (detected_objects는 리스트)
            if hasattr(video_processor, 'detected_objects') and video_processor.detected_objects:
                for obj in video_processor.detected_objects:
                    if not obj:
                        continue
                        
                    if obj.get('id') == obj_id:
                        logger.info(f"[OBJECT-FOUND] 카메라 감지 객체 발견: {obj_id}, 타입: {obj.get('class_name')}")
                        
                        # 🔧 안전성 체크: coords가 유효한지 확인
                        coords = obj.get('coords')
                        if coords and len(coords) == 2:
                            position = coords
                        else:
                            logger.warning(f"[OBJECT-INFO] 카메라 객체 {obj_id}의 좌표 정보 유효하지 않음: {coords}")
                            position = None
                            
                        return {
                            'id': obj.get('id'),
                            'type': obj.get('class_name', 'vehicle'),
                            'position': position,  # (lat, lon)
                            'speed': 0,  # 카메라 객체는 속도 정보 없음
                            'heading': 0,  # 카메라 객체는 방향 정보 없음
                            'timestamp': obj.get('detection_time', time.time())
                        }
            
            # 모바일 사용자에서 찾기
            if self.mobile_objects_cache and obj_id in self.mobile_objects_cache:
                mobile_obj = self.mobile_objects_cache[obj_id]
                if mobile_obj and isinstance(mobile_obj, dict):
                    logger.info(f"[OBJECT-FOUND] 모바일 사용자 발견: {obj_id}")
                    return mobile_obj
                else:
                    logger.warning(f"[OBJECT-INFO] 모바일 객체 {obj_id}의 데이터가 유효하지 않음")
            
            logger.warning(f"[OBJECT-NOT-FOUND] 객체를 찾을 수 없음: {obj_id}")
            return None
            
        except Exception as e:
            logger.error(f"객체 정보 조회 오류 {obj_id}: {str(e)}")
            return None
    
    def _build_collision_warning(self, mobile_session, other_obj_info: Dict, 
                                risk_score: float, collisions: Dict) -> Dict[str, Any]:
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
                'timestamp': datetime.now().isoformat() + 'Z'
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
                'timestamp': datetime.now().isoformat() + 'Z'
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