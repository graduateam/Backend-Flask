백엔드 Flask 애플리케이션 - YOLO 객체 인식

이 저장소는 YOLO 모델을 활용한 객체 인식을 통합하는 백엔드 Flask 애플리케이션을 포함하고 있습니다. 이 프로젝트에서 사용된 YOLO 모델은 yolo_model/0317_best.pt이며, 아래 링크에서 다운로드할 수 있습니다.


---

목차

소개

기능

설치

사용 방법

모델 정보

기여 방법

라이선스



---

소개

이 프로젝트는 YOLO (You Only Look Once) 모델을 사용하여 객체 인식을 수행하는 백엔드 솔루션을 제공합니다. Flask 프레임워크를 기반으로 구축되었으며, 가볍고 효율적인 웹 애플리케이션 환경을 제공합니다.


---

기능

✅ YOLO 모델을 활용한 객체 인식
✅ 이미지 업로드 및 예측을 위한 RESTful API 제공
✅ 다른 애플리케이션과 쉽게 통합 가능


---

설치

이 프로젝트를 시작하려면 다음 단계를 따르세요.

1. 저장소 클론

git clone https://github.com/viincci/Backend-Flask.git
cd Backend-Flask

2. 가상 환경 생성 및 활성화

python3 -m venv venv
source venv/bin/activate

3. 필수 패키지 설치

pip install -r requirements.txt

4. YOLO 모델 다운로드 및 저장

mkdir -p yolo_model
wget -O yolo_model/0317_best.pt https://github.com/graduateam/YOLO/blob/de480a760724c23bf275478c2f970919b13ba363/0317_best.pt


---

사용 방법

Flask 애플리케이션을 실행하려면 다음 명령어를 사용하세요.

flask run

애플리케이션이 http://127.0.0.1:5000/ 에서 실행됩니다. Postman 또는 cURL을 사용하여 API와 상호작용할 수 있습니다.


---

모델 정보

이 프로젝트에서 사용된 YOLO 모델은 0317_best.pt입니다. 해당 모델은 객체 인식 작업을 위해 훈련되었으며, 여기에서 다운로드할 수 있습니다.


---

기여 방법

기여를 환영합니다! 아이디어, 제안 또는 버그 보고가 있다면 이슈를 생성하거나 PR(Pull Request)을 제출해 주세요.


---

기여자

viincci

GraduaTeam



---

라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 LICENSE 파일을 참조하세요.

