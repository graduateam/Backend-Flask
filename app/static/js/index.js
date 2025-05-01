/**
 * 차량 충돌 예측 시스템 메인 페이지 JavaScript
 */

// 문서 로드 완료 시 실행
$(document).ready(function () {
    // 지도 초기화
    console.log("지도 초기화 시작, 중심 좌표:", mapCenter);
    initMap(mapCenter);
    console.log("지도 초기화 완료");

    // 체크박스 초기 상태 설정
    $('#showVideoBounds').prop('checked', true);

    // 카메라 소스 선택 이벤트 처리
    $('#cameraSourceSelect').change(function() {
        var selectedSource = $(this).val();
        changeVideoSource(selectedSource);
    });

    // 페이지 로드 시 서버에서 사용 가능한 카메라 소스 목록을 가져오기
    fetchCameraSources();

    // 페이지 로드 시 자동으로 처리 시작
    startProcessing();
});

// 카메라 소스 목록 가져오기
function fetchCameraSources() {
    $.get('/api/camera-sources', function(response) {
        if (response.success) {
            var $select = $('#cameraSourceSelect');

            // 소스 목록 갱신 (옵션: 서버에서 템플릿으로 이미 전달되므로 생략 가능)
            // $select.empty();
            // response.sources.forEach(function(source) {
            //     $select.append(`<option value="${source.id}">${source.name}</option>`);
            // });

            // 현재 소스 선택
            $select.val(response.current_source);

            console.log('카메라 소스 목록 로드 완료, 현재 소스:', response.current_source);
        } else {
            console.error('카메라 소스 목록 로드 실패:', response.message);
        }
    }).fail(function(error) {
        console.error('카메라 소스 요청 실패:', error);
    });
}

// 처리 자동 시작 함수
function startProcessing() {
    console.log('처리 자동 시작 중...');
    $.get('/api/start-processing', function (data) {
        console.log('처리 시작 응답:', data);
        if (data.success) {
            // 비디오 경계 업데이트
            updateVideoBounds();
            console.log(data.message);
        } else {
            console.error('오류:', data.message);
        }
    }).fail(function (error) {
        console.error('처리 시작 요청 실패:', error);
    });
}

// 비디오 소스 변경 함수
function changeVideoSource(source) {
    console.log('비디오 소스 변경 중...', source);

    $.ajax({
        url: '/api/change-source',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ source: source }),
        success: function(response) {
            console.log('소스 변경 응답:', response);
            if (response.success) {
                console.log(response.message);
                // 비디오 경계 업데이트
                updateVideoBounds();
            } else {
                console.error('소스 변경 오류:', response.message);
            }
        },
        error: function(error) {
            console.error('소스 변경 요청 실패:', error);
        }
    });
}

// 처리 자동 시작 함수
function startProcessing() {
    console.log('처리 자동 시작 중...');
    $.get('/api/start-processing', function (data) {
        console.log('처리 시작 응답:', data);
        if (data.success) {
            // 비디오 경계 업데이트
            updateVideoBounds();
            console.log(data.message);
        } else {
            console.error('오류:', data.message);
        }
    }).fail(function (error) {
        console.error('처리 시작 요청 실패:', error);
    });
}

// 비디오 소스 변경 함수
function changeVideoSource(source) {
    console.log('비디오 소스 변경 중...', source);

    $.ajax({
        url: '/api/change-source',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ source: source }),
        success: function(response) {
            console.log('소스 변경 응답:', response);
            if (response.success) {
                console.log(response.message);
                // 비디오 경계 업데이트
                updateVideoBounds();
            } else {
                console.error('소스 변경 오류:', response.message);
            }
        },
        error: function(error) {
            console.error('소스 변경 요청 실패:', error);
        }
    });
}

// Socket.IO 연결
var socket = io();
socket.on('connect', function () {
    console.log('Socket.IO 연결됨');
    // 연결 시 스트리밍 시작 요청
    socket.emit('start_stream', {quality: 'high'});
});

// 지도 업데이트 이벤트 처리
socket.on('map_update', function (data) {
    console.log('지도 데이터 수신');
    try {
        var mapData = typeof data === 'string' ? JSON.parse(data) : data;
        console.log('파싱된 데이터:', {
            '차량 수': mapData.vehicles ? mapData.vehicles.length : 0,
            '충돌 수': mapData.collisions ? mapData.collisions.length : 0
        });

        if (mapData.vehicles && mapData.vehicles.length > 0) {
            // 감지된 객체 목록 업데이트
            updateDetectedObjectsList(mapData.vehicles);
        }

        updateMap(mapData);
        updateCollisionWarnings(mapData.collisions);
    } catch (error) {
        console.error('지도 데이터 파싱 오류:', error);
    }
});

// WebSocket 비디오 스트리밍 처리
(function () {
    const canvas = document.getElementById('videoCanvas');
    const ctx = canvas.getContext('2d');

    // 비디오 프레임 처리 함수
    socket.on('video_frame', function (data) {
        // Base64 인코딩된 이미지를 Image 객체로 변환
        const img = new Image();
        img.onload = function () {
            // 캔버스 크기 조정 (첫 프레임 기준)
            if (canvas.width !== this.width || canvas.height !== this.height) {
                canvas.width = this.width;
                canvas.height = this.height;
            }
            // 이미지를 캔버스에 그리기
            ctx.drawImage(img, 0, 0);
        };
        img.src = 'data:image/jpeg;base64,' + data.frame;
    });
})();

// 객체 정보 표시
function updateDetectedObjectsList(vehicles) {
    var $objectsList = $('#detectedObjectsList');
    $objectsList.empty();

    if (!vehicles || vehicles.length === 0) {
        $objectsList.append('<tr><td colspan="4" class="text-center">감지된 객체가 없습니다</td></tr>');
        return;
    }

    // 객체 정보 테이블
    vehicles.forEach(function (vehicle) {
        var id = vehicle.properties.id;
        var lat = vehicle.geometry.coordinates[1].toFixed(6); // 위도
        var lon = vehicle.geometry.coordinates[0].toFixed(6); // 경도
        var speed = vehicle.properties.speed_kph.toFixed(1);  // 속력

        console.log("Vehicle ID:", id, "Speed:", speed, "Raw speed:", vehicle.properties.speed);

        var rowClass = vehicle.properties.is_collision_risk ? 'table-danger' : '';

        var row = '<tr class="' + rowClass + '">' +
            '<td>' + id + '</td>' +
            '<td>' + lat + '</td>' +
            '<td>' + lon + '</td>' +
            '<td>' + speed + '</td>' +
            '</tr>';

        $objectsList.append(row);
    });

    // 객체 수 업데이트
    $('#objectCount').text(vehicles.length);
}

// 충돌 경고 업데이트 함수
function updateCollisionWarnings(collisions) {
    var $warningsContainer = $('#collisionWarnings');
    var collisionCount = 0;

    // 시간이 지난 알림은 제거
    $warningsContainer.find('.collision-alert').each(function () {
        var timestamp = $(this).data('timestamp');
        if (timestamp && (Date.now() - timestamp > 5000)) {
            $(this).remove();
        }
    });

    if (!collisions || collisions.length === 0) {
        if ($warningsContainer.find('.collision-alert').length === 0) {
            $warningsContainer.html('<div class="alert alert-info">충돌 감지되지 않음</div>');
        }
        $('#collisionCount').text('0');
        return;
    }

    // "충돌 감지되지 않음" 메시지 제거
    $warningsContainer.find('.alert-info').remove();

    // 충돌 알림 추가
    collisions.forEach(function (collision) {
        var severity = collision.properties.ttc < 1.0 ? 'danger' : 'warning';
        collisionCount++;

        // 충돌 예상 시간(TTC) 처리
        var ttcText = collision.properties.ttc === 0 ? '0.0초' : collision.properties.ttc.toFixed(1) + '초';

        // 차량 ID를 별도로 포맷팅하여 각각 강조
        var vehicleIds = collision.properties.vehicle_ids;
        var formattedVehicleIds = '<span class="vehicle-id">' + vehicleIds.join('</span> & <span class="vehicle-id">') + '</span>';

        var currentTime = new Date().toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        // 이미 표시된 알림인지 확인
        var collisionId = 'collision_' + collision.properties.id;
        if ($warningsContainer.find('#' + collisionId).length === 0) {
            var warningHtml = '<div id="' + collisionId + '" class="alert alert-' + severity + ' collision-alert" data-timestamp="' + Date.now() + '">' +
                '<div class="alert-time">' + currentTime + '</div>' +
                '<div class="vehicle-info">' + formattedVehicleIds + '</div>' +
                '<div class="ttc-info">' + ttcText + '</div>' +
                '</div>';

            $warningsContainer.prepend(warningHtml);

            // 5초 후 자동 제거
            setTimeout(function () {
                $('#' + collisionId).fadeOut('slow', function () {
                    $(this).remove();

                    if ($warningsContainer.find('.collision-alert').length === 0) {
                        $warningsContainer.html('<div class="alert alert-info">충돌 감지되지 않음</div>');
                    }
                });
            }, 5000);
        }
    });

    // 충돌 경고 수 업데이트
    $('#collisionCount').text(collisionCount);
}