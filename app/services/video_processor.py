"""
비디오 처리 서비스
객체 감지 및 충돌 예측을 수행하는 핵심 서비스
"""
import time
import threading
import cv2
from flask import current_app
import config
from app.analyzers.object_detection import ObjectDetector
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

        # 지연 초기화를 위한 변수 설정
        self.detector = None
        self.predictor = None
        self.transformer = None
        self.map_service = None
        self._is_initialized = False

    def initialize_models(self):
        """모델 초기화 - 필요할 때만 한 번 실행"""
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

            logger.info("충돌 예측기 초기화 중...")
            self.predictor = CollisionPredictor(
                car_length=config.CAR_LENGTH,
                car_width=config.CAR_WIDTH,
                ttc_threshold=config.TTC_THRESHOLD
            )
            logger.info("충돌 예측기 초기화 완료!")

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

            logger.info("비디오 처리 및 소켓 업데이트 스레드 시작됨")
            return {'success': True, 'message': '비디오 처리가 시작되었습니다.'}

        except Exception as e:
            self.is_processing = False
            error_msg = f"처리 시작 오류: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}

    def stop_processing(self):
        """비디오 처리 중지"""
        if not self.is_processing and not self.is_socket_running:
            return {'success': False, 'message': '처리 중인 비디오가 없습니다.'}

        # 처리 플래그 해제
        self.is_processing = False
        self.is_socket_running = False

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

        return {
            'is_processing': self.is_processing,
            'object_count': obj_count,
            'collision_count': collision_count,
            'video_source': config.VIDEO_SOURCE
        }


    def _process_video_with_app_context(self, app):
        """앱 컨텍스트를 적용하여 비디오 처리"""
        with app.app_context():
            self._process_video()

    def _process_video(self, frame_skip=0):
        """비디오 소스에서 프레임을 읽고 객체 감지 수행"""
        logger.info(f"비디오 처리 시작: {config.VIDEO_SOURCE}")

        try:
            # 비디오 소스 열기
            self.cap = cv2.VideoCapture(config.VIDEO_SOURCE)
            if not self.cap.isOpened():
                logger.error(f"오류: 비디오 소스 '{config.VIDEO_SOURCE}'를 열 수 없습니다.")
                self.is_processing = False
                return

            # 비디오 속성 출력
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            logger.info(f"비디오 정보: {width}x{height}, {fps}fps, 총 {frame_count}프레임")

            # 비디오 처리 시작
            frames_processed = 0

            while self.is_processing:
                # 프레임 읽기
                ret, frame = self.cap.read()

                # 프레임 읽기 실패 처리
                if not ret:
                    logger.info("비디오 끝에 도달 또는 프레임 읽기 실패, 처음부터 다시 시작")
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.1)
                    continue

                frames_processed += 1

                # 프레임 번호에 따른 처리 결정
                should_process = (frame_skip == 0) or (frames_processed % (frame_skip + 1) == 1)

                if not should_process:
                    # 처리는 하지 않아도 화면에는 표시
                    simple_display = frame.copy()
                    cv2.putText(
                        simple_display,
                        f"Frame: {frames_processed} | Skip | {time.strftime('%H:%M:%S')}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2
                    )
                    video_stream.update(simple_display)
                    continue

                try:
                    # 객체 감지 수행
                    self.detected_objects = self.detector.detect_objects(frame)

                    # 충돌 위험 객체 확인을 위해 예측 수행
                    if self.detected_objects:
                        self.prediction_result = self.predictor.update_from_detection(self.detected_objects)
                        # 충돌 위험 객체 ID 업데이트
                        self.collision_risk_ids.clear()
                        for (id1, id2) in self.prediction_result['collisions'].keys():
                            self.collision_risk_ids.add(id1)
                            self.collision_risk_ids.add(id2)

                    # 바운딩 박스를 그릴 프레임 복사
                    display_frame = frame.copy()

                    # 바운딩 박스 그리기
                    for obj in self.detected_objects:
                        bbox = obj['bbox']
                        obj_id = obj['id']

                        # 충돌 위험 여부 확인
                        if obj_id in self.collision_risk_ids:
                            color = (0, 0, 255)  # 빨간색 (BGR)
                            text_color = (0, 0, 255)
                        else:
                            color = (0, 255, 0)  # 초록색 (BGR)
                            text_color = (0, 255, 0)

                        # 사각형 그리기
                        cv2.rectangle(display_frame,
                                      (int(bbox[0]), int(bbox[1])),
                                      (int(bbox[2]), int(bbox[3])),
                                      color, 2)

                        # 객체 ID 표시
                        cv2.putText(
                            display_frame,
                            f"ID: {obj_id}" + (" (danger)" if obj_id in self.collision_risk_ids else ""),
                            (int(bbox[0]), int(bbox[1]) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            text_color,
                            2
                        )

                    # 프레임 업데이트
                    video_stream.update(display_frame)

                except Exception as e:
                    logger.error(f"객체 감지 오류: {str(e)}")
                    video_stream.update(frame)  # 오류 발생 시 기본 프레임 표시

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