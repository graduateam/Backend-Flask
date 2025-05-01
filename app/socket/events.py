"""
Socket.IO 이벤트 핸들러
"""
from flask import request, current_app
from flask_socketio import emit
from app import socketio
from app.services.streaming import VideoStreamManager
from app.services.video_processor import video_processor
from app.utils.logger import setup_logger
import threading
import time

# 로거 설정
logger = setup_logger(__name__)

# 비디오 스트림 매니저 인스턴스 생성
stream_manager = VideoStreamManager()

@socketio.on('connect')
def handle_connect():
    """클라이언트 연결 이벤트 처리"""
    logger.info('클라이언트가 연결되었습니다.')
    emit('connect_response', {'status': 'connected'})

@socketio.on('start_stream')
def handle_start_stream(data):
    """비디오 스트리밍 시작 요청 처리"""
    # 클라이언트 등록
    stream_manager.add_client(request.sid)
    logger.info(f"클라이언트 {request.sid} 스트리밍 시작 요청")

    # 품질 설정
    if 'quality' in data:
        stream_manager.set_quality(data['quality'])

    # 스트리밍 시작
    stream_manager.start_streaming()

@socketio.on('change_quality')
def handle_change_quality(data):
    """비디오 스트림 품질 변경 요청 처리"""
    if 'quality' in data:
        stream_manager.set_quality(data['quality'])
        logger.info(f"스트림 품질 변경: {data['quality']}")

@socketio.on('disconnect')
def handle_disconnect():
    """클라이언트 연결 종료 처리"""
    stream_manager.remove_client(request.sid)
    logger.info(f"클라이언트 {request.sid} 연결 종료")

# 실시간 지도 데이터 업데이트 소켓 스레드 시작
def start_socket_update_thread(app=None):
    """Socket.IO 업데이트 스레드 시작"""
    if app is None:
        app = current_app._get_current_object()

    thread = threading.Thread(target=socket_update_thread, args=(app,))
    thread.daemon = True
    thread.start()
    logger.info("Socket.IO 업데이트 스레드 시작됨")
    return thread

# Socket.IO 업데이트 스레드
def socket_update_thread(app):
    """주기적으로 웹 소켓을 통해 객체 및 충돌 정보 전송"""
    with app.app_context():
        logger.info("소켓 업데이트 스레드 시작")

        # 플래그 설정
        video_processor.is_socket_running = True

        # 마지막 전송 시간 기록
        last_update_time = time.time()
        update_count = 0
        success_count = 0
        error_count = 0

        logger.info("실시간 맵 데이터 업데이트 비활성화됨 (요구사항 1)")

        # 오류 카운터 및 최대 재시도 횟수
        error_count = 0
        max_retries = 5
        retry_delay = 1.0  # 초기 재시도 대기 시간 (초)

        while video_processor.is_socket_running:
            # 실시간 업데이트 비활성화
            time.sleep(1.0)  # 스레드 유지만 하고 실제 데이터 전송은 하지 않음

        logger.info("소켓 업데이트 스레드 종료")