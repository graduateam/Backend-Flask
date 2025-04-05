"""
뷰 모듈 패키지
웹 페이지 렌더링 관련 라우트 정의
"""
from app.views.main import main_bp

# 모든 블루프린트 목록 (자동 등록에 활용 가능)
blueprints = [main_bp]

# 모듈 공개 API
__all__ = ['main_bp', 'blueprints']