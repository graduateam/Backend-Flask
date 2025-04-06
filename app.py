"""
Flask 애플리케이션 실행 스크립트
"""
from app import create_app, socketio
import os

if __name__ == '__main__':
    # 환경 변수에서 호스트와 포트 가져오기 (기본값 설정)
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # 애플리케이션 생성
    app = create_app()

    # Flask 앱 실행 (Socket.IO 통합)
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)