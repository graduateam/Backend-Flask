"""
인증 관련 API 엔드포인트
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta
from app.utils.logger import setup_logger

# 로거 설정
logger = setup_logger(__name__)

# 인증 블루프린트 생성 (URL 접두사 추가)
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# 사용자 데이터 (데모용 - 실제로는 데이터베이스 사용)
USERS = {
    "admin": {
        "id": 1,
        "username": "admin",
        "password": "password",  # 실제로는 해시된 암호를 저장
        "role": "ADMIN"
    }
}

def register_auth_blueprint(app):
    """
    인증 블루프린트 등록 함수

    Parameters:
    flask_app: Flask - Flask 애플리케이션 인스턴스
    """
    app.register_blueprint(auth_bp)
    logger.info('인증 API 블루프린트 등록 완료')

@auth_bp.route('/login', methods=['POST'])
def login():
    """사용자 로그인 API"""
    try:
        # 요청 데이터 확인
        if not request.is_json:
            logger.warning("로그인 요청: JSON 형식이 아님")
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "JSON 요청이 필요합니다."
                }
            }), 400

        data = request.get_json()
        username = data.get('username', '')
        password = data.get('password', '')
        
        logger.info(f"로그인 시도: 사용자={username}")

        # 사용자 존재 및 비밀번호 확인
        user = USERS.get(username)
        if not user or user['password'] != password:
            logger.warning(f"로그인 실패: 사용자={username} - 잘못된 자격 증명")
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "아이디 또는 비밀번호가 잘못되었습니다."
                }
            }), 401

        # JWT 토큰 생성
        expires = timedelta(hours=1)
        access_token = create_access_token(
            identity=username,
            additional_claims={"user_id": user["id"], "role": user["role"]},
            expires_delta=expires
        )

        # 사용자 정보 (비밀번호 제외)
        user_info = {k: v for k, v in user.items() if k != 'password'}
        
        logger.info(f"로그인 성공: 사용자={username}, 역할={user['role']}")

        return jsonify({
            "success": True,
            "data": {
                "token": access_token,
                "user": user_info
            },
            "message": f"{username} 로그인 성공"
        })

    except Exception as e:
        logger.error(f"로그인 처리 중 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": {
                "code": "SERVER_ERROR",
                "message": "서버 오류가 발생했습니다."
            }
        }), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """사용자 로그아웃 API"""
    # JWT 토큰은 클라이언트 측에서 제거하므로 서버에서 특별한 처리 필요 없음
    # 필요시 토큰 블랙리스트 구현 가능

    return jsonify({
        "success": True,
        "message": "로그아웃 성공"
    })

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """사용자 프로필 조회 API"""
    try:
        current_user = get_jwt_identity()
        user = USERS.get(current_user)
        
        if not user:
            return jsonify({
                "success": False,
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "사용자를 찾을 수 없습니다."
                }
            }), 404

        # 사용자 정보 (비밀번호 제외)
        user_info = {k: v for k, v in user.items() if k != 'password'}

        return jsonify({
            "success": True,
            "data": user_info
        })

    except Exception as e:
        logger.error(f"프로필 조회 중 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": {
                "code": "SERVER_ERROR",
                "message": "서버 오류가 발생했습니다."
            }
        }), 500