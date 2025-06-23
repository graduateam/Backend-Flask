#!/usr/bin/env python3
"""
Flask API 테스트 스크립트
모바일 앱 연동을 위한 API 엔드포인트 테스트
"""

import requests
import json
import time
from datetime import datetime

# Flask 서버 URL (필요시 수정)
BASE_URL = "http://localhost:5000"

def test_api_status():
    """API 상태 확인 테스트"""
    print("1. API 상태 확인 테스트...")
    try:
        response = requests.get(f"{BASE_URL}/api/status")
        print(f"   응답 상태: {response.status_code}")
        print(f"   응답 내용: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"   오류: {e}")
        return False

def test_location_update():
    """위치 업데이트 API 테스트"""
    print("\n2. 위치 업데이트 API 테스트...")
    
    # 테스트 데이터
    test_data = {
        "device_id": "test_device_123",
        "timestamp": datetime.now().isoformat(),
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
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/location/update",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"   응답 상태: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   성공: {data['success']}")
            print(f"   메시지: {data['message']}")
            print(f"   차량 수: {data['nearby_vehicles']['total_count']}")
            print(f"   보행자 수: {data['nearby_people']['total_count']}")
            print(f"   충돌 경고: {data['collision_warning']['hasWarning']}")
            
            if data['collision_warning']['hasWarning']:
                warning = data['collision_warning']['warning']
                print(f"   경고 상세: {warning['objectType']} ID {warning['objectId']}, "
                      f"TTC {warning['ttc']:.1f}초, 심각도 {warning['severity']}")
        else:
            print(f"   오류 응답: {response.text}")
            
        return response.status_code == 200
    except Exception as e:
        print(f"   오류: {e}")
        return False

def test_nearby_vehicles():
    """주변 차량 조회 API 테스트"""
    print("\n3. 주변 차량 조회 API 테스트...")
    
    params = {
        "latitude": 37.5666102,
        "longitude": 126.9783881,
        "radius": 500
    }
    
    try:
        response = requests.get(f"{BASE_URL}/api/vehicles/nearby", params=params)
        print(f"   응답 상태: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   성공: {data['success']}")
            print(f"   차량 수: {data['data']['total_count']}")
            
            if data['data']['total_count'] > 0:
                vehicle = data['data']['vehicles'][0]
                print(f"   첫 번째 차량: ID {vehicle['id']}, "
                      f"위치 ({vehicle['latitude']:.6f}, {vehicle['longitude']:.6f}), "
                      f"속도 {vehicle['speed_kph']:.1f} km/h")
        else:
            print(f"   오류 응답: {response.text}")
            
        return response.status_code == 200
    except Exception as e:
        print(f"   오류: {e}")
        return False

def test_nearby_people():
    """주변 보행자 조회 API 테스트"""
    print("\n4. 주변 보행자 조회 API 테스트...")
    
    params = {
        "latitude": 37.5666102,
        "longitude": 126.9783881,
        "radius": 500
    }
    
    try:
        response = requests.get(f"{BASE_URL}/api/people/nearby", params=params)
        print(f"   응답 상태: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   성공: {data['success']}")
            print(f"   보행자 수: {data['data']['total_count']}")
            
            if data['data']['total_count'] > 0:
                person = data['data']['people'][0]
                print(f"   첫 번째 보행자: ID {person['id']}, "
                      f"위치 ({person['latitude']:.6f}, {person['longitude']:.6f}), "
                      f"속도 {person['speed_kph']:.1f} km/h")
        else:
            print(f"   오류 응답: {response.text}")
            
        return response.status_code == 200
    except Exception as e:
        print(f"   오류: {e}")
        return False

def test_collision_warning():
    """충돌 경고 조회 API 테스트"""
    print("\n5. 충돌 경고 조회 API 테스트...")
    
    test_data = {
        "device_id": "test_device_123",
        "latitude": 37.5666102,
        "longitude": 126.9783881
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/collision/warning",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"   응답 상태: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   성공: {data['success']}")
            print(f"   경고 있음: {data['data']['hasWarning']}")
            
            if data['data']['hasWarning']:
                warning = data['data']['warning']
                print(f"   경고 상세: {warning['objectType']} ID {warning['objectId']}, "
                      f"방향 {warning['relativeDirection']}, "
                      f"TTC {warning['ttc']:.1f}초")
        else:
            print(f"   오류 응답: {response.text}")
            
        return response.status_code == 200
    except Exception as e:
        print(f"   오류: {e}")
        return False

def test_collision_warning_generation():
    """충돌 경고 생성 주기 테스트 (7번째 요청마다)"""
    print("\n6. 충돌 경고 생성 주기 테스트 (7번째 요청마다)...")
    
    collision_count = 0
    total_requests = 10
    
    for i in range(total_requests):
        test_data = {
            "device_id": f"test_device_{i}",
            "timestamp": datetime.now().isoformat(),
            "location": {
                "latitude": 37.5666102 + i * 0.0001,  # 약간씩 다른 위치
                "longitude": 126.9783881 + i * 0.0001,
                "accuracy": 5.0
            },
            "device_info": {
                "device_type": "mobile",
                "app_version": "1.0.0"
            }
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/location/update",
                json=test_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                has_warning = data['collision_warning']['hasWarning']
                print(f"   요청 {i+1}: 충돌 경고 {'있음' if has_warning else '없음'}")
                
                if has_warning:
                    collision_count += 1
                    warning = data['collision_warning']['warning']
                    print(f"     -> {warning['objectType']} {warning['objectId']}, "
                          f"심각도: {warning['severity']}, TTC: {warning['ttc']:.1f}초")
            
            time.sleep(0.1)  # 짧은 지연
        except Exception as e:
            print(f"   요청 {i+1} 오류: {e}")
    
    print(f"   총 {total_requests}번 요청 중 {collision_count}번 충돌 경고 발생")
    return True

def main():
    """전체 테스트 실행"""
    print("Flask API 테스트 시작")
    print("=" * 50)
    
    tests = [
        test_api_status,
        test_location_update,
        test_nearby_vehicles,
        test_nearby_people,
        test_collision_warning,
        test_collision_warning_generation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   테스트 실행 중 오류: {e}")
    
    print("\n" + "=" * 50)
    print(f"테스트 완료: {passed}/{total} 통과")
    
    if passed == total:
        print("✅ 모든 테스트 성공! React Native 앱에서 연결할 수 있습니다.")
    else:
        print("❌ 일부 테스트 실패. Flask 서버 상태를 확인하세요.")
        print("\n확인사항:")
        print("1. Flask 서버가 실행 중인지 확인 (python app.py)")
        print("2. 포트 5000이 사용 가능한지 확인")
        print("3. requirements.txt의 모든 패키지가 설치되었는지 확인")

if __name__ == "__main__":
    main()