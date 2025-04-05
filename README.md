# 웹 기반 실시간 차량 충돌 예측 시스템 (Backend-Flask)
###  _( Prototype )_ 

## 목차
1. [프로젝트 소개](#프로젝트-소개)
2. [프로젝트 구조](#프로젝트-구조)
3. [파일 기능 설명](#파일-기능-설명)
4. [핵심 알고리즘 분석](#핵심-알고리즘-분석)
5. [데이터 흐름](#데이터-흐름)
6. [시스템 설치 및 실행](#시스템-설치-및-실행)
7. [사용자 인터페이스 가이드](#사용자-인터페이스-가이드)
8. [주요 기능 사용법](#주요-기능-사용법)
9. [인터페이스 요소 설명](#인터페이스-요소-설명)
10. [문제 해결](#문제-해결)

## 프로젝트 소개

차량 충돌 예측 시스템은 YOLO 객체 탐지와 벡터 기반 충돌 예측 알고리즘을 결합하여 실시간으로 영상에서 차량을 감지하고 잠재적인 충돌을 예측합니다. 이 시스템은 Socket.IO를 활용한 실시간 통신, 그리고 네이버 지도 API를 통한 지리적 시각화를 제공합니다.

주요 기능:
- 비디오 소스에서 실시간 객체 감지 및 추적
- 벡터 기반 충돌 예측 (TTC: Time-to-Collision)
- 실시간 웹 인터페이스를 통한 시각화
- 카메라 피드 및 지도 실시간 동기화

## 프로젝트 구조

```
Backend-Flask/
│
├── app.py                      # 앱 실행 진입점
├── config.py                   # 설정 파일
│
└── app/
    ├── __init__.py             # Flask 애플리케이션 초기화
    │
    ├── views/                  # HTML 렌더링
    │   ├── __init__.py
    │   └── main.py             # 웹 페이지 라우트
    │
    ├── apis/                   # JSON API 엔드포인트
    │   ├── __init__.py
    │   └── api.py              # 데이터 API 정의
    │
    ├── socket/                 # 웹소켓 통신
    │   ├── __init__.py
    │   └── events.py           # Socket.IO 이벤트 핸들러
    │
    ├── services/               # 비즈니스 로직
    │   ├── __init__.py
    │   ├── video_processor.py  # 비디오 처리 및 관리
    │   ├── streaming.py        # 스트리밍 서비스
    │   └── map_service.py      # 지도 데이터 처리 서비스
    │
    ├── analyzers/              # 핵심 분석 알고리즘
    │   ├── __init__.py
    │   ├── object_detection.py # 객체 탐지 모델
    │   └── collision_prediction.py # 충돌 예측 모델
    │
    ├── utils/                  # 유틸리티 함수
    │   ├── __init__.py
    │   ├── coord_utils.py      # 좌표 변환 유틸리티
    │   ├── map_utils.py        # 지도 데이터 유틸리티
    │   ├── geometry_utils.py   # 기하학 계산 유틸리티
    │   └── logger.py           # 로깅 설정 및 유틸리티
    │
    ├── static/                 # 정적 파일
    │   ├── css/
    │   ├── js/
    │   ├── videos/             # 테스트를 위한 비디오 파일 저장
    │   └── yolo_models/        # 모델 파일 저장
    │
    └── templates/              # HTML 템플릿
        └── index.html          # 메인 페이지
```

## 파일 기능 설명

### 최상위 디렉토리 파일

#### app.py
- **기능**: 플라스크 애플리케이션의 진입점
- 환경 변수에서 호스트, 포트, 디버그 모드 설정 로드
- 애플리케이션 생성 및 Socket.IO 서버 실행
- 애플리케이션 실행 시작점으로 사용됨

#### config.py
- **기능**: 전역 설정 정보 관리
- 지도 API 키 (네이버맵)
- 이미지-세계 좌표 변환 설정 (카메라 캘리브레이션)
- YOLO 모델 경로 및 비디오 소스 설정
- 차량 크기 및 충돌 임계값 설정

### 핵심 모듈 (app/ 디렉토리)

#### app/__init__.py
- **기능**: Flask 애플리케이션 초기화
- 애플리케이션 팩토리 패턴 구현
- Socket.IO, 블루프린트, 로거 초기화 및 등록
- 앱 생성 및 설정 로드

### 분석기 모듈 (app/analyzers/)

#### app/analyzers/__init__.py
- **기능**: 분석기 모듈 패키지 초기화
- 객체 탐지 및 충돌 예측 모듈 가져오기
- 공개 API 정의

#### app/analyzers/object_detection.py
- **기능**: YOLO 기반 객체 탐지 및 추적
- YOLO 모델을 사용해 비디오 프레임에서 차량 등 객체 감지
- 감지된 객체의 이미지 좌표를 실제 GPS 좌표로 변환
- 객체 ID 추적 및 관리
- 비디오 스트림 처리 및 콜백 호출

#### app/analyzers/collision_prediction.py
- **기능**: 벡터 기반 충돌 예측 알고리즘
- 객체 위치 이력 저장 및 속도/방향/가속도 계산
- 등가속도 운동 방정식 기반 미래 위치 예측
- 차량을 직사각형으로 모델링하여 교차 여부 검사
- 충돌 위험이 있는 객체 쌍 식별 및 충돌예상시간(TTC) 계산
- 비활성 객체 정리 및 객체 정보 제공

### API 모듈 (app/apis/)

#### app/apis/__init__.py
- **기능**: API 모듈 패키지 초기화
- API 블루프린트 가져오기 및 리스트 관리

#### app/apis/api.py
- **기능**: REST API 엔드포인트 정의
- 시스템 상태 정보 제공 `/api/status`
- 비디오 프레임 경계 좌표 제공 `/api/video-bounds`
- 처리 시작/중지 제어 `/api/start-processing`, `/api/stop-processing`
- 좌표 변환 및 에러 처리

### 서비스 모듈 (app/services/)

#### app/services/__init__.py
- **기능**: 서비스 모듈 패키지 초기화
- 비즈니스 로직 모듈들 가져오기 및 공개 API 정의

#### app/services/video_processor.py
- **기능**: 핵심 비디오 처리 및 객체 감지/추적 관리
- 비디오 캡처 관리 및 프레임 처리
- 객체 감지기 및 충돌 예측기 초기화/관리
- 감지된 객체 시각화 및 바운딩 박스 그리기
- 처리 스레드 관리 및 앱 컨텍스트 유지
- 충돌 예측 결과 저장 및 상태 정보 제공

#### app/services/streaming.py
- **기능**: 비디오 스트리밍 서비스
- 웹 브라우저에 비디오 프레임 스트리밍 (MJPEG, WebSocket)
- 비디오 프레임 인코딩 및 품질 조정
- 클라이언트 연결 관리 및 스트리밍 제어
- 다중 클라이언트 지원 및 성능 최적화

#### app/services/map_service.py
- **기능**: 지도 데이터 처리 서비스
- GeoJSON 형식의 지도 데이터 생성
- 차량, 경로, 충돌 지점 정보 처리
- 비디오 프레임 경계의 지리적 좌표 계산
- 클라이언트에 전송할 데이터 패키지 생성

### 소켓 모듈 (app/socket/)

#### app/socket/__init__.py
- **기능**: 웹소켓 모듈 패키지 초기화
- Socket.IO 기능 등록 및 내보내기

#### app/socket/events.py
- **기능**: Socket.IO 이벤트 핸들러
- 클라이언트 연결/연결해제 처리
- 비디오 스트리밍 시작/품질변경 요청 처리
- 실시간 지도 데이터 업데이트 스레드 관리
- 오류 처리 및 재시도 로직 구현

### 유틸리티 모듈 (app/utils/)

#### app/utils/__init__.py
- **기능**: 유틸리티 모듈 패키지 초기화
- 공통 유틸리티 함수 가져오기 및 내보내기

#### app/utils/coord_utils.py
- **기능**: 좌표 변환 유틸리티
- 이미지 픽셀 좌표 ↔ GPS 좌표 변환 (Homography 행렬)
- 거리 계산 (Haversine 공식)
- 방위각 계산 및 오프셋 좌표 계산

#### app/utils/geometry_utils.py
- **기능**: 기하학 계산 유틸리티
- 차량 직사각형 모델링 및 모서리 좌표 계산
- 위경도 ↔ 카르테시안 좌표 변환
- 선분 교차 여부 검사 및 직사각형 충돌 검사

#### app/utils/logger.py
- **기능**: 로깅 유틸리티
- 중앙 집중식 로깅 설정 관리
- 로그 레벨 및 포맷 관리
- 각 모듈별 로거 생성 및 설정

#### app/utils/map_utils.py
- **기능**: 지도 관련 유틸리티
- 차량 GeoJSON 생성
- 충돌 지점 GeoJSON 생성
- 경로 GeoJSON 생성
- 통합 지도 데이터 패키지 생성

### 뷰 모듈 (app/views/)

#### app/views/__init__.py
- **기능**: 뷰 모듈 패키지 초기화
- 웹 페이지 렌더링 관련 블루프린트 관리

#### app/views/main.py
- **기능**: 웹 페이지 라우트 정의
- 메인 페이지 라우트 `/`
- 비디오 피드 스트림 라우트 `/video_feed`
- 템플릿 렌더링 및 콘텐츠 타입 설정

### 프론트엔드 파일

#### app/static/css/style.css
- **기능**: 웹 인터페이스 스타일링
- 레이아웃 구성 (좌우 패널 배치)
- 카드 디자인 및 비디오 피드 스타일
- 객체 목록 테이블 스타일
- 충돌 경고 알람 애니메이션 및 스타일
- 지도 컨트롤 및 마커 스타일
- 반응형 디자인 구현

#### app/static/js/index.js
- **기능**: 메인 페이지 인터랙션 관리
- Socket.IO 연결 및 이벤트 처리
- 객체 목록 및 충돌 경고 UI 업데이트
- 상태 표시 및 제어 버튼 동작 구현
- WebSocket 비디오 스트리밍 처리
- API 요청 처리 및 오류 핸들링

#### app/static/js/map.js
- **기능**: 지도 시각화 및 인터랙션
- 네이버 지도 초기화 및 설정
- 차량 마커 및 직사각형 표시 업데이트
- 충돌 마커 및 경로 라인 그리기
- 인포윈도우 생성 및 콘텐츠 관리
- 비디오 프레임 경계 표시 및 토글

#### app/templates/index.html
- **기능**: 메인 웹 인터페이스 템플릿
- 좌측 패널 (제어, 비디오 피드, 객체 목록)
- 우측 패널 (지도, 충돌 경고)
- 관련 스크립트 및 스타일시트 로드
- 네이버 맵 API 및 Socket.IO 통합

## 핵심 알고리즘 분석

### CollisionPredictor 클래스

`CollisionPredictor` 클래스는 차량 충돌 예측 시스템의 핵심 알고리즘으로, 위치 데이터를 수신하여 실시간으로 충돌 가능성을 예측합니다.

#### 데이터 구조
- 각 객체(차량)는 고유 ID로 식별되며 `self.objects` 딕셔너리에 저장됩니다.
- 객체별로 위치 이력, 속도, 방향, 가속도 등의 정보를 유지합니다.
- `deque` 자료구조를 사용하여 제한된 크기(`history_size`)의 이력 데이터를 관리합니다.

#### 알고리즘 및 로직

##### 1. 속도 및 방향 계산
```python
def _calculate_velocity_and_heading(self, obj_id):
    # 가장 최근 두 지점의 위치와 시간
    pos_prev = self.objects[obj_id]['positions'][-2]
    pos_curr = self.objects[obj_id]['positions'][-1]
    # ... 생략 ...
    
    # 시간 간격 (초)
    dt = time_curr - time_prev
    
    # 카르테시안 좌표에서의 변화 (미터)
    dx = cart_curr[0] - cart_prev[0]
    dy = cart_curr[1] - cart_prev[1]
    
    # 속도 벡터 및 속력 계산
    vx, vy = dx / dt, dy / dt
    speed = math.sqrt(vx**2 + vy**2)
    
    # 방향 계산 (도)
    heading = calculate_bearing(pos_prev[0], pos_prev[1], pos_curr[0], pos_curr[1])
```

- 두 시점 간의 거리와 시간 차이를 이용해 속도 계산
- 카르테시안 좌표(미터)에서 변위를 계산해 정확한 물리적 속도 산출
- 방위각 계산으로 이동 방향 결정 (북쪽이 0도, 시계방향)

##### 2. 가속도 계산
```python
def _calculate_acceleration(self, obj_id):
    # ... 생략 ...
    
    # 각 구간의 속도 계산
    vx1 = (pos_t1[0] - pos_t0[0]) / dt1
    vy1 = (pos_t1[1] - pos_t0[1]) / dt1
    vx2 = (pos_t2[0] - pos_t1[0]) / dt2
    vy2 = (pos_t2[1] - pos_t1[1]) / dt2
    
    # 가속도 계산 (속도 변화율)
    ax = (vx2 - vx1) / ((dt1 + dt2) / 2)
    ay = (vy2 - vy1) / ((dt1 + dt2) / 2)
```

- 연속된 세 위치 지점을 사용하여 가속도 계산
- 두 구간의 속도 차이를 평균 시간 간격으로 나누는 방식 적용

##### 3. 미래 위치 예측
```python
def _predict_position_at_time(self, obj_id, time_delta):
    # ... 생략 ...
    
    # 등가속도 운동 방정식 사용 (s = s₀ + v₀t + ½at²)
    future_x = current_cart_pos[0] + velocity[0] * time_delta + 0.5 * acceleration[0] * time_delta ** 2
    future_y = current_cart_pos[1] + velocity[1] * time_delta + 0.5 * acceleration[1] * time_delta ** 2
```

- 물리학의 등가속도 운동 방정식을 사용하여 정확한 예측
- 현재 위치, 속도, 가속도 정보로 미래 위치 예측

##### 4. 최근접 시간 계산
```python
def _compute_closest_approach_time(self, id1, id2):
    # ... 생략 ...
    
    # 두 객체가 서로 접근하는지 확인
    approaching = np.dot(r, v) < 0
    if not approaching:
        return None  # 서로 멀어지는 중이면 충돌 없음
    
    # 등가속 운동 케이스 vs 등속 운동 케이스
    if np.linalg.norm(a) > 1e-10:
        # 샘플링 방식으로 최소 거리 시점 탐색
        # ... 생략 ...
    else:
        # 해석적 방법으로 정확한 최근접 시간 계산
        t_closest = -np.dot(r, v) / v_squared
```

- 벡터 연산을 통해 접근 여부 판단 (`np.dot(r, v) < 0`)
- 가속도가 유의미한 경우와 무시할 수 있는 경우 구분하여 처리

##### 5. 충돌 예측
```python
def predict_collisions(self):
    # ... 생략 ...
    
    # 모든 객체 쌍에 대해 충돌 예측
    for i in range(len(obj_ids)):
        for j in range(i + 1, len(obj_ids)):
            # ... 생략 ...
            
            # 현재 직사각형이 이미 충돌 중인지 확인
            if do_rectangles_intersect(rect1.corners, rect2.corners):
                # 이미 충돌 중인 경우 처리
                # ... 생략 ...
                continue
            
            # 벡터 기반으로 가장 가까워지는 시간 계산
            closest_time = self._compute_closest_approach_time(id1, id2)
            
            if closest_time is not None and closest_time <= self.ttc_threshold:
                # 해당 시간에 두 객체의 위치 예측 및 충돌 확인
                # ... 생략 ...
```

- 모든 객체 쌍(n²/2 복잡도)에 대해 충돌 가능성 검사
- 현재 이미 충돌 중인 경우와 미래 충돌 예측 구분
- 두 단계 접근법으로 효율성 확보:
  1. 최근접 시간 계산으로 가능성 필터링
  2. 해당 시점에서 차량 직사각형 교차 여부 정밀 검사

## 데이터 흐름

시스템의 데이터 흐름은 다음과 같습니다:

1. **비디오 프레임 획득**:
   - `video_processor.py`에서 비디오 소스에서 프레임 읽기
   - `streaming.py`를 통해 웹 클라이언트에 실시간 스트리밍

2. **객체 감지 및 추적**:
   - YOLO 모델을 사용하여 프레임에서 차량 등 객체 감지
   - 이미지 좌표를 GPS 좌표로 변환
   - 객체 ID 부여 및 추적

3. **충돌 예측**:
   - 객체 위치 이력 저장 및 속도/방향/가속도 계산
   - 미래 위치 예측 및 충돌 가능성 검사
   - 충돌 위험이 있는 객체 쌍 식별 및 TTC 계산

4. **데이터 시각화 및 전송**:
   - 객체 및 충돌 정보를 GeoJSON 형식으로 변환
   - Socket.IO를 통해 웹 클라이언트에 실시간 전송
   - 웹 인터페이스에서 지도 시각화 및 충돌 경고 표시

## 시스템 설치 및 실행

### 사전 요구사항
- Python
- pip (Python 패키지 관리자)
- 웹캠 또는 분석할 비디오 파일

### 설치 단계

1. 프로젝트 복제하기
   ```bash
   git clone https://github.com/graduateam/Backend-Flask.git
   cd Backend-Flask
   ```

2. 의존성 설치
   ```bash
   pip install -r requirements.txt
   ``` 
    <pre style="color: #F05650; background-color: black; padding: 10px;">
    ERROR: Could not find a version that satisfies the requirement torch==2.6.0+cu126 (from versions: 2.6.0)
    ERROR: No matching distribution found for torch==2.6.0+cu126
    </pre>

    - 위와 같은 오류 발생 시, 다음 명령어 실행
    ```bash
    pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu126
    pip install -r requirements.txt 
   ```
   
   - 'CUDA(GPU)'로 실행이 안되는 경우, 다음 명령어 실행
   ```bash
    pip uninstall torch torchvision
    pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu126
   ```


3. 필요한 모델 파일
   - YOLO 모델 파일(`app/static/yolo_models/` 디렉토리에 저장)
   - 기본 모델은 `0317_best.pt`를 사용함

4. 설정 파일 수정 (필요한 경우)
   - `config.py` 파일에서 다음 설정 확인:
     - `VIDEO_SOURCE`: 사용할 비디오 소스 (파일 경로 또는 카메라 ID)
     - `MAP_API_KEY`: 네이버 지도 API 키
     - `IMAGE_POINTS` 및 `WORLD_POINTS`: 좌표 변환 설정

### 애플리케이션 실행

1. 애플리케이션 시작
   ```bash
   python app.py
   ```

2. 실행 성공 시 다음과 같은 메시지가 표시됩니다:
   ```
   * Running on http://127.0.0.1:5000 (Press CTRL+C to quit)
   ```

## 사용자 인터페이스 가이드

### 웹 인터페이스 접속

#### 로컬 접속
1. 웹 브라우저 열기 (Chrome, Firefox, Safari 등 권장)
2. 주소창에 `http://localhost:5000` 입력
3. 차량 충돌 예측 시스템 메인 페이지가 로드됩니다

#### 외부 접속 (같은 네트워크)
1. 서버 실행 기기의 IP 주소 확인
   ```bash
   # Linux/Mac
   ifconfig
   
   # Windows
   ipconfig
   ```
2. 웹 브라우저에서 `http://<서버IP>:5000` 접속
   (예: `http://192.168.1.100:5000`)

### 사용자 인터페이스 구성

웹 인터페이스는 두 개의 주요 패널로 구성되어 있습니다:

#### 좌측 패널
- **시스템 제어**: 연결 시작/중지 버튼 및 상태 표시
- **카메라 피드**: 실시간 비디오 스트림과 객체 감지 시각화
- **감지된 객체**: 현재 추적 중인 모든 객체 목록과 정보

#### 우측 패널
- **지도 뷰**: 객체 위치 및 이동 방향, 충돌 예측 시각화
- **충돌 예측**: 감지된 충돌 위험 경고 목록

## 주요 기능 사용법

### 시스템 연결 및 제어

1. **연결 시작**
   - 좌측 패널 상단의 `연결 시작` 버튼 클릭
   - 버튼 클릭 시 다음 절차가 실행됩니다:
     1. 비디오 소스 연결
     2. YOLO 객체 감지 모델 초기화
     3. 충돌 예측 알고리즘 활성화
     4. 카메라 피드 및 지도 데이터 스트리밍 시작
   - 처리가 시작되면 상태 표시기가 빨간색에서 녹색으로 변경되며 "충돌 예측 실행 중" 메시지가 표시됩니다

2. **중지**
   - `중지` 버튼 클릭으로 모든 처리 중단
   - 처리가 중지되면 상태 표시기가 녹색에서 빨간색으로 변경되며 "연결 준비됨" 메시지로 돌아갑니다

### 지도 컨트롤 사용

1. **카메라 범위 표시**
   - 우측 하단 체크박스로 카메라 시야 범위 표시/숨김 전환
   - 체크 시 오렌지색 경계선으로 카메라가 비추는 영역 표시

2. **지도 유형 변경**
   - 지도 우측 상단의 드롭다운 메뉴 클릭
   - 지도 유형 선택:
     - `위성`: 위성 이미지 지도
     - `지형도`: 일반 도로 지도
     - `하이브리드`: 위성 이미지와 도로 정보 결합

3. **지도 탐색**
   - 마우스 드래그: 지도 이동
   - 마우스 휠 또는 +/- 버튼: 확대/축소
   - 더블 클릭: 특정 위치 확대

### 객체 및 충돌 정보 확인

1. **객체 정보 확인**
   - 좌측 하단 테이블에 감지된 모든 객체 정보 표시
   - 각 객체의 ID, 위치(위도/경도), 속도 확인 가능
   - 충돌 위험이 있는 객체는 빨간색으로 강조 표시

2. **충돌 경고 확인**
   - 우측 하단 패널에 감지된 충돌 위험 표시
   - 각 경고는 다음 정보 포함:
     - 충돌 예상 시간
     - 관련 차량 ID
     - 충돌까지 남은 시간(TTC)
   - 경고 심각도에 따라 색상 구분:
     - 노란색(경고): 3초 이내 충돌 가능성
     - 빨간색(위험): 1초 이내 충돌 가능성

## 인터페이스 요소 설명

### 카메라 피드
- 비디오 소스에서 직접 스트리밍되는 실시간 피드
- 감지된 객체에 바운딩 박스 표시
- 안전한 객체는 녹색, 충돌 위험 객체는 빨간색으로 표시
- 각 객체의 ID 및 충돌 위험 여부 표시

### 지도 표시
- 카메라 시야 영역 내의 지리적 공간 표시
- 차량 위치를 컬러 마커로 표시
- 차량 마커 설명:
  - 마커 색상: 파란색(안전), 빨간색(충돌 위험)
  - 마커 내 화살표: 차량 이동 방향
  - 외곽선: 차량 실제 크기 및 방향 표시
- 충돌 지점 표시:
  - 빨간색 X 표시: 예상 충돌 지점
  - 깜빡임 효과: 경고 긴급성 표시

### 객체 목록 테이블
- 모든 감지된 객체의 실시간 정보 표시
- 각 행은 하나의 객체 표시
- 포함 정보:
  - ID: 객체 고유 식별자
  - 위도/경도: 객체의 지리적 위치
  - 속력(km/h): 객체의 현재 이동 속도
- 충돌 위험 객체는 빨간색 배경으로 강조

### 충돌 경고 알림
- 실시간 충돌 예측 결과 표시
- 각 알림 요소:
  - 시간 표시: 경고 발생 시간
  - 차량 정보: 충돌 위험이 있는 차량 ID
  - TTC 정보: 충돌까지 남은 시간(초)
- 5초 후 자동으로 사라지는 페이드 아웃 효과

### 상태 표시
- 시스템 현재 상태 표시
- 상태 인디케이터:
  - 빨간색: 처리 중지 상태
  - 녹색(깜빡임): 처리 중 상태
- 상태 텍스트:
  - "연결 준비됨": 초기 상태 또는 중지 상태
  - "충돌 예측 실행 중": 처리 중 상태

## 문제 해결

### 비디오 피드 문제
- **증상**: 비디오 피드가 표시되지 않음
- **해결 방법**:
  1. 설정 파일의 `VIDEO_SOURCE` 확인
  2. 비디오 파일 경로 또는 카메라 ID 올바른지 확인
  3. 처리 중지 후 다시 시작 시도

### 지도 로드 문제
- **증상**: 지도가 로드되지 않거나 오류 메시지 표시
- **해결 방법**:
  1. 네이버 지도 API 키 유효성 확인
  2. 인터넷 연결 상태 확인
  3. 브라우저 콘솔에서 네트워크 오류 확인

### 객체 감지 문제
- **증상**: 객체가 감지되지 않거나 잘못 분류됨
- **해결 방법**:
  1. YOLO 모델 파일 존재 확인
  2. 충분한 조명 확보
  3. 카메라 위치 및 각도 조정

### 속도 계산 문제
- **증상**: 객체 속도가 0으로 표시되거나 불규칙함
- **해결 방법**:
  1. 객체가 실제로 움직이는지 확인
  2. 좌표 변환 설정(`IMAGE_POINTS`, `WORLD_POINTS`) 확인
  3. 낮은 프레임 속도로 인한 경우 `events.py`의 시간 간격 조정

### 충돌 예측 문제
- **증상**: 충돌 예측이 나타나지 않거나 부정확함
- **해결 방법**:
  1. `config.py`의 충돌 임계값(`TTC_THRESHOLD`) 확인
  2. 차량 크기 설정(`CAR_LENGTH`, `CAR_WIDTH`) 확인
  3. 카메라 캘리브레이션 설정 검증

### 로그 확인
문제 해결에 도움이 되는 로그는 콘솔 출력에서 확인할 수 있습니다. 추가 디버깅을 위해 로그 레벨 변경:
```python
# app/utils/logger.py에서 로그 레벨 변경
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG').upper()
```
