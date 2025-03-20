import time
import cv2
import torch
import numpy as np
from ultralytics import YOLO
from flask import Flask, Response, render_template

app = Flask(__name__)

# YOLO 모델 로드 (GPU 사용 설정)
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = YOLO('yolo_model/0317_best.pt').to(device)

# COCO 데이터셋에서 사람과 차량 관련 클래스 ID
TARGET_CLASSES = [0, 2, 3, 5]  # 사람(0), 자동차(2), 오토바이(3), 버스(5)

# 이미지 좌표 (픽셀 좌표)
image_points = np.array([
    [335, 102],
    [23, 251],
    [584, 234],
    [146, 404]
], dtype=np.float32)

# 실제 세계 좌표 (위도, 경도)
world_points = np.array([
    [37.67675942, 126.74583666],
    [37.67696082, 126.74597894],
    [37.67687015, 126.74558537],
    [37.67703350, 126.74581464]
], dtype=np.float32)

# Homography 행렬 계산
H, status = cv2.findHomography(image_points, world_points)

# 이미지 좌표를 실세계 좌표로 변환하는 함수
def convert_image_to_world(image_coords, homography_matrix):
    image_coords_homogeneous = np.array([image_coords[0], image_coords[1], 1]).reshape(3, 1)
    world_coords_homogeneous = np.dot(homography_matrix, image_coords_homogeneous)
    world_coords = world_coords_homogeneous / world_coords_homogeneous[2]
    lat = world_coords[0][0]
    lon = world_coords[1][0]
    return lat, lon

@app.route('/')
def index():
    """ 웹 페이지 렌더링 """
    return render_template('index.html')

@app.route('/detect_stream')
def detect_stream():
    """
    YOLO 탐지 결과를 실시간으로 스트리밍
    """
    def generate():
        video_path = "C:/Users/user/YOLO/video/ilsan.mp4"
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            yield "data: {}\n\n".format('{"error": "Cannot open video file"}')

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            results = model.track(frame, classes=TARGET_CLASSES, persist=True)

            for obj in results[0].boxes:
                obj_id = int(obj.id) if obj.id is not None else -1
                bbox = obj.xyxy.cpu().numpy()[0]

                center_x = int((bbox[0] + bbox[2]) / 2)
                center_y = int((bbox[1] + bbox[3]) / 2)

                lat, lon = convert_image_to_world([center_x, center_y], H)
                timestamp = time.time()

                # 클라이언트에게 실시간으로 JSON 데이터 전송
                yield f"data: {{"f'"id": {obj_id}, "latitude": {lat}, "longitude": {lon}, "timestamp": {timestamp}'"}}\n\n"

            time.sleep(0.1)  # 데이터 전송 속도를 조절

        cap.release()

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
