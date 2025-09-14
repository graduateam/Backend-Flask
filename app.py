"""
Flask 애플리케이션 실행 스크립트 - 모바일 API 최적화 모드
"""
from app import create_app
import os

if __name__ == '__main__':
    # 환경 변수에서 호스트와 포트 가져오기 (기본값 설정)
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    enable_web = os.environ.get('ENABLE_WEB_INTERFACE', 'false').lower() in ('true', '1', 't', 'yes')

    # 애플리케이션 생성
    app = create_app()

    # 🚀 모드별 서버 시작 메시지
    print("=" * 60)
    if enable_web:
        print("🌐 개발/디버그 모드로 서버 시작")
        print(f"📱 모바일 API: http://{host}:{port}/api/mobile/")
        print(f"🌐 웹 인터페이스: http://{host}:{port}/")
        print(f"🎥 비디오 스트림: http://{host}:{port}/video_feed")
        print("⚠️  성능 주의: 웹 인터페이스로 인한 성능 저하 가능")
    else:
        print("🚀 모바일 API 전용 모드로 서버 시작 (최고 성능)")
        print(f"📱 모바일 API: http://{host}:{port}/api/mobile/")
        print("🚫 웹 인터페이스 비활성화")
        print("💡 비디오 확인이 필요하다면:")
        print("   ENABLE_WEB_INTERFACE=true python app.py")
    print("=" * 60)
    
    app.run(host=host, port=port, debug=debug, threaded=True)