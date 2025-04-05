"""
비디오 스트리밍 서비스
"""
import time
import threading
import cv2
import numpy as np
import base64
from app.utils.logger import setup_logger

# 로거 설정
logger = setup_logger(__name__)

class VideoStream:
    """비디오 스트림 담당 클래스"""
    def __init__(self):
        self.frame = None
        self.lock = threading.Lock()
        self.status = "ready"

    def update(self, frame):
        """스레드 안전하게 프레임 업데이트"""
        with self.lock:
            self.frame = frame.copy() if frame is not None else None
            self.status = "updated"

    def get_frame(self):
        """현재 프레임 반환"""
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return None

# 비디오 스트림 인스턴스 생성
video_stream = VideoStream()

def generate_frames():
    """비디오 스트림을 MJPEG 형식으로 생성"""
    while True:
        try:
            # video_stream에서 프레임 가져오기
            frame = video_stream.get_frame()

            if frame is not None:
                # JPEG 형식으로 인코딩
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    continue

                # MJPEG 스트림 형식으로 변환
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                # 프레임이 없으면 빈 프레임 생성
                empty_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(
                    empty_frame,
                    "비디오가 준비 중입니다...",
                    (50, 240),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 255, 255),
                    2
                )
                ret, buffer = cv2.imencode('.jpg', empty_frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            # 스트림 업데이트 간격 (약 30 FPS)
            time.sleep(1 / 30)

        except Exception as e:
            logger.error(f"프레임 생성 오류: {str(e)}")
            time.sleep(0.1)


class VideoStreamManager:
    """WebSocket을 통한 비디오 스트리밍 관리 클래스"""
    def __init__(self):
        self.clients = set()
        self.quality = 'high'  # 'high' 또는 'low'
        self.stream_thread = None
        self.is_streaming = False

    def add_client(self, client_id):
        """클라이언트 등록"""
        self.clients.add(client_id)
        logger.info(f"클라이언트 {client_id} 등록됨, 현재 클라이언트 수: {len(self.clients)}")

    def remove_client(self, client_id):
        """클라이언트 제거"""
        if client_id in self.clients:
            self.clients.remove(client_id)
            logger.info(f"클라이언트 {client_id} 제거됨, 현재 클라이언트 수: {len(self.clients)}")

        # 모든 클라이언트 연결 종료 시 스트리밍 중지
        if len(self.clients) == 0:
            self.stop_streaming()

    def set_quality(self, quality):
        """스트림 품질 설정"""
        if quality in ['high', 'low']:
            self.quality = quality
            logger.info(f"스트림 품질 설정: {quality}")

    def start_streaming(self):
        """스트리밍 시작"""
        if self.stream_thread is None or not self.stream_thread.is_alive():
            self.is_streaming = True
            self.stream_thread = threading.Thread(target=self._stream_video_frames)
            self.stream_thread.daemon = True
            self.stream_thread.start()
            logger.info("WebSocket 비디오 스트리밍 스레드 시작")

    def stop_streaming(self):
        """스트리밍 중지"""
        self.is_streaming = False
        logger.info("WebSocket 비디오 스트리밍 중지")

    def _stream_video_frames(self):
        """WebSocket을 통해 비디오 프레임 스트리밍"""
        from app import socketio  # 여기서 임포트하여 순환 참조 방지

        fps_target = 30  # 목표 FPS
        last_frame_time = time.time()

        while self.is_streaming and len(self.clients) > 0:
            try:
                # 현재 시간
                current_time = time.time()
                elapsed = current_time - last_frame_time

                # FPS 제어
                if elapsed < 1.0 / fps_target:
                    time.sleep(0.001)  # CPU 사용률 감소
                    continue

                last_frame_time = current_time

                # 비디오 스트림에서 프레임 가져오기
                frame = video_stream.get_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue

                # 프레임 품질 조정
                if self.quality == 'low':
                    # 저화질: 크기 축소 및 JPEG 품질 낮춤
                    frame = cv2.resize(frame, (640, 360))
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
                else:
                    # 고화질: 원본 크기, 높은 JPEG 품질
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]

                # JPEG으로 인코딩
                _, buffer = cv2.imencode('.jpg', frame, encode_param)

                # Base64로 인코딩하여 WebSocket으로 전송
                frame_base64 = base64.b64encode(buffer).decode('utf-8')

                # 연결된 모든 클라이언트에 전송
                socketio.emit('video_frame', {'frame': frame_base64}, room=list(self.clients))

            except Exception as e:
                logger.error(f"비디오 스트리밍 오류: {str(e)}")
                time.sleep(0.1)

        logger.info("비디오 스트리밍 스레드 종료")