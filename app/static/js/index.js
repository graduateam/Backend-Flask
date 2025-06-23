/**
 * 차량 충돌 예측 시스템 메인 페이지 JavaScript
 */

// 위험도 레벨 설정
const RISK_LEVELS = {
    SAFE: { min: 0, max: 40, color: '#28a745', label: '안전' },
    LOW: { min: 40, max: 55, color: '#ffc107', label: '낮음' },
    MEDIUM: { min: 55, max: 70, color: '#fd7e14', label: '중간' },
    HIGH: { min: 70, max: 85, color: '#dc3545', label: '높음' },
    CRITICAL: { min: 85, max: 100, color: '#6f42c1', label: '치명적' }
};

// 전역 변수
let currentRiskSummary = {};
let riskHistory = []; // 위험도 이력 저장

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

    // 위험도 표시 영역 초기화
    initRiskDisplays();

    // 페이지 로드 시 자동으로 처리 시작
    startProcessing();

    // 위험도 이력 차트 초기화 (선택적)
    initRiskChart();
});

// 위험도 표시 영역 초기화
function initRiskDisplays() {
    // 전체 위험도 표시 영역 추가
    if ($('#overallRiskDisplay').length === 0) {
        const riskDisplayHtml = `
            <div class="card mb-3" id="overallRiskCard">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">전체 위험도</h5>
                    <div id="riskIndicator" class="badge badge-success">안전</div>
                </div>
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="text-muted">위험도 점수</span>
                        <span id="riskScore" class="font-weight-bold">0점</span>
                    </div>
                    <div class="progress mb-2" style="height: 10px;">
                        <div id="riskProgressBar" class="progress-bar bg-success" 
                             role="progressbar" style="width: 0%" 
                             aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <div class="d-flex justify-content-between">
                        <small class="text-muted">활성 경고</small>
                        <small id="activeWarnings" class="font-weight-bold">0개</small>
                    </div>
                </div>
            </div>
        `;
        $('.left-panel h1').after(riskDisplayHtml);
    }
}

// 위험도 차트 초기화 (간단한 선 그래프)
function initRiskChart() {
    // 차트 라이브러리가 있다면 여기서 초기화
    // 지금은 간단한 텍스트 기반 이력만 표시
    riskHistory = [];
}

// 카메라 소스 목록 가져오기
function fetchCameraSources() {
    $.get('/api/camera-sources', function(response) {
        if (response.success) {
            var $select = $('#cameraSourceSelect');
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
    socket.emit('start_stream', {quality: 'high'});
});

// 지도 업데이트 이벤트 처리
socket.on('map_update', function (data) {
    console.log('지도 데이터 수신');
    try {
        var mapData = typeof data === 'string' ? JSON.parse(data) : data;
        console.log('파싱된 데이터:', {
            '차량 수': mapData.vehicles ? mapData.vehicles.length : 0,
            '충돌 수': mapData.collisions ? mapData.collisions.length : 0,
            '위험도 세부사항': mapData.risk_details ? Object.keys(mapData.risk_details).length : 0
        });

        // 감지된 객체 목록 업데이트
        if (mapData.vehicles && mapData.vehicles.length > 0) {
            updateDetectedObjectsList(mapData.vehicles, mapData.risk_details);
        }

        // 전체 위험도 업데이트
        updateOverallRiskDisplay(mapData);

        // 지도 및 충돌 경고 업데이트
        updateMap(mapData);
        updateCollisionWarnings(mapData.collisions, mapData.risk_details);

    } catch (error) {
        console.error('지도 데이터 파싱 오류:', error);
    }
});

// WebSocket 비디오 스트리밍 처리
(function () {
    const canvas = document.getElementById('videoCanvas');
    const ctx = canvas.getContext('2d');

    socket.on('video_frame', function (data) {
        const img = new Image();
        img.onload = function () {
            if (canvas.width !== this.width || canvas.height !== this.height) {
                canvas.width = this.width;
                canvas.height = this.height;
            }
            ctx.drawImage(img, 0, 0);
        };
        img.src = 'data:image/jpeg;base64,' + data.frame;
    });
})();

// 전체 위험도 표시 업데이트
function updateOverallRiskDisplay(mapData) {
    // 전체 위험도 계산
    let maxRisk = 0;
    let totalWarnings = 0;
    let riskStatus = 'SAFE';

    if (mapData.collisions && mapData.collisions.length > 0) {
        totalWarnings = mapData.collisions.length;

        // 최대 위험도 찾기
        mapData.collisions.forEach(function(collision) {
            const risk = collision.properties.risk_score || 0;
            maxRisk = Math.max(maxRisk, risk);
        });
    }

    // 위험도 레벨 결정
    for (const [level, config] of Object.entries(RISK_LEVELS)) {
        if (maxRisk >= config.min && maxRisk <= config.max) {
            riskStatus = level;
            break;
        }
    }

    const riskConfig = RISK_LEVELS[riskStatus];

    // UI 업데이트
    $('#riskScore').text(maxRisk.toFixed(1) + '점');
    $('#activeWarnings').text(totalWarnings + '개');

    // 위험도 표시기 업데이트
    const $indicator = $('#riskIndicator');
    $indicator.text(riskConfig.label)
             .removeClass('badge-success badge-warning badge-danger badge-secondary badge-primary')
             .addClass(getBadgeClass(riskStatus));

    // 진행률 바 업데이트
    const $progressBar = $('#riskProgressBar');
    $progressBar.css('width', maxRisk + '%')
                .removeClass('bg-success bg-warning bg-danger bg-secondary bg-primary')
                .addClass(getProgressBarClass(riskStatus));

    // 위험도 이력 저장
    const now = new Date();
    riskHistory.push({
        timestamp: now.toLocaleTimeString(),
        risk: maxRisk,
        warnings: totalWarnings,
        status: riskStatus
    });

    // 이력은 최근 50개만 유지
    if (riskHistory.length > 50) {
        riskHistory.shift();
    }

    // 전역 위험도 요약 업데이트
    currentRiskSummary = {
        maxRisk: maxRisk,
        totalWarnings: totalWarnings,
        status: riskStatus,
        timestamp: now
    };
}

// 위험도에 따른 Badge 클래스 반환
function getBadgeClass(riskStatus) {
    const classMap = {
        'SAFE': 'badge-success',
        'LOW': 'badge-warning',
        'MEDIUM': 'badge-warning',
        'HIGH': 'badge-danger',
        'CRITICAL': 'badge-primary'
    };
    return classMap[riskStatus] || 'badge-secondary';
}

// 위험도에 따른 Progress Bar 클래스 반환
function getProgressBarClass(riskStatus) {
    const classMap = {
        'SAFE': 'bg-success',
        'LOW': 'bg-warning',
        'MEDIUM': 'bg-warning',
        'HIGH': 'bg-danger',
        'CRITICAL': 'bg-primary'
    };
    return classMap[riskStatus] || 'bg-secondary';
}

// 객체 정보 표시
function updateDetectedObjectsList(vehicles, riskDetails) {
    var $objectsList = $('#detectedObjectsList');
    $objectsList.empty();

    if (!vehicles || vehicles.length === 0) {
        $objectsList.append('<tr><td colspan="5" class="text-center">감지된 객체가 없습니다</td></tr>');
        return;
    }

    // 테이블 헤더 업데이트
    const $tableHead = $objectsList.closest('table').find('thead tr');
    if ($tableHead.find('th').length === 4) {
        $tableHead.append('<th>위험도</th>');
    }

    // 객체 정보 테이블
    vehicles.forEach(function (vehicle) {
        var id = vehicle.properties.id;
        var lat = vehicle.geometry.coordinates[1].toFixed(6);
        var lon = vehicle.geometry.coordinates[0].toFixed(6);
        var speed = vehicle.properties.speed_kph.toFixed(1);

        // 해당 객체의 최대 위험도 찾기
        let maxRiskForObject = 0;
        let riskLevel = 'SAFE';

        if (riskDetails) {
            Object.entries(riskDetails).forEach(([pairKey, details]) => {
                const [id1, id2] = pairKey.split(',').map(id => parseInt(id));
                if (id === id1 || id === id2) {
                    const risk = details.total_risk || 0;
                    if (risk > maxRiskForObject) {
                        maxRiskForObject = risk;
                    }
                }
            });
        }

        // 위험도 레벨 결정
        for (const [level, config] of Object.entries(RISK_LEVELS)) {
            if (maxRiskForObject >= config.min && maxRiskForObject <= config.max) {
                riskLevel = level;
                break;
            }
        }

        const rowClass = maxRiskForObject >= 60 ? 'table-danger' :
                        maxRiskForObject >= 40 ? 'table-warning' : '';

        const riskDisplay = maxRiskForObject > 0 ?
            `<span class="badge" style="background-color: ${RISK_LEVELS[riskLevel].color}">
                ${maxRiskForObject.toFixed(1)}점
            </span>` :
            '<span class="badge badge-success">안전</span>';

        var row = '<tr class="' + rowClass + '">' +
            '<td>' + id + '</td>' +
            '<td>' + lat + '</td>' +
            '<td>' + lon + '</td>' +
            '<td>' + speed + '</td>' +
            '<td>' + riskDisplay + '</td>' +
            '</tr>';

        $objectsList.append(row);
    });

    // 객체 수 업데이트
    $('#objectCount').text(vehicles.length);
}

// 충돌 경고 업데이트 함수
function updateCollisionWarnings(collisions, riskDetails) {
    var $warningsContainer = $('#collisionWarnings');
    var collisionCount = 0;

    // 시간이 지난 알림은 제거
    $warningsContainer.find('.collision-alert').each(function () {
        var timestamp = $(this).data('timestamp');
        if (timestamp && (Date.now() - timestamp > 8000)) { // 8초로 증가
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

    // 충돌 알림 - 위험도 기반
    collisions.forEach(function (collision) {
        const riskScore = collision.properties.risk_score || 0;
        const vehicleIds = collision.properties.vehicle_ids;
        const ttc = collision.properties.ttc;

        // 위험도에 따른 경고 레벨 결정
        let severity, riskLevel;
        for (const [level, config] of Object.entries(RISK_LEVELS)) {
            if (riskScore >= config.min && riskScore <= config.max) {
                riskLevel = level;
                break;
            }
        }

        // Bootstrap 경고 클래스 매핑
        const severityMap = {
            'SAFE': 'info',
            'LOW': 'warning',
            'MEDIUM': 'warning',
            'HIGH': 'danger',
            'CRITICAL': 'danger'
        };
        severity = severityMap[riskLevel] || 'info';

        collisionCount++;

        // TTC 텍스트 처리
        var ttcText = ttc === 0 ? '0.0초' : ttc.toFixed(1) + '초';

        // 차량 ID 포맷팅
        var formattedVehicleIds = '<span class="vehicle-id">' +
            vehicleIds.join('</span> & <span class="vehicle-id">') + '</span>';

        var currentTime = new Date().toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        // 위험도 세부 정보 툴팁 생성
        let detailsTooltip = '';
        const pairKey = vehicleIds.sort().join(',');
        if (riskDetails && riskDetails[pairKey]) {
            const details = riskDetails[pairKey];
            detailsTooltip = `title="거리: ${details.distance_risk.toFixed(1)}점 | 상대속도: ${details.relative_speed_risk.toFixed(1)}점 | 방향수렴: ${details.convergence_risk.toFixed(1)}점 | 시간: ${details.time_risk.toFixed(1)}점"`;
        }

        // 이미 표시된 알림인지 확인
        var collisionId = 'collision_' + collision.properties.id;
        if ($warningsContainer.find('#' + collisionId).length === 0) {
            var warningHtml = '<div id="' + collisionId + '" class="alert alert-' + severity + ' collision-alert" data-timestamp="' + Date.now() + '" ' + detailsTooltip + '>' +
                '<div class="alert-time">' + currentTime + '</div>' +
                '<div class="vehicle-info">' + formattedVehicleIds + '</div>' +
                '<div class="risk-score-info">위험도: <strong>' + riskScore.toFixed(1) + '점</strong></div>' +
                '<div class="ttc-info">' + ttcText + '</div>' +
                '</div>';

            $warningsContainer.prepend(warningHtml);

            // 8초 후 자동 제거
            setTimeout(function () {
                $('#' + collisionId).fadeOut('slow', function () {
                    $(this).remove();

                    if ($warningsContainer.find('.collision-alert').length === 0) {
                        $warningsContainer.html('<div class="alert alert-info">충돌 감지되지 않음</div>');
                    }
                });
            }, 8000);
        }
    });

    // 충돌 경고 수 업데이트
    $('#collisionCount').text(collisionCount);
}