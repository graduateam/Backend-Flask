"""
Flask 애플리케이션 실행 스크립트 - 외부 접근 지원
"""
from app import create_app, socketio
import os

if __name__ == '__main__':
    # 환경 변수에서 호스트와 포트 가져오기
    host = os.environ.get('FLASK_HOST', '0.0.0.0')  # 모든 인터페이스에서 접근 허용
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # 애플리케이션 생성
    app = create_app()

    print(f"🚀 Flask 서버가 시작됩니다:")
    print(f"   - 호스트: {host}")
    print(f"   - 포트: {port}")
    print(f"   - 디버그 모드: {debug}")
    print(f"   - 외부 접근: {'허용' if host == '0.0.0.0' else '차단'}")
    print(f"")
    print(f"📡 접근 가능한 URL:")
    print(f"   - 로컬: http://localhost:{port}")
    print(f"   - 내부 네트워크: http://[내부IP]:{port}")
    print(f"   - 외부 접근: http://[공인IP]:{port} (포트 포워딩 필요)")
    print(f"")
    print(f"⚠️  보안 주의사항:")
    print(f"   - 공인 IP로 서비스할 경우 방화벽 설정을 확인하세요")
    print(f"   - 필요시 HTTPS 적용을 고려하세요")
    print(f"")

    # Flask 앱 실행 (Socket.IO 통합)
    socketio.run(
        app, 
        host=host, 
        port=port, 
        debug=debug, 
        allow_unsafe_werkzeug=True,
        # 외부 접근 시 추가 보안 설정
        use_reloader=debug,  # 프로덕션에서는 리로더 비활성화
        log_output=True
    )