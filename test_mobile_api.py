#!/usr/bin/env python
"""
모바일 API 테스트 스크립트
Backend-Flask 모바일 API 엔드포인트들을 테스트
"""
import requests
import json
import time
from datetime import datetime

# 테스트 설정
BASE_URL = "http://localhost:5000"
TEST_DEVICE_ID = f"device_{int(time.time())}_abc123def456"

def test_api_endpoint(method, endpoint, data=None, params=None):
    """API 엔드포인트 테스트 헬퍼 함수"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, params=params)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data)
        else:
            print(f"❌ 지원하지 않는 HTTP 메서드: {method}")
            return False
        
        print(f"\n{'='*60}")
        print(f"🔍 Testing: {method.upper()} {endpoint}")
        print(f"📤 Request Data: {json.dumps(data, indent=2) if data else 'None'}")
        print(f"📤 Request Params: {params if params else 'None'}")
        print(f"📊 Status Code: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"📥 Response: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200 and response_json.get('success'):
                print("✅ 테스트 통과!")
                return True
            else:
                print("❌ 테스트 실패!")
                return False
                
        except json.JSONDecodeError:
            print(f"📥 Response (Raw): {response.text}")
            print("❌ JSON 파싱 실패!")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ 연결 실패: {url}")
        print("   서버가 실행 중인지 확인하세요 (python app.py)")
        return False
    except Exception as e:
        print(f"❌ 예외 발생: {str(e)}")
        return False

def test_mobile_api():
    """모바일 API 전체 테스트 실행"""
    print("🚀 모바일 API 테스트 시작")
    print(f"📱 테스트 Device ID: {TEST_DEVICE_ID}")
    
    test_results = []
    
    # 1. API 상태 확인
    print("\n" + "="*60)
    print("📋 1. API 상태 확인 테스트")
    result = test_api_endpoint('GET', '/api/status')
    test_results.append(('API Status', result))
    
    # 2. CCTV 정보 조회
    print("\n" + "="*60) 
    print("📋 2. CCTV 커버리지 정보 조회 테스트")
    result = test_api_endpoint('GET', '/api/cctv')
    test_results.append(('CCTV Coverage', result))
    
    # 3. 위치 업데이트 (첫 번째)
    print("\n" + "="*60)
    print("📋 3. 첫 번째 위치 업데이트 테스트")
    first_location_data = {
        "device_id": TEST_DEVICE_ID,
        "timestamp": datetime.now().isoformat() + "Z",
        "location": {
            "latitude": 37.67675942,
            "longitude": 126.74583666
        }
    }
    result = test_api_endpoint('POST', '/api/location', first_location_data)
    test_results.append(('First Location Update', result))
    
    # 잠시 대기 (속도 계산을 위해)
    print("\n⏳ 속도 계산을 위해 2초 대기...")
    time.sleep(2)
    
    # 4. 위치 업데이트 (두 번째) - 이동하여 속도 생성
    print("\n" + "="*60)
    print("📋 4. 두 번째 위치 업데이트 테스트 (이동)")
    second_location_data = {
        "device_id": TEST_DEVICE_ID,
        "timestamp": datetime.now().isoformat() + "Z",
        "location": {
            "latitude": 37.67685942,  # 약 10m 북쪽으로 이동
            "longitude": 126.74593666  # 약 10m 동쪽으로 이동
        }
    }
    result = test_api_endpoint('POST', '/api/location', second_location_data)
    test_results.append(('Second Location Update', result))
    
    # 5. 주변 차량 조회
    print("\n" + "="*60)
    print("📋 5. 주변 차량 조회 테스트")
    vehicle_params = {
        'lat': 37.67675942,
        'lng': 126.74583666,
        'radius': 500
    }
    result = test_api_endpoint('GET', '/api/vehicles/nearby', params=vehicle_params)
    test_results.append(('Nearby Vehicles', result))
    
    # 6. 주변 보행자 조회
    print("\n" + "="*60)
    print("📋 6. 주변 보행자 조회 테스트")
    people_params = {
        'lat': 37.67675942,
        'lng': 126.74583666,
        'radius': 500
    }
    result = test_api_endpoint('GET', '/api/people/nearby', params=people_params)
    test_results.append(('Nearby People', result))
    
    # 7. 충돌 경고 조회
    print("\n" + "="*60)
    print("📋 7. 충돌 경고 조회 테스트")
    collision_data = {
        "device_id": TEST_DEVICE_ID,
        "latitude": 37.67675942,
        "longitude": 126.74583666
    }
    result = test_api_endpoint('POST', '/api/collision/warning', collision_data)
    test_results.append(('Collision Warning', result))
    
    # 8. 잘못된 Device ID 테스트
    print("\n" + "="*60)
    print("📋 8. 잘못된 Device ID 테스트")
    invalid_location_data = {
        "device_id": "invalid_device_id",
        "timestamp": datetime.now().isoformat() + "Z",
        "location": {
            "latitude": 37.67675942,
            "longitude": 126.74583666
        }
    }
    result = test_api_endpoint('POST', '/api/location', invalid_location_data)
    # 이 테스트는 실패해야 정상
    test_results.append(('Invalid Device ID', not result))  # 결과 반전
    
    # 결과 요약
    print("\n" + "="*80)
    print("📊 모바일 API 테스트 결과 요약")
    print("="*80)
    
    passed = 0
    total = len(test_results)
    
    for test_name, test_success in test_results:
        status = "✅ PASS" if test_success else "❌ FAIL"
        print(f"{status} {test_name}")
        if test_success:
            passed += 1
    
    print(f"\n📈 총 테스트: {total}개")
    print(f"✅ 통과: {passed}개")
    print(f"❌ 실패: {total - passed}개")
    print(f"📊 성공률: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
    else:
        print(f"\n⚠️  {total - passed}개의 테스트가 실패했습니다. 서버 로그를 확인하세요.")
    
    return passed == total

def test_invalid_requests():
    """잘못된 요청 테스트"""
    print("\n" + "="*60)
    print("📋 잘못된 요청 테스트")
    
    invalid_tests = [
        {
            'name': '빈 요청 데이터',
            'method': 'POST',
            'endpoint': '/api/location',
            'data': {}
        },
        {
            'name': '위도 없음',
            'method': 'POST', 
            'endpoint': '/api/location',
            'data': {
                "device_id": TEST_DEVICE_ID,
                "location": {"longitude": 126.74583666}
            }
        },
        {
            'name': '잘못된 위도 범위',
            'method': 'POST',
            'endpoint': '/api/location', 
            'data': {
                "device_id": TEST_DEVICE_ID,
                "location": {"latitude": 999, "longitude": 126.74583666}
            }
        }
    ]
    
    for test in invalid_tests:
        print(f"\n🔍 {test['name']} 테스트")
        result = test_api_endpoint(test['method'], test['endpoint'], test['data'])
        # 이런 요청들은 실패해야 정상
        if not result:
            print("✅ 예상대로 실패 (정상)")
        else:
            print("❌ 예상과 다르게 성공 (비정상)")

if __name__ == "__main__":
    print("🧪 Backend-Flask 모바일 API 테스트")
    print("="*60)
    print("⚠️  주의: 이 테스트를 실행하기 전에 서버를 시작하세요:")
    print("   cd Backend-Flask")
    print("   python app.py")
    print("="*60)
    
    input("서버가 준비되면 Enter를 눌러주세요...")
    
    # 메인 테스트 실행
    success = test_mobile_api()
    
    # 추가 잘못된 요청 테스트
    test_invalid_requests()
    
    print("\n🏁 테스트 완료!")
    
    if success:
        exit(0)
    else:
        exit(1)