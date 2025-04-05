/**
 * 네이버 지도 관련 JavaScript 코드
 */

// 전역 변수
var map = null;          // 네이버 맵 객체
var vehicleMarkers = {}; // 차량 마커 객체를 저장할 객체
var videoBoundsPolygon = null;
var showVideoBounds = true; // 기본값으로 표시
var vehiclePaths = {};   // 차량 경로를 저장할 객체
var collisionMarkers = {}; // 충돌 지점 마커를 저장할 객체
var infoWindows = {};    // 인포윈도우 객체 저장

/**
 * 지도 초기화 함수
 * @param {Object} center - 지도 중심 좌표 {lat, lng}
 */
function initMap(center) {
    var mapContainer = document.getElementById('map');
    var mapOptions = {
        center: new naver.maps.LatLng(center.lat, center.lng),
        zoom: 20,
        mapTypeId: naver.maps.MapTypeId.SATELLITE,
        mapTypeControl: true,
        mapTypeControlOptions: {
            style: naver.maps.MapTypeControlStyle.DROPDOWN
        }
    };

    try {
        map = new naver.maps.Map(mapContainer, mapOptions);
        console.log("지도 초기화 성공");

        // 비디오 경계 초기화
        updateVideoBounds();

        // 컨트롤 이벤트 설정
        setupVideoControlEvents();

        // 시간 표시 시작
        updateMapTime();
        setInterval(updateMapTime, 1000);
    } catch (e) {
        console.error("지도 초기화 실패:", e);
    }
}

// 지도 시간 업데이트 함수
function updateMapTime() {
    var now = new Date();
    var timeString = now.toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });

    var dateString = now.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });

    $('#map-time').text(dateString + ' ' + timeString);
}

/**
 * 지도 데이터 업데이트 함수
 * @param {Object} mapData - 지도 데이터 객체
 */
function updateMap(mapData) {
    if (!map) return;

    // 차량 마커 업데이트
    updateVehicleMarkers(mapData.vehicles);

    // 경로 업데이트
    updateVehiclePaths(mapData.paths);

    // 충돌 지점 마커 업데이트
    updateCollisionMarkers(mapData.collisions);
}

// 비디오 경계 표시 함수
function updateVideoBounds() {
    // 서버에서 비디오 경계 가져오기
    $.get('/api/video-bounds', function (data) {
        if (!data.success) {
            console.error('비디오 경계 가져오기 실패:', data.message);
            return;
        }

        console.log('비디오 경계 좌표:', data.corners);

        // 기존 폴리곤 제거
        if (videoBoundsPolygon) {
            videoBoundsPolygon.setMap(null);
        }

        // 좌표 변환 (Naver Maps API)
        var navermapCoords = data.corners.map(function (coord) {
            return new naver.maps.LatLng(coord[0], coord[1]);
        });

        // 폴리곤 생성
        videoBoundsPolygon = new naver.maps.Polygon({
            map: showVideoBounds ? map : null, // 체크박스 상태에 따라 표시 여부 결정
            paths: navermapCoords,
            strokeColor: '#FF7F00',
            strokeWeight: 2,
            strokeOpacity: 0.8,
            fillColor: '#FF7F00',
            fillOpacity: 0.1
        });
    }).fail(function (error) {
        console.error('비디오 경계 요청 실패:', error);
    });
}

// 체크박스 이벤트 핸들러
function setupVideoControlEvents() {
    $('#showVideoBounds').change(function () {
        showVideoBounds = $(this).is(':checked');

        // 폴리곤이 있으면 표시 여부 업데이트
        if (videoBoundsPolygon) {
            videoBoundsPolygon.setMap(showVideoBounds ? map : null);
        } else if (showVideoBounds) {
            // 폴리곤이 없는데 표시해야 하는 경우 새로 가져오기
            updateVideoBounds();
        }
    });
}

/**
 * 차량 마커 업데이트 함수
 * @param {Array} vehicles - 차량 GeoJSON 객체 배열
 */
function updateVehicleMarkers(vehicles) {
    console.log("updateVehicleMarkers 호출됨, 데이터:", vehicles);
    // 현재 표시된 모든 차량 ID 추적
    var currentVehicleIds = new Set();

    // 각 차량 마커 업데이트/생성
    vehicles.forEach(function (vehicle) {
        console.log("updateVehicleMarkers 호출됨, 데이터:", vehicles);
        var id = vehicle.properties.id;
        currentVehicleIds.add(id);

        var lat = vehicle.geometry.coordinates[1]; // GeoJSON은 [경도, 위도] 순서
        var lng = vehicle.geometry.coordinates[0];
        var position = new naver.maps.LatLng(lat, lng);

        // 차량 정보
        var speed = vehicle.properties.speed_kph;
        var heading = vehicle.properties.heading;
        var isCollisionRisk = vehicle.properties.is_collision_risk;
        var ttc = vehicle.properties.ttc; // 충돌까지 남은 시간 (초)

        // 마커 아이콘 설정
        var markerColor = isCollisionRisk ? '#ff4444' : '#4285F4';

        // 기존 마커가 있는지 확인
        if (id in vehicleMarkers) {
            // 마커 위치 업데이트
            vehicleMarkers[id].setPosition(position);

            // 마커 스타일 업데이트 (아이콘 변경)
            var markerIcon = createVehicleMarkerIcon(markerColor, heading);
            vehicleMarkers[id].setIcon(markerIcon);

            // 인포윈도우 내용 업데이트
            if (id in infoWindows) {
                infoWindows[id].setContent(createVehicleInfoWindowContent(id, speed, heading, isCollisionRisk, ttc));
            }
        } else {
            // 새 마커 생성
            var markerIcon = createVehicleMarkerIcon(markerColor, heading);

            var marker = new naver.maps.Marker({
                position: position,
                map: map,
                title: '차량 ID: ' + id,
                icon: markerIcon,
                zIndex: isCollisionRisk ? 100 : 10
            });

            // 차량 정보 표시 인포윈도우 생성
            var infoWindow = new naver.maps.InfoWindow({
                content: createVehicleInfoWindowContent(id, speed, heading, isCollisionRisk, ttc),
                maxWidth: 200,
                backgroundColor: "#fff",
                borderColor: "#ccc",
                borderWidth: 1,
                anchorSize: new naver.maps.Size(10, 10),
                pixelOffset: new naver.maps.Point(10, -10)
            });

            // 마커 클릭 이벤트 - 인포윈도우 토글
            naver.maps.Event.addListener(marker, 'click', function () {
                if (marker.infoWindowOpen) {
                    infoWindow.close();
                    marker.infoWindowOpen = false;
                } else {
                    infoWindow.open(map, marker);
                    marker.infoWindowOpen = true;
                }
            });

            // 마커와 인포윈도우 저장
            marker.infoWindowOpen = false;
            vehicleMarkers[id] = marker;
            infoWindows[id] = infoWindow;
        }

        // 차량 직사각형 표시 (해당 정보가 있는 경우)
        updateVehicleRectangle(id, vehicle.rectangle, isCollisionRisk);
    });

    // 더 이상 존재하지 않는 차량 마커 제거
    Object.keys(vehicleMarkers).forEach(function (id) {
        if (!currentVehicleIds.has(parseInt(id))) {
            vehicleMarkers[id].setMap(null);
            delete vehicleMarkers[id];

            // 관련 인포윈도우 제거
            if (id in infoWindows) {
                infoWindows[id].close();
                delete infoWindows[id];
            }

            // 관련 경로와 직사각형도 제거
            if (id in vehiclePaths) {
                if (vehiclePaths[id].path) vehiclePaths[id].path.setMap(null);
                if (vehiclePaths[id].predictedPath) vehiclePaths[id].predictedPath.setMap(null);
                if (vehiclePaths[id].rectangle) vehiclePaths[id].rectangle.setMap(null);
                delete vehiclePaths[id];
            }
        }
    });
}

/**
 * 차량 마커 아이콘 생성 함수 - 방향이 수정된 사각형 버전
 * @param {string} color - 마커 색상
 * @param {number} heading - 차량 진행 방향 (도)
 * @returns {Object} 네이버맵 마커 아이콘 객체
 */
function createVehicleMarkerIcon(color, heading) {
    // 차량 모양의 원형 아이콘 생성
    var radius = 13;  // 원의 반지름 (픽셀)
    var indicatorLength = 10; // 방향 표시기 길이

    // 캔버스 생성
    var canvasSize = (radius + indicatorLength) * 2 + 10;
    var canvas = document.createElement('canvas');
    canvas.width = canvasSize;
    canvas.height = canvasSize;
    var ctx = canvas.getContext('2d');

    // 캔버스 초기화
    ctx.clearRect(0, 0, canvasSize, canvasSize);

    // 중심점
    var centerX = canvasSize / 2;
    var centerY = canvasSize / 2;

    // 원 그리기
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 방향 표시기 그리기
    // heading에 따른 각도 계산 (북쪽이 0도, 시계방향)
    var angleRad = (heading - 90) * Math.PI / 180;

    // 삼각형 꼭지점 계산
    var tipX = centerX + radius * Math.cos(angleRad);
    var tipY = centerY + radius * Math.sin(angleRad);

    var leftX = centerX + (radius - 6) * Math.cos(angleRad) - 4 * Math.sin(angleRad);
    var leftY = centerY + (radius - 6) * Math.sin(angleRad) + 4 * Math.cos(angleRad);

    var rightX = centerX + (radius - 6) * Math.cos(angleRad) + 4 * Math.sin(angleRad);
    var rightY = centerY + (radius - 6) * Math.sin(angleRad) - 4 * Math.cos(angleRad);

    // 삼각형 그리기
    ctx.beginPath();
    ctx.moveTo(tipX, tipY);
    ctx.lineTo(leftX, leftY);
    ctx.lineTo(rightX, rightY);
    ctx.closePath();
    ctx.fillStyle = '#ffffff';
    ctx.fill();

    // 이미지 URL 생성
    var imageUrl = canvas.toDataURL();

    // 네이버 맵 아이콘 객체 생성
    return {
        url: imageUrl,
        size: new naver.maps.Size(canvasSize, canvasSize),
        anchor: new naver.maps.Point(canvasSize / 2, canvasSize / 2),
        origin: new naver.maps.Point(0, 0)
    };
}

/**
 * 차량 정보 인포윈도우 내용 생성 함수
 * @param {number} id - 차량 ID
 * @param {number} speed - 차량 속도 (km/h)
 * @param {number} heading - 차량 진행 방향 (도)
 * @param {boolean} isCollisionRisk - 충돌 위험 여부
 * @param {number|null} ttc - 충돌까지 남은 시간 (초)
 * @returns {string} 인포윈도우 HTML 콘텐츠
 */
function createVehicleInfoWindowContent(id, speed, heading, isCollisionRisk, ttc) {
    var content = '<div style="padding:5px;width:150px;text-align:center;">';
    content += '<strong>차량 ID: ' + id + '</strong><br>';
    content += '속도: ' + speed.toFixed(1) + ' km/h<br>';
    content += '방향: ' + heading.toFixed(1) + '°<br>';

    if (isCollisionRisk) {
        if (ttc === 0) {
            content += '<span style="color:red;font-weight:bold;">충돌 중!</span>';
        } else {
            content += '<span style="color:red;font-weight:bold;">' + ttc.toFixed(1) + '초 후 충돌 예상</span>';
        }
    } else {
        content += '<span style="color:green;">안전</span>';
    }

    content += '</div>';

    return content;
}

/**
 * 차량 직사각형 업데이트 함수
 * @param {number} id - 차량 ID
 * @param {Object|null} rectangle - 직사각형 GeoJSON 객체
 * @param {boolean} isCollisionRisk - 충돌 위험 여부
 */
function updateVehicleRectangle(id, rectangle, isCollisionRisk) {
    // 직사각형 정보가 없는 경우 종료
    if (!rectangle) return;

    // 직사각형 좌표 변환
    var path = rectangle.geometry.coordinates[0].map(function (coord) {
        return new naver.maps.LatLng(coord[1], coord[0]); // GeoJSON은 [경도, 위도] 순서
    });

    // 직사각형 스타일
    var strokeColor = isCollisionRisk ? '#ff4444' : '#4285F4';
    var fillColor = isCollisionRisk ? 'rgba(255, 68, 68, 0.2)' : 'rgba(66, 133, 244, 0.2)';

    // 저장 구조 초기화
    if (!(id in vehiclePaths)) {
        vehiclePaths[id] = {};
    }

    // 기존 직사각형이 있는지 확인
    if (vehiclePaths[id].rectangle) {
        // 직사각형 경로 업데이트
        vehiclePaths[id].rectangle.setPath(path);

        // 스타일 업데이트
        vehiclePaths[id].rectangle.setOptions({
            strokeColor: strokeColor,
            fillColor: fillColor
        });
    } else {
        // 새 직사각형 생성
        var polygon = new naver.maps.Polygon({
            paths: path,
            strokeWeight: 2,
            strokeColor: strokeColor,
            strokeOpacity: 0.8,
            fillColor: fillColor,
            fillOpacity: 0.5,
            map: map
        });

        vehiclePaths[id].rectangle = polygon;
    }
}

/**
 * 차량 경로 업데이트 함수
 * @param {Array} paths - 경로 GeoJSON 객체 배열
 */
function updateVehiclePaths(paths) {
    if (!paths) return;

    paths.forEach(function (pathData) {
        var id = pathData.properties.vehicle_id;

        // 경로 좌표 변환
        var pathCoords = pathData.geometry.coordinates.map(function (coord) {
            return new naver.maps.LatLng(coord[1], coord[0]); // GeoJSON은 [경도, 위도] 순서
        });

        // 예측 경로 좌표 변환
        var predictedPathCoords = null;
        if (pathData.predicted_path) {
            predictedPathCoords = pathData.predicted_path.geometry.coordinates.map(function (coord) {
                return new naver.maps.LatLng(coord[1], coord[0]);
            });
        }

        // 저장 구조 초기화
        if (!(id in vehiclePaths)) {
            vehiclePaths[id] = {};
        }

        // 이동 경로 업데이트/생성
        if (pathCoords.length > 0) {
            if (vehiclePaths[id].path) {
                vehiclePaths[id].path.setPath(pathCoords);
            } else {
                vehiclePaths[id].path = new naver.maps.Polyline({
                    path: pathCoords,
                    strokeWeight: 3,
                    strokeColor: '#4285F4',
                    strokeOpacity: 0.8,
                    map: map
                });
            }
        }

        // 예측 경로 업데이트/생성
        if (predictedPathCoords && predictedPathCoords.length > 0) {
            if (vehiclePaths[id].predictedPath) {
                vehiclePaths[id].predictedPath.setPath(predictedPathCoords);
            } else {
                vehiclePaths[id].predictedPath = new naver.maps.Polyline({
                    path: predictedPathCoords,
                    strokeWeight: 2,
                    strokeColor: '#4285F4',
                    strokeOpacity: 0.5,
                    strokeStyle: 'dashed',
                    map: map
                });
            }
        }
    });
}

/**
 * 충돌 지점 마커 업데이트 함수
 * @param {Array} collisions - 충돌 GeoJSON 객체 배열
 */
function updateCollisionMarkers(collisions) {
    // 현재 표시된 모든 충돌 ID 추적
    var currentCollisionIds = new Set();

    // 각 충돌 마커 업데이트/생성
    collisions.forEach(function (collision) {
        var id = collision.properties.id;
        currentCollisionIds.add(id);

        var lat = collision.geometry.coordinates[1]; // GeoJSON은 [경도, 위도] 순서
        var lng = collision.geometry.coordinates[0];
        var position = new naver.maps.LatLng(lat, lng);

        // 충돌 정보
        var vehicleIds = collision.properties.vehicle_ids;
        var ttc = collision.properties.ttc;

        // 충돌 지점 아이콘 스타일
        var iconUrl = createCollisionMarkerImageUrl(ttc < 1.0); // 1초 이내 충돌 예상 시 맥동 효과

        // 기존 마커가 있는지 확인
        if (id in collisionMarkers) {
            // 마커 위치 업데이트
            collisionMarkers[id].setPosition(position);

            // 아이콘 업데이트
            collisionMarkers[id].setIcon({
                url: iconUrl,
                size: new naver.maps.Size(32, 32),
                anchor: new naver.maps.Point(16, 16)
            });

            // 인포윈도우 내용 업데이트
            if (id in infoWindows) {
                infoWindows[id].setContent(createCollisionInfoWindowContent(id, vehicleIds, ttc));
            }
        } else {
            // 새 마커 생성
            var marker = new naver.maps.Marker({
                position: position,
                map: map,
                title: '충돌 지점: ' + id,
                icon: {
                    url: iconUrl,
                    size: new naver.maps.Size(32, 32),
                    anchor: new naver.maps.Point(16, 16)
                },
                zIndex: 150
            });

            // 충돌 정보 표시 인포윈도우 생성
            var infoWindow = new naver.maps.InfoWindow({
                content: createCollisionInfoWindowContent(id, vehicleIds, ttc),
                maxWidth: 200,
                backgroundColor: "#fff",
                borderColor: "#f00",
                borderWidth: 2,
                anchorSize: new naver.maps.Size(10, 10),
                pixelOffset: new naver.maps.Point(10, -10)
            });

            // 마커 클릭 이벤트 - 인포윈도우 토글
            naver.maps.Event.addListener(marker, 'click', function () {
                if (marker.infoWindowOpen) {
                    infoWindow.close();
                    marker.infoWindowOpen = false;
                } else {
                    infoWindow.open(map, marker);
                    marker.infoWindowOpen = true;
                }
            });

            // 마커와 인포윈도우 저장
            marker.infoWindowOpen = false;
            collisionMarkers[id] = marker;
            infoWindows[id] = infoWindow;
        }
    });

    // 더 이상 존재하지 않는 충돌 마커 제거
    Object.keys(collisionMarkers).forEach(function (id) {
        if (!currentCollisionIds.has(id)) {
            collisionMarkers[id].setMap(null);
            delete collisionMarkers[id];

            // 관련 인포윈도우 제거
            if (id in infoWindows) {
                infoWindows[id].close();
                delete infoWindows[id];
            }
        }
    });
}

/**
 * 충돌 마커 이미지 URL 생성 함수
 * @param {boolean} pulse - 맥동 효과 여부
 * @returns {string} 이미지 URL
 */
function createCollisionMarkerImageUrl(pulse) {
    // 충돌 지점 마커 이미지 생성
    var size = 16;
    var canvas = document.createElement('canvas');
    canvas.width = size * 2;
    canvas.height = size * 2;
    var ctx = canvas.getContext('2d');

    // 배경 지우기
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 중심점
    var centerX = canvas.width / 2;
    var centerY = canvas.height / 2;

    // 충돌 지점 그리기 (X 표시)
    ctx.beginPath();

    // X 그리기
    ctx.moveTo(centerX - size / 2, centerY - size / 2);
    ctx.lineTo(centerX + size / 2, centerY + size / 2);
    ctx.moveTo(centerX + size / 2, centerY - size / 2);
    ctx.lineTo(centerX - size / 2, centerY + size / 2);

    ctx.strokeStyle = '#ff0000';
    ctx.lineWidth = 3;
    ctx.stroke();

    // 원 그리기
    ctx.beginPath();
    ctx.arc(centerX, centerY, size / 2, 0, 2 * Math.PI);
    ctx.fillStyle = 'rgba(255, 0, 0, 0.3)';
    ctx.fill();
    ctx.strokeStyle = '#ff0000';
    ctx.lineWidth = 2;
    ctx.stroke();

    // 이미지 URL 생성
    return canvas.toDataURL();
}

/**
 * 충돌 정보 인포윈도우 내용 생성 함수
 * @param {string} id - 충돌 ID
 * @param {Array} vehicleIds - 충돌 관련 차량 ID 배열
 * @param {number} ttc - 충돌까지 남은 시간 (초)
 * @returns {string} 인포윈도우 HTML 콘텐츠
 */
function createCollisionInfoWindowContent(id, vehicleIds, ttc) {
    var content = '<div style="padding:5px;width:150px;text-align:center;">';
    content += '<strong>충돌 예측</strong><br>';
    content += '차량: ' + vehicleIds.join(' & ') + '<br>';

    if (ttc === 0) {
        content += '<span style="color:red;font-weight:bold;">충돌 중!</span>';
    } else {
        content += '<span style="color:red;font-weight:bold;">' + ttc.toFixed(1) + '초 후 충돌 예상</span>';
    }

    content += '</div>';

    return content;
}