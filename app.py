"""
Flask 애플리케이션 실행 스크립트
"""
from app import create_app, socketio
import os
import threading
import time

def auto_start_processing(app):
    """서버 시작 후 자동으로 비디오 처리 시작"""
    # Flask 앱이 완전히 시작될 때까지 잠시 대기
    time.sleep(3)
    
    try:
        # Flask 애플리케이션 컨텍스트 설정
        with app.app_context():
            from app.services.video_processor import video_processor
            print("자동으로 비디오 처리를 시작합니다...")
            
            # 모델 초기화
            video_processor.initialize_models()
            
            # 처리 시작
            result = video_processor.start_processing()
            if result['success']:
                print(f"✅ 비디오 처리 자동 시작 성공: {result['message']}")
            else:
                print(f"❌ 비디오 처리 자동 시작 실패: {result['message']}")
                
    except Exception as e:
        print(f"❌ 자동 시작 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # 환경 변수에서 호스트와 포트 가져오기 (기본값 설정)
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # 애플리케이션 생성
    app = create_app()

    # 자동 시작 스레드 (app 객체를 인자로 전달)
    auto_start_thread = threading.Thread(target=auto_start_processing, args=(app,))
    auto_start_thread.daemon = True
    auto_start_thread.start()

    # Flask 앱 실행 (Socket.IO 통합)
    print("🚀 Flask 서버를 시작합니다...")
    print(f"📍 서버 주소: http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)