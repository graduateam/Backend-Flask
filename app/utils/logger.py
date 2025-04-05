"""
중앙 집중식 로깅 설정 모듈
애플리케이션 전체의 로그 설정을 관리
"""
import logging
import os

# 로그 레벨 설정 (환경 변수 또는 기본값)
# LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG').upper()
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def setup_logger(name):
    """
    지정된 이름으로 로거를 설정하고 반환

    Parameters:
    name: str - 로거 이름 (보통 __name__ 사용)

    Returns:
    logging.Logger - 설정된 로거 객체
    """
    logger = logging.getLogger(name)

    # 이미 핸들러가 설정되어 있으면 중복 방지
    if logger.handlers:
        return logger

    # 로그 레벨 설정
    level = getattr(logging, LOG_LEVEL)
    logger.setLevel(level)

    # 부모 로거로의 전파 중지
    logger.propagate = False

    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console_handler)

    return logger


# 기본 로거 설정
def setup_root_logger():
    """애플리케이션 루트 로거 설정"""

    # 기존 핸들러 제거
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT
    )