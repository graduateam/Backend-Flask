# 🔧 백엔드-프론트엔드 연결 완전 가이드

React Native 앱과 Flask 백엔드 연동을 위한 **실제 검증된** 설정 가이드입니다.

## 📋 사전 요구사항

### 필수 소프트웨어
- [ ] **Node.js** (18+): https://nodejs.org/
- [ ] **Python** (3.8+): https://python.org/downloads/
- [ ] **Android Studio** (Android 에뮬레이터용): https://developer.android.com/studio
- [ ] **Git**: https://git-scm.com/

### 프로젝트 구조 확인
```
workspace/
├── Backend-Flask/          # Flask 백엔드
│   ├── app/
│   ├── app.py
│   ├── requirements.txt
│   └── venv/ (생성됨)
└── smartroadreflector/     # React Native 앱
    ├── app/
    ├── package.json
    ├── .env.example
    └── .env (생성 필요)
```

---

## 🚀 백엔드 설정 (5분)

### 1단계: Flask 서버 설정
```bash
# 백엔드 디렉토리로 이동
cd Backend-Flask

# Python 가상환경 생성 (중요!)
python -m venv venv

# 가상환경 활성화
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# Flask 서버 실행
python app.py
```

### ✅ 백엔드 성공 확인
터미널에 다음 메시지 출력:
```
* Running on http://127.0.0.1:5000 (Press CTRL+C to quit)
* Running on http://0.0.0.0:5000 (Press CTRL+C to quit)
```

### 2단계: API 테스트 (선택사항)
새 터미널에서:
```bash
cd Backend-Flask
venv\Scripts\activate  # 가상환경 활성화
python test_api.py
```

**예상 결과**: `테스트 완료: 6/6 통과`

---

## 📱 프론트엔드 설정 (3분)

### 1단계: React Native 앱 설정
```bash
# 프론트엔드 디렉토리로 이동
cd smartroadreflector

# 의존성 설치
npm install
```

### 2단계: 환경변수 설정
```bash
# .env 파일 생성 (기존 .env.example 참고)
# Windows:
copy .env.example .env
# Mac/Linux:
cp .env.example .env
```

### 3단계: .env 파일 수정
**.env 파일 내용**:
```bash
# 네이버 지도 API 키 (실제 키로 변경)
EXPO_PUBLIC_NAVER_MAP_CLIENT_ID=your_actual_client_id_here
EXPO_PUBLIC_NAVER_MAP_CLIENT_SECRET=your_actual_client_secret_here

# API 모드 설정 (중요!)
EXPO_PUBLIC_API_MODE=api

# Android 에뮬레이터용 Flask 서버 URL (중요!)
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:5000
```

> **⚠️ 중요**: Android 에뮬레이터에서는 반드시 `10.0.2.2:5000`을 사용해야 합니다.

### 4단계: Android 에뮬레이터 실행
```bash
# Android Studio에서 AVD Manager 실행
# 또는 명령줄에서:
emulator -avd 에뮬레이터_이름
```

### 5단계: React Native 앱 실행
```bash
# Metro 서버 시작
npx expo start

# Android 에뮬레이터에 설치 (터미널에서 'a' 키 입력)
# 또는 직접 실행:
npx expo run:android
```

---

## ✅ 연결 성공 확인

### 1. Flask 서버 로그 확인
백엔드 터미널에서 다음과 같은 로그 확인:
```
INFO - 위치 업데이트 요청 처리 완료 (#1): 디바이스=mobile_device_xxx, 차량=5대, 보행자=3명, 충돌경고=없음
INFO - 위치 업데이트 요청 처리 완료 (#2): 디바이스=mobile_device_xxx, 차량=5대, 보행자=3명, 충돌경고=없음
```

### 2. React Native 앱 화면 확인
- [ ] **앱 정상 실행**: 스플래시 → 메인 화면
- [ ] **지도 표시**: 네이버 지도 정상 로드
- [ ] **위치 권한**: 위치 권한 요청 및 허용
- [ ] **차량 마커**: 지도에 5대의 파란색 차량 마커 표시
- [ ] **차량 이동**: 시간이 지나면서 마커들이 움직임
- [ ] **객체 목록**: 좌측 하단에 차량/보행자 정보 표시
- [ ] **충돌 경고**: 잠시 기다리면 빨간색 경고창 표시 (7번째마다)

### 3. 실시간 데이터 흐름 확인
- **1초마다** 위치 정보 전송
- **실시간** 차량 위치 업데이트
- **7번째 요청마다** 충돌 경고 발생

---

## 🐛 문제 해결

### 백엔드 문제

#### Flask 서버 실행 안됨
```bash
# 포트 충돌 확인
netstat -ano | findstr :5000  # Windows
lsof -i :5000                 # Mac/Linux

# 가상환경 재생성
deactivate
rmdir /s venv  # Windows
rm -rf venv    # Mac/Linux
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

#### 의존성 설치 실패
```bash
# pip 업그레이드
python -m pip install --upgrade pip

# PyTorch 문제 시 CPU 버전 설치
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### 프론트엔드 문제

#### Metro 서버 연결 실패
```bash
# 캐시 클리어
npx expo start --clear

# node_modules 재설치
rm -rf node_modules package-lock.json
npm install
```

#### API 연결 실패
1. **.env 파일 확인**:
   ```bash
   EXPO_PUBLIC_API_MODE=api
   EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:5000
   ```

2. **네트워크 테스트**:
   ```bash
   # Android 에뮬레이터 내에서 브라우저로 확인
   http://10.0.2.2:5000
   ```

3. **다른 에뮬레이터/기기별 URL**:
   - **iOS 시뮬레이터**: `http://localhost:5000`
   - **실제 기기**: `http://192.168.x.x:5000` (실제 IP)
   - **웹 브라우저**: `http://localhost:5000`

#### 네이버 지도 표시 안됨
```bash
# 실제 네이버 지도 API 키 발급 필요
# https://www.ncloud.com/product/applicationService/maps
# .env 파일에 실제 키 입력
```

---

## ⚡ 빠른 시작 가이드 (5분)

### 🚀 백엔드 (2분)
```bash
cd Backend-Flask
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
python app.py
```

### 📱 프론트엔드 (3분)
```bash
cd smartroadreflector
npm install

# .env 파일 생성 및 수정
echo "EXPO_PUBLIC_API_MODE=api" > .env
echo "EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:5000" >> .env
echo "EXPO_PUBLIC_NAVER_MAP_CLIENT_ID=your_key_here" >> .env

npx expo start
# 터미널에서 'a' 키 입력하여 Android 에뮬레이터에 설치
```

### ✅ 성공 확인 (30초)
- Flask 터미널: `Running on http://0.0.0.0:5000` 메시지
- React Native 앱: 지도에 5대 차량 표시
- 실시간 로그: `위치 업데이트 요청 처리 완료` 메시지

---

## 🎯 다음 단계

### 개발 환경 확장
1. **실제 기기 테스트**: 같은 Wi-Fi의 다른 기기에서 접속
2. **네이버 지도 API**: 실제 API 키 발급 및 적용
3. **실제 로직 연동**: Mock 데이터를 실제 YOLO 결과로 교체

### 실제 배포 준비
1. **네트워크 설정**: 고정 IP 또는 도메인 설정
2. **보안 강화**: CORS 설정 제한, HTTPS 적용
3. **성능 최적화**: 데이터 압축, 캐싱 적용

---

## 📞 추가 지원

### 디버깅 도구
- **Flask 로그**: 터미널에서 실시간 확인
- **React Native 디버거**: Metro 터미널에서 `j` 키
- **네트워크 확인**: `curl http://10.0.2.2:5000/api/status`

### 개발 팁
1. **터미널 2개 사용**: 백엔드용, 프론트엔드용
2. **가상환경 활성화**: 백엔드 작업 시 항상 확인
3. **로그 모니터링**: 연결 상태 실시간 확인

---

## 🎉 완료!

**총 소요시간**: 약 8분 ⏱️

성공적으로 연결되면:
- ✅ **실시간 연동**: 1초마다 데이터 송수신
- ✅ **지도 시각화**: 5대 차량이 실시간으로 이동
- ✅ **충돌 경고**: 7번째마다 발생하는 테스트 가능한 경고
- ✅ **확장 준비**: 실제 로직으로 교체 가능한 구조

이제 기본적인 프론트-백엔드 연동이 완료되었습니다! 🚀