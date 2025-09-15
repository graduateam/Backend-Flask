"""
비디오 처리 서비스
객체 감지 및 충돌 예측을 수행하는 핵심 서비스
"""
import numpy as np
import time
import threading
import cv2
import queue
from flask import current_app
import config
from app.analyzers.object_detection import ObjectDetector
# 새로운 충돌 예측기 import
from app.analyzers.collision_prediction import CollisionPredictor
from app.utils.coord_utils import CoordinateTransformer
from app.services.streaming import video_stream
from app.services.map_service import MapDataService
from app.utils.logger import setup_logger

# 로거 설정
logger = setup_logger(__name__)

class VideoProcessor:
    """비디오 처리 및 객체 감지/추적 관리 클래스"""
    def __init__(self):
        # 상태 변수 초기화
        self.cap = None
        self.processing_thread = None
        self.socket_thread = None
        self.is_processing = False
        self.is_socket_running = False
        self.detected_objects = []
        self.collision_risk_ids = set()  # 충돌 위험이 있는 객체 ID 저장

        # 예측 결과 저장을 위한 변수
        self.prediction_result = None
        self.risk_summary = {}  # 위험도 요약 정보

        # 지연 초기화를 위한 변수 설정
        self.detector = None
        self.predictor = None  # 이제 UpgradedCollisionPredictor 사용
        self.transformer = None
        self.map_service = None
        self._is_initialized = False

        # 카메라 소스 관리
        self.current_source = config.DEFAULT_CAMERA_SOURCE
        self.camera_frames = {}  # 카메라 ID별 최신 프레임 저장 (읽기 전용)
        self.camera_locks = {}   # 카메라 ID별 스레드 락 (frame storage만 사용)
        
        # 이중 버퍼링 시스템 - YOLO 처리용 별도 버퍼
        self.processing_frames = {}  # YOLO 처리용 프레임 버퍼
        self.frame_queue = queue.Queue(maxsize=5)  # 비동기 YOLO 처리용 큐
        self.yolo_thread = None  # 별도 YOLO 처리 스레드
        self.yolo_running = False

        # 각 카메라에 대한 락 초기화
        for camera_id in config.CAMERA_SOURCES:
            if camera_id != "file":  # 파일 소스는 프레임 저장 불필요
                self.camera_locks[camera_id] = threading.Lock()
                self.camera_frames[camera_id] = None

    def initialize_models(self):
        """모델 초기화 - 충돌 예측기 사용"""
        if self._is_initialized:
            return True

        try:
            logger.info("객체 감지기 초기화 중...")
            self.detector = ObjectDetector(
                model_path=config.MODEL_PATH,
                image_points=config.IMAGE_POINTS,
                world_points=config.WORLD_POINTS
            )
            logger.info("객체 감지기 초기화 완료!")

            logger.info("업그레이드된 충돌 예측기 초기화 중...")
            # 새로운 충돌 예측기 사용 (위험도 임계값 설정 가능)
            self.predictor = CollisionPredictor(
                car_length=config.CAR_LENGTH,
                car_width=config.CAR_WIDTH,
                ttc_threshold=config.TTC_THRESHOLD,
                risk_threshold=getattr(config, 'RISK_THRESHOLD', 60.0)  # 기본값 60점
            )
            logger.info("업그레이드된 충돌 예측기 초기화 완료!")

            # 좌표 변환기 초기화
            self.transformer = CoordinateTransformer(
                image_points=config.IMAGE_POINTS,
                world_points=config.WORLD_POINTS
            )

            # 지도 서비스 초기화
            self.map_service = MapDataService(self.transformer)

            self._is_initialized = True
            return True

        except Exception as e:
            logger.error(f"초기화 오류: {str(e)}")
            raise

    def set_camera_source(self, source_id):
        """카메라 소스 변경"""
        if source_id not in config.CAMERA_SOURCES:
            logger.error(f"유효하지 않은 카메라 소스: {source_id}")
            return False

        self.current_source = source_id
        logger.info(f"비디오 소스를 '{config.CAMERA_NAMES.get(source_id, source_id)}'로 변경")
        return True

    def set_camera_frame(self, camera_id, frame):
        """특정 카메라에서 받은 최신 프레임 설정 - 이중 버퍼링으로 락 분리"""
        if camera_id in self.camera_locks and frame is not None:
            # 1. 빠른 프레임 저장 (라즈베리파이 응답용)
            with self.camera_locks[camera_id]:
                self.camera_frames[camera_id] = frame.copy()
            
            # 2. YOLO 처리용 비동기 큐에 추가 (락 없음)
            try:
                frame_data = {
                    'camera_id': camera_id,
                    'frame': frame.copy(),
                    'timestamp': time.time()
                }
                self.frame_queue.put_nowait(frame_data)
            except queue.Full:
                # 큐가 가득 차면 가장 오래된 프레임 제거 후 추가
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(frame_data)
                except queue.Empty:
                    pass
            
            return True
        return False

    def get_camera_frame(self, camera_id):
        """특정 카메라에서 최신 프레임 가져오기"""
        if camera_id in self.camera_locks:
            with self.camera_locks[camera_id]:
                if self.camera_frames[camera_id] is not None:
                    return self.camera_frames[camera_id].copy()
        return None

    def start_processing(self):
        """비디오 처리 시작"""
        if self.is_processing:
            return {'success': False, 'message': '이미 처리 중입니다.'}

        # 모델 초기화 확인
        if not self._is_initialized:
            self.initialize_models()

        try:
            # 비디오 처리 스레드 시작
            self.is_processing = True

            # 현재 앱 인스턴스 캡처
            app = current_app._get_current_object()

            # 앱 컨텍스트와 함께 스레드 실행
            self.processing_thread = threading.Thread(
                target=self._process_video_with_app_context,
                args=(app,)
            )
            self.processing_thread.daemon = True
            self.processing_thread.start()

            # 소켓 업데이트 스레드 시작
            from app.socket.events import start_socket_update_thread
            self.socket_thread = start_socket_update_thread(app)
            
            # YOLO 처리를 위한 별도 스레드 시작
            self.yolo_running = True
            self.yolo_thread = threading.Thread(
                target=self._yolo_processor_with_app_context,
                args=(app,)
            )
            self.yolo_thread.daemon = True
            self.yolo_thread.start()

            logger.info(f"비디오 처리, 소켓 업데이트, YOLO 처리 스레드 시작됨 (소스: {self.current_source})")
            return {'success': True, 'message': f'비디오 처리가 시작되었습니다. (소스: {config.CAMERA_NAMES.get(self.current_source, self.current_source)})'}

        except Exception as e:
            self.is_processing = False
            error_msg = f"처리 시작 오류: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}

    def _yolo_processor_with_app_context(self, app):
        """앱 컨텍스트를 포함한 YOLO 처리 래퍼"""
        with app.app_context():
            self.yolo_processor()

    def yolo_processor(self):
        """별도 스레드에서 YOLO 처리 수행 - 락 분리로 300ms 지연 해결"""
        logger.info("YOLO 비동기 처리 스레드 시작")
        
        while self.yolo_running:
            try:
                # 큐에서 프레임 가져오기 (최대 0.1초 대기)
                frame_data = self.frame_queue.get(timeout=0.1)
                
                camera_id = frame_data['camera_id']
                frame = frame_data['frame']
                
                # 현재 활성화된 카메라만 처리
                if camera_id != self.current_source:
                    continue
                
                # YOLO 객체 감지 수행 (락 없이)
                detected_objects = self.detector.detect_objects(frame)
                
                # 충돌 예측 수행
                prediction_result = None
                if detected_objects:
                    prediction_result = self.predictor.update_from_detection(detected_objects)
                
                # 결과를 thread-safe하게 업데이트
                self.detected_objects = detected_objects
                self.prediction_result = prediction_result
                
                if prediction_result:
                    # 충돌 위험 객체 ID 업데이트
                    self.collision_risk_ids.clear()
                    for (id1, id2) in prediction_result['collisions'].keys():
                        self.collision_risk_ids.add(id1)
                        self.collision_risk_ids.add(id2)
                    
                    # 위험도 요약 정보 업데이트
                    self.risk_summary = self.predictor.get_risk_summary()
                
                # 처리된 프레임을 별도 버퍼에 저장 (디스플레이용)
                self.processing_frames[camera_id] = frame.copy()
                
            except queue.Empty:
                # 큐가 비어있으면 계속 대기
                continue
            except Exception as e:
                logger.error(f"YOLO 처리 오류: {str(e)}")
                time.sleep(0.1)
        
        logger.info("YOLO 비동기 처리 스레드 종료")

    def stop_processing(self):
        """비디오 처리 중지"""
        if not self.is_processing and not self.is_socket_running:
            return {'success': False, 'message': '처리 중인 비디오가 없습니다.'}

        # 처리 플래그 해제
        self.is_processing = False
        self.is_socket_running = False
        self.yolo_running = False

        # 비디오 캡처 해제
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        logger.info("비디오 처리 중지됨")
        return {'success': True, 'message': '비디오 처리가 중지되었습니다.'}

    def get_status(self):
        """현재 처리 상태 정보 반환"""
        obj_count = len(self.detected_objects) if self.detected_objects else 0
        collision_count = len(self.predictor.collision_warnings) if hasattr(self.predictor, 'collision_warnings') and self._is_initialized else 0

        # 현재 소스 이름 가져오기
        source_name = config.CAMERA_NAMES.get(self.current_source, self.current_source)

        # 위험도 요약 정보
        risk_info = {}
        if self._is_initialized and hasattr(self.predictor, 'get_risk_summary'):
            risk_info = self.predictor.get_risk_summary()

        return {
            'is_processing': self.is_processing,
            'object_count': obj_count,
            'collision_count': collision_count,
            'current_source': self.current_source,
            'source_name': source_name,
            'source_path': config.CAMERA_SOURCES.get(self.current_source),
            'risk_summary': risk_info  # 위험도 요약 정보
        }

    def _process_video_with_app_context(self, app):
        """앱 컨텍스트를 적용하여 비디오 처리"""
        with app.app_context():
            self._process_video()

    def _process_video(self, frame_skip=0):
        """비디오 소스에서 프레임을 읽고 객체 감지 수행"""
        logger.info(f"비디오 처리 시작: 소스 = {self.current_source}")

        try:
            # 소스에 따른 비디오 캡처 설정
            self.cap = None
            if self.current_source == "file":
                file_path = config.CAMERA_SOURCES["file"]
                self.cap = cv2.VideoCapture(file_path)
                if not self.cap.isOpened():
                    logger.error(f"오류: 비디오 파일 '{file_path}'을 열 수 없습니다.")
                    self.is_processing = False
                    return

                fps = self.cap.get(cv2.CAP_PROP_FPS)
                width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                logger.info(f"비디오 정보: {width}x{height}, {fps}fps, 총 {frame_count}프레임")

            elif self.current_source == "camera_0":
                logger.info(f"[CAMERA-0] 외부 API로부터 프레임을 수신하는 '{config.CAMERA_NAMES.get(self.current_source)}' 모드")
                logger.info(f"[CAMERA-0] 현재 프레임 상태: {self.camera_frames.get('camera_0') is not None}")

            elif self.current_source.startswith("camera_"):
                camera_source = config.CAMERA_SOURCES[self.current_source]

                if isinstance(camera_source, int):
                    self.cap = cv2.VideoCapture(camera_source)
                    logger.info(f"로컬 카메라 {camera_source} 연결")
                else:
                    self.cap = cv2.VideoCapture(camera_source)
                    logger.info(f"스트림 카메라 연결: {camera_source}")

                if not self.cap.isOpened():
                    logger.error(f"오류: 카메라 소스 '{camera_source}'를 열 수 없습니다.")
                    self.is_processing = False
                    return

            # 비디오 처리 시작
            frames_processed = 0

            while self.is_processing:
                # 프레임 획득
                frame = None

                if self.current_source == "file":
                    ret, frame = self.cap.read()
                    if not ret:
                        logger.info("비디오 끝에 도달, 처음부터 다시 시작")
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        time.sleep(0.1)
                        continue

                elif self.current_source.startswith("camera_"):
                    frame = self.get_camera_frame(self.current_source)
                    if frame is None:
                        empty_frame = np.zeros((360, 480, 3), dtype=np.uint8)
                        cv2.putText(
                            empty_frame,
                            f"{config.CAMERA_NAMES.get(self.current_source, self.current_source)} - 프레임 대기 중",
                            (50, 240),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (255, 255, 255),
                            2
                        )
                        video_stream.update(empty_frame)
                        time.sleep(0.1)
                        continue

                if frame is None:
                    logger.warning("프레임을 가져올 수 없습니다.")
                    time.sleep(0.1)
                    continue

                frames_processed += 1

                # 프레임 번호에 따른 처리 결정
                should_process = (frame_skip == 0) or (frames_processed % (frame_skip + 1) == 1)

                if not should_process:
                    simple_display = frame.copy()
                    # 🚫 시간 표시 제거
                    # cv2.putText(
                    #     simple_display,
                    #     f"{time.strftime('%H:%M:%S')}",
                    #     (10, 30),
                    #     cv2.FONT_HERSHEY_SIMPLEX,
                    #     0.7,
                    #     (255, 255, 255),
                    #     2
                    # )
                    video_stream.update(simple_display)
                    continue

                try:
                    # YOLO 처리는 별도 스레드에서 비동기 처리됨 
                    # 여기서는 디스플레이용 프레임만 처리

                    # 바운딩 박스를 그릴 프레임 복사
                    display_frame = frame.copy()

                    # 🚫 시간 표시 제거, 위험도 정보만 표시
                    # cv2.putText(
                    #     display_frame,
                    #     f"{time.strftime('%H:%M:%S')}",
                    #     (10, 30),
                    #     cv2.FONT_HERSHEY_SIMPLEX,
                    #     0.7,
                    #     (255, 255, 255),
                    #     2
                    # )

                    # 위험도 요약 표시
                    if hasattr(self, 'risk_summary') and self.risk_summary:
                        risk_status = self.risk_summary.get('status', 'safe')
                        max_risk = self.risk_summary.get('max_risk', 0)
                        warning_count = self.risk_summary.get('warning_count', 0)

                        # 위험도에 따른 색상 설정
                        if risk_status == 'critical':
                            risk_color = (0, 0, 255)  # 빨간색
                        elif risk_status == 'high':
                            risk_color = (0, 100, 255)  # 주황색
                        elif risk_status == 'medium':
                            risk_color = (0, 255, 255)  # 노란색
                        else:
                            risk_color = (0, 255, 0)  # 초록색

                        cv2.putText(
                            display_frame,
                            f"Risk: {risk_status.upper()} ({max_risk:.1f}%)",
                            (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            risk_color,
                            2
                        )

                        if warning_count > 0:
                            cv2.putText(
                                display_frame,
                                f"Warnings: {warning_count}",
                                (10, 90),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                risk_color,
                                2
                            )

                    # 바운딩 박스 그리기 - 위험도에 따른 색상
                    for obj in self.detected_objects:
                        bbox = obj['bbox']
                        obj_id = obj['id']

                        # 충돌 위험 여부 및 위험도에 따른 색상 결정
                        if obj_id in self.collision_risk_ids:
                            # 해당 객체가 관련된 위험도 찾기
                            max_risk_for_obj = 0
                            for (id1, id2), risk_score in self.prediction_result['collisions'].items():
                                if obj_id == id1 or obj_id == id2:
                                    max_risk_for_obj = max(max_risk_for_obj, risk_score)

                            # 위험도에 따른 색상
                            if max_risk_for_obj >= 90:
                                color = (0, 0, 255)  # 빨간색 (치명적)
                                text_color = (0, 0, 255)
                                risk_text = f"CRITICAL ({max_risk_for_obj:.0f}%)"
                            elif max_risk_for_obj >= 70:
                                color = (0, 100, 255)  # 주황색 (높음)
                                text_color = (0, 100, 255)
                                risk_text = f"HIGH ({max_risk_for_obj:.0f}%)"
                            else:
                                color = (0, 255, 255)  # 노란색 (중간)
                                text_color = (0, 255, 255)
                                risk_text = f"MEDIUM ({max_risk_for_obj:.0f}%)"
                        else:
                            color = (0, 255, 0)  # 초록색 (안전)
                            text_color = (0, 255, 0)
                            risk_text = "SAFE"

                        # 사각형 그리기
                        cv2.rectangle(display_frame,
                                      (int(bbox[0]), int(bbox[1])),
                                      (int(bbox[2]), int(bbox[3])),
                                      color, 2)

                        # 객체 ID 및 위험도 표시
                        cv2.putText(
                            display_frame,
                            f"ID: {obj_id}",
                            (int(bbox[0]), int(bbox[1]) - 25),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            text_color,
                            2
                        )

                        cv2.putText(
                            display_frame,
                            risk_text,
                            (int(bbox[0]), int(bbox[1]) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.4,
                            text_color,
                            1
                        )

                    # 프레임 업데이트
                    video_stream.update(display_frame)

                except Exception as e:
                    logger.error(f"객체 감지 오류: {str(e)}")
                    # 오류 정보 표시
                    error_frame = frame.copy()
                    cv2.putText(
                        error_frame,
                        f"Error: {str(e)}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2
                    )
                    video_stream.update(error_frame)

                # 프레임 처리 속도 조절
                if self.current_source == "file":
                    time.sleep(0.03)  # ~30fps

        except Exception as e:
            logger.error(f"비디오 처리 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            # 비디오 소스 닫기
            if self.cap is not None:
                self.cap.release()
                self.cap = None

            self.is_processing = False
            logger.info("비디오 처리 종료")

    def get_map_update_data(self):
        """지도 업데이트 데이터 요청"""
        if not self._is_initialized:
            return None

        return self.map_service.generate_map_data(
            self.detected_objects,
            self.predictor,
            video_stream,
            self.prediction_result  # 저장된 예측 결과 전달
        )

# VideoProcessor 인스턴스 생성
video_processor = VideoProcessor()