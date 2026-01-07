from fastapi.security import OAuth2PasswordBearer
from fastapi import status
from loguru import logger
from fastapi.exceptions import HTTPException
from pycountry import countries

# Инициализация OAuth2 схем
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
oauth2_optional_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def validate_country_code(code: str) -> str:
    """
    Валидирует код страны по стандарту ISO 3166-1 alpha-2.

    Args:
        code: Код страны (2 символа)

    Returns:
        str: Валидный код страны в верхнем регистре

    Raises:
        HTTPException: Если код страны невалидный или неизвестный
    """
    logger.debug(f"Валидация кода страны: {code}")

    if not isinstance(code, str) or len(code) != 2 or not code.isalpha():
        error_msg = "Код страны должен состоять из 2 латинских букв (ISO 3166-1 alpha-2)"
        logger.warning(f"Неверный формат кода страны: {code}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    normalized_code = code.upper()

    if not countries.get(alpha_2=normalized_code):
        error_msg = f"Неизвестный код страны ISO 3166-1 alpha-2: {code}"
        logger.warning(error_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    logger.debug(f"Код страны {code} успешно валидирован")
    return normalized_code