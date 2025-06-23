# 스마트 도로반사경 통합 API 문서

**버전**: 1.0.0  
**업데이트**: 2025-01-25  
**목적**: React Native 모바일 앱과 Flask 충돌 예측 서버 간의 통합 통신 규격

## 📋 목차

1. [개요](#개요)
2. [실시간 위치 추적 API (통합)](#실시간-위치-추적-api)
3. [주변 객체 조회 API (참고용)](#주변-객체-조회-api-참고용)
4. [충돌 경고 API (참고용)](#충돌-경고-api-참고용)
5. [WebSocket 이벤트](#websocket-이벤트)
6. [데이터 모델](#데이터-모델)
7. [오류 처리](#오류-처리)

---

## 개요

### 시스템 아키텍처 (임시)
```
[모바일 앱] ←→ [Flask 서버] ←→ [YOLO + 충돌예측]
     ↑              ↑
   HTTP API    Socket.IO (실시간)
```

### 통신 흐름
1. **연결**: 모바일 앱이 Flask 서버에 연결 (익명 사용자)
2. **통합 요청**: 모바일 앱이 1초마다 위치 정보를 전송
3. **서버 분석**: Flask가 위치 이력으로 속도/방향 계산 + YOLO 충돌예측
4. **통합 응답**: 주변 차량/보행자 정보 + 충돌 경고를 한 번에 반환

---

## 실시간 위치 추적 API (통합)

### POST `/api/location/update`
모바일 앱에서 자신의 위치 정보를 Flask 서버로 전송 (1초마다)  
**서버가 위치 이력을 기반으로 속도/방향을 계산하고, 주변 객체 정보와 충돌 경고를 함께 반환합니다**

**요청**:
```json
{
  "device_id": "mobile_device_123",
  "timestamp": "2025-01-25T10:30:00.000Z",
  "location": {
    "latitude": 37.5666102,
    "longitude": 126.9783881,
    "accuracy": 5.0
  },
  "device_info": {
    "device_type": "mobile",
    "app_version": "1.0.0"
  }
}
```

**응답**:
```json
{
  "success": true,
  "message": "위치 정보 업데이트 완료",
  "server_timestamp": "2025-01-25T10:30:00.500Z",
  "assigned_id": "mobile_user_789",
  "calculated_motion": {
    "speed": 15.5,
    "speed_kph": 55.8,
    "heading": 45.2
  },
  "nearby_vehicles": {
    "vehicles": [
      {
        "id": "vehicle_456",
        "type": "vehicle",
        "latitude": 37.5666200,
        "longitude": 126.9783900,
        "heading": 90.5,
        "speed": 12.3,
        "speed_kph": 44.3,
        "timestamp": "2025-01-25T10:30:01.000Z",
        "is_collision_risk": false,
        "ttc": null,
        "source": "camera_detection"
      }
    ],
    "total_count": 5
  },
  "nearby_people": {
    "people": [
      {
        "id": "person_789",
        "type": "person",
        "latitude": 37.5666150,
        "longitude": 126.9783850,
        "heading": 180.0,
        "speed": 1.4,
        "speed_kph": 5.0,
        "timestamp": "2025-01-25T10:30:01.000Z",
        "is_collision_risk": false,
        "ttc": null
      }
    ],
    "total_count": 3
  },
  "collision_warning": {
    "hasWarning": true,
    "warning": {
      "objectId": "vehicle_456",
      "objectType": "vehicle",
      "direction": 90.5,
      "relativeDirection": "front-right",
      "speed": 12.3,
      "speed_kph": 44.3,
      "distance": 25.7,
      "ttc": 2.1,
      "severity": "high",
      "timestamp": "2025-01-25T10:30:01.000Z"
    }
  }
}
```

---

## 주변 객체 조회 API (참고용)

> **주요 용도**: `/api/location/update`가 통합 응답을 제공하므로, 이 개별 API들은 **특수한 경우**에만 사용됩니다.

### GET `/api/vehicles/nearby`
주변 차량 정보만 개별 조회 (일반적으로 사용되지 않음)

**쿼리 파라미터**:
- `latitude`: 위도
- `longitude`: 경도  
- `radius`: 반경(미터, 기본값: 500)

**응답**:
```json
{
  "success": true,
  "data": {
    "vehicles": [
      {
        "id": "vehicle_456",
        "type": "vehicle",
        "latitude": 37.5666200,
        "longitude": 126.9783900,
        "heading": 90.5,
        "speed": 12.3,
        "speed_kph": 44.3,
        "timestamp": "2025-01-25T10:30:01.000Z",
        "is_collision_risk": false,
        "ttc": null,
        "source": "camera_detection"
      }
    ],
    "timestamp": "2025-01-25T10:30:01.000Z",
    "total_count": 5
  }
}
```

### GET `/api/people/nearby`
주변 보행자 정보 조회

**응답 구조는 vehicles와 동일하되 type이 "person"**

---

## 충돌 경고 API (참고용)

> **주요 용도**: `/api/location/update`가 통합 응답을 제공하므로, 이 개별 API는 **특수한 경우**에만 사용됩니다.

### POST `/api/collision/warning`
충돌 위험 정보만 개별 조회 (일반적으로 사용되지 않음)  
**서버가 위치 이력으로 계산한 속도/방향 정보를 사용합니다**

**요청**:
```json
{
  "device_id": "mobile_device_123",
  "latitude": 37.5666102,
  "longitude": 126.9783881
}
```

**응답**:
```json
{
  "success": true,
  "data": {
    "warning": {
      "objectId": "vehicle_456",
      "objectType": "vehicle",
      "direction": 90.5,
      "relativeDirection": "front-right",
      "speed": 12.3,
      "speed_kph": 44.3,
      "distance": 25.7,
      "ttc": 2.1,
      "severity": "high",
      "timestamp": "2025-01-25T10:30:01.000Z"
    },
    "hasWarning": true
  }
}
```

---

## WebSocket 이벤트 (보조)

> **주요 용도**: HTTP API가 주요 통신 방식이며, WebSocket은 **추가적인 실시간 알림**이나 **시스템 상태 업데이트**에 사용됩니다.

### 연결 설정
```javascript
const socket = io('ws://flask-server:5000');

// 디바이스 정보 등록
socket.emit('register_device', {
  device_id: 'mobile_device_123',
  device_type: 'mobile',
  app_version: '1.0.0'
});
```

### 클라이언트 → 서버 이벤트

#### `location_update`
실시간 위치 업데이트 (1초마다) - 위치 정보만 전송
```json
{
  "device_id": "mobile_device_123",
  "latitude": 37.5666102,
  "longitude": 126.9783881,
  "timestamp": "2025-01-25T10:30:01.000Z"
}
```

### 서버 → 클라이언트 이벤트

#### `nearby_objects_update`
주변 객체 정보 업데이트 (실시간)
```json
{
  "vehicles": [...],
  "people": [...],
  "timestamp": "2025-01-25T10:30:01.000Z"
}
```

#### `collision_warning`
충돌 경고 (즉시 전송)
```json
{
  "warning": {
    "objectId": "vehicle_456",
    "objectType": "vehicle",
    "severity": "critical",
    "ttc": 1.2,
    "distance": 8.5,
    "relativeDirection": "front"
  },
  "timestamp": "2025-01-25T10:30:01.000Z"
}
```

#### `system_status`
시스템 상태 업데이트
```json
{
  "processing_active": true,
  "connected_devices": 12,
  "camera_status": "active",
  "detection_fps": 25.5
}
```

---

## 데이터 모델

### Vehicle (차량)
```typescript
interface Vehicle {
  id: string;
  type: "vehicle";
  latitude: number;
  longitude: number;
  heading: number;        // 0-360도
  speed: number;          // m/s
  speed_kph: number;      // km/h
  timestamp: string;      // ISO 8601
  is_collision_risk: boolean;
  ttc?: number;          // Time to Collision (초)
  source: "camera_detection" | "mobile_user" | "simulation";
}
```

### Person (보행자)
```typescript
interface Person {
  id: string;
  type: "person";
  latitude: number;
  longitude: number;
  heading: number;
  speed: number;
  speed_kph: number;
  timestamp: string;
  is_collision_risk: boolean;
  ttc?: number;
}
```

### CollisionWarning (충돌 경고)
```typescript
interface CollisionWarning {
  objectId: string;
  objectType: "vehicle" | "person";
  direction: number;                    // 절대 방향 (0-360도)
  relativeDirection: "front" | "front-left" | "front-right" | 
                    "left" | "right" | "rear-left" | "rear" | "rear-right";
  speed: number;                       // m/s
  speed_kph: number;                   // km/h
  distance: number;                    // 미터
  ttc: number;                        // Time to Collision (초)
  severity: "low" | "medium" | "high" | "critical";
  timestamp: string;                   // ISO 8601
}
```

### LocationUpdate (위치 업데이트)
```typescript
interface LocationUpdate {
  device_id: string;
  timestamp: string;
  location: {
    latitude: number;
    longitude: number;
    accuracy: number;                  // GPS 정확도 (미터)
  };
  device_info: {
    device_type: "mobile" | "vehicle" | "infrastructure";
    app_version: string;
  };
}

// 서버에서 계산되는 모션 정보
interface CalculatedMotion {
  speed: number;                       // m/s (서버 계산)
  speed_kph: number;                   // km/h (서버 계산)
  heading: number;                     // 0-360도 (서버 계산)
  acceleration?: {                     // 가속도 (서버 계산)
    x: number;
    y: number;
  };
}
```

---

## 오류 처리

### HTTP 오류 응답
```json
{
  "success": false,
  "error": {
    "code": "LOCATION_INVALID",
    "message": "위치 정보가 유효하지 않습니다",
    "details": "Latitude out of range"
  },
  "timestamp": "2025-01-25T10:30:01.000Z"
}
```

### 주요 오류 코드
- `DEVICE_NOT_REGISTERED`: 디바이스 미등록
- `LOCATION_INVALID`: 위치 정보 오류  
- `RATE_LIMIT_EXCEEDED`: 요청 빈도 초과
- `INTERNAL_ERROR`: 서버 내부 오류
- `CAMERA_UNAVAILABLE`: 카메라 시스템 오류

### WebSocket 오류 이벤트
```json
{
  "event": "error",
  "data": {
    "code": "CONNECTION_LOST",
    "message": "카메라 연결이 끊어졌습니다",
    "reconnect_in": 5000
  }
}
```

---

## 구현 체크리스트

### Flask 서버 측
- [ ] 디바이스 등록 및 관리 시스템 구현
- [ ] **통합 위치 업데이트 API 구현** (`/api/location/update`)
- [ ] **모바일 사용자 위치 이력 기반 속도/방향 계산**
- [ ] **한 번의 요청으로 주변 객체 + 충돌 경고 통합 응답**
- [ ] 모바일 사용자를 충돌 예측 시스템에 통합
- [ ] Socket.IO 이벤트 핸들러 구현
- [ ] 기존 카메라 감지와 모바일 데이터 융합

### 모바일 앱 측  
- [ ] Real API 모드에서 Flask 서버 연결
- [ ] **1초마다 위치 정보 전송 후 통합 응답 처리**
- [ ] **통합 응답에서 주변 객체 정보 추출 및 UI 업데이트**
- [ ] **통합 응답에서 충돌 경고 추출 및 알림 처리**
- [ ] Socket.IO 실시간 데이터 수신 (보조)
- [ ] 오프라인 모드 처리

### 테스트 시나리오
- [ ] 단일 모바일 사용자 테스트
- [ ] 다중 사용자 동시 접속 테스트
- [ ] 카메라 감지 + 모바일 사용자 혼합 시나리오
- [ ] 네트워크 끊김/재연결 테스트
- [ ] 충돌 경고 정확도 검증