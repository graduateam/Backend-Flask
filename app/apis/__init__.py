"""
API 모듈 패키지
RESTful API 엔드포인트 정의
"""
from app.apis.api import api_bp

# 모든 API 블루프린트 목록
blueprints = [api_bp]

# 모듈 공개 API
__all__ = ['api_bp', 'blueprints']