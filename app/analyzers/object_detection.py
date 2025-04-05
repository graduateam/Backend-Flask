"""
YOLO 객체 감지 모델을 사용한 객체 탐지 및 추적
"""
import cv2
from ultralytics import YOLO
import torch
import time
from app.utils.coord_utils import CoordinateTransformer

class ObjectDetector:
    def __init__(self, model_path, image_points, world_points, device=None):
        """
        객체 감지 및 추적 모델 초기화

        Parameters:
        model_path: str - YOLO 모델 파일 경로 (예: 'runs/detect/train5/weights/best.pt')
        image_points: list - 이미지 상의 픽셀 좌표 [(x1, y1), ...]
        world_points: list - 실제 세계 좌표 [(lat1, lon1), ...]
        device: str - 사용할 장치 ('cuda' 또는 'cpu', None일 경우 자동 감지)
        """
        # 사용할 장치 설정
        self.device = device if device else ('cuda' if torch.cuda.is_available() else 'cpu')

        # YOLO 모델 로드
        self.model = YOLO(model_path).to(self.device)

        # 좌표 변환기 초기화
        self.transformer = CoordinateTransformer(image_points, world_points)

        # 객체 클래스 이름 설정 (필요시 업데이트)
        self.class_names = {
            0: "car",
            1: "person",
            # 필요한 경우 추가 클래스 정의
        }

    def detect_objects(self, frame, persist=True):
        """
        영상 프레임에서 객체 감지 및 추적 수행

        Parameters:
        frame: np.array - 영상 프레임
        persist: bool - 객체 ID 유지 여부 (추적 활성화)

        Returns:
        list - 감지된 객체 목록 [{'id': int, 'bbox': [x1, y1, x2, y2], 'class_id': int, 'coords': (lat, lon), 'center': (x, y)}]
        """
        # 시작 시간 측정
        start_time = time.time()

        # 객체 감지 수행
        results = self.model.track(frame, persist=persist) if persist else self.model(frame)

        # 감지된 객체 정보 추출
        detected_objects = []

        for obj in results[0].boxes:
            # 객체 ID 추출 (추적 모드에서만 제공)
            obj_id = int(obj.id) if hasattr(obj, 'id') and obj.id is not None else -1

            # 고유 ID가 없는 객체는 건너뜀
            if obj_id < 0 and persist:
                continue

            # 바운딩 박스 좌표 추출
            bbox = obj.xyxy.cpu().numpy()[0]

            # 클래스 ID 추출
            class_id = int(obj.cls) if hasattr(obj, 'cls') else -1

            # 바운딩 박스의 중앙 좌표 계산
            center_x = int((bbox[0] + bbox[2]) / 2)
            center_y = int((bbox[1] + bbox[3]) / 2)

            # 이미지 좌표를 GPS 좌표로 변환
            lat, lon = self.transformer.image_to_world((center_x, center_y))

            # 객체 정보 저장
            detected_objects.append({
                'id': obj_id,
                'bbox': bbox.tolist(),
                'class_id': class_id,
                'class_name': self.class_names.get(class_id, "unknown"),
                'center': (center_x, center_y),
                'coords': (lat, lon),
                'detection_time': time.time(),
                'processing_time': time.time() - start_time
            })

        return detected_objects

    def process_video_stream(self, video_source, callback, max_frames=None, skip_frames=0):
        """
        비디오 소스에서 객체 감지 및 추적 수행

        Parameters:
        video_source: str/int - 비디오 파일 경로 또는 카메라 ID
        callback: function - 각 프레임의 객체 감지 결과를 처리할 콜백 함수
        max_frames: int - 처리할 최대 프레임 수 (None이면 무제한)
        skip_frames: int - 몇 프레임마다 한 번씩 처리할지 (0이면 모든 프레임 처리)

        Returns:
        dict - 처리 결과 통계
        """
        # 비디오 소스 열기
        cap = cv2.VideoCapture(video_source)

        # 통계 변수 초기화
        frames_processed = 0
        total_objects_detected = 0
        total_processing_time = 0
        frame_count = 0

        # 전체 시작 시간
        start_time = time.time()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # 프레임 스킵
            if skip_frames > 0 and (frame_count - 1) % (skip_frames + 1) != 0:
                continue

            # 객체 감지 수행
            objects = self.detect_objects(frame)
            total_objects_detected += len(objects)

            # 처리 시간 계산
            frame_processing_time = objects[0]['processing_time'] if objects else 0
            total_processing_time += frame_processing_time

            # 콜백 함수 호출
            if callback:
                callback(frame, objects, frame_count)

            frames_processed += 1

            # 최대 프레임 수에 도달한 경우 종료
            if max_frames and frames_processed >= max_frames:
                break

        # 비디오 소스 닫기
        cap.release()

        # 전체 처리 시간
        total_time = time.time() - start_time

        # 처리 결과 통계
        stats = {
            'total_time': total_time,
            'frames_processed': frames_processed,
            'avg_fps': frames_processed / total_time if total_time > 0 else 0,
            'total_objects_detected': total_objects_detected,
            'avg_objects_per_frame': total_objects_detected / frames_processed if frames_processed > 0 else 0,
            'avg_processing_time_per_frame': total_processing_time / frames_processed if frames_processed > 0 else 0
        }

        return stats