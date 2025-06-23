#!/bin/bash

echo "🚀 충돌 예측 백엔드 서버 시작"
echo "================================"

# 환경 변수 로드
if [ -f ".env.production" ]; then
    echo "📄 프로덕션 환경 변수 로드 중..."
    export $(cat .env.production | grep -v '#' | xargs)
fi

# 가상환경 활성화 (있는 경우)
if [ -d "venv" ]; then
    echo "🐍 가상환경 활성화 중..."
    source venv/bin/activate
fi

# 의존성 확인
echo "📦 의존성 확인 중..."
pip install -r requirements.txt

# 포트 확인
echo "🔍 포트 $FLASK_PORT 사용 가능 여부 확인..."
if lsof -Pi :$FLASK_PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  포트 $FLASK_PORT가 이미 사용 중입니다."
    echo "   기존 프로세스를 종료하거나 다른 포트를 사용하세요."
    exit 1
fi

# IP 주소 정보 출력
echo "🌐 서버 접속 정보:"
echo "   - 로컬 접속: http://localhost:$FLASK_PORT"
if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "your.public.ip.here" ]; then
    echo "   - 외부 접속: http://$PUBLIC_IP:$PUBLIC_PORT"
else
    echo "   - 외부 접속: PUBLIC_IP 환경변수를 설정하세요"
fi

echo ""
echo "🛡️  보안 알림:"
echo "   - 방화벽에서 포트 $FLASK_PORT를 허용했는지 확인하세요"
echo "   - 라우터에서 포트 포워딩을 설정했는지 확인하세요"
echo "   - 프로덕션 환경에서는 HTTPS 사용을 권장합니다"
echo ""

# 서버 시작
echo "🎯 서버 시작 중..."
python app.py