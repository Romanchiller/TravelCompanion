"""
Модуль зависимостей приложения.
Содержит все зависимости, используемые в эндпоинтах FastAPI.
"""
from typing import Optional, Generator, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from httpx import AsyncClient, Timeout
import jwt

from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import SessionLocal
from .models import User
from .tools import validate_country_code

from .di import get_container
from .services.auth_service import AuthService
from sqlalchemy import select
from loguru import logger

# Аутентификация
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
oauth2_optional_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


container = get_container()
# Database
async def get_db():
    """
    Зависимость для получения асинхронной сессии базы данных.

    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()


# HTTP Client
async def get_http_client() -> Generator[AsyncClient, None, None]:
    """
    Зависимость для получения HTTP-клиента с настройками таймаутов.
    
    Yields:
        AsyncClient: Асинхронный HTTP-клиент
    """
    timeout = Timeout(connect=15.0, read=40.0, write=15.0, pool=40.0)
    async with AsyncClient(timeout=timeout) as client:
        yield client


# Authentication
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Зависимость для получения текущего аутентифицированного пользователя.
    
    Args:
        token: JWT токен из заголовка Authorization
        db: Сессия базы данных
        
    Returns:
        User: Объект пользователя
        
    Raises:
        HTTPException: Если пользователь не аутентифицирован
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        email = payload.get("sub")
        if email is None:
            raise credentials_exception

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        # user = await db.get(User, email)
        if user is None:
            raise credentials_exception
            
        return user
        
    except jwt.InvalidTokenError:
        raise credentials_exception


async def get_optional_current_user(
    token: Annotated[Optional[str], Depends(oauth2_optional_scheme)],
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Зависимость для получения текущего пользователя, если он аутентифицирован.
    
    Args:
        token: Опциональный JWT токен
        db: Сессия базы данных
        
    Returns:
        Optional[User]: Объект пользователя или None, если не аутентифицирован
    """
    if not token:
        return None
        
    try:
        return await get_current_user(token, db)
        # payload = jwt.decode(
        #     token,
        #     settings.SECRET_KEY,
        #     algorithms=[settings.ALGORITHM]
        # )
        # email = payload.get("sub")
        # if email is None:
        #     return None
        #
        # return await db.get(User, email)
        
    except jwt.InvalidTokenError:
        return None


# Сервисы
async def get_auth_service(
    db: AsyncSession = Depends(get_db)
):
    """
    Зависимость для получения сервиса аутентификации.
    
    Returns:
        AuthService: Сервис для работы с аутентификацией
    """
    return AuthService(db)


async def get_place_service():
    """
    Зависимость для получения сервиса работы с местами.
    
    Returns:
        PlaceService: Сервис для работы с местами
    """
    return container.place_service()


async def get_hotel_service(db: AsyncSession = Depends(get_db)):
    """
    Зависимость для получения сервиса работы с отелями.
    
    Returns:
        HotelService: Сервис для работы с отелями
    """
    return container.hotel_service(db=db)


async def get_country_validator():
    """
    Зависимость для получения валидатора стран.
    
    Returns:
        CountryValidator: Валидатор стран
    """
    return await container.async_country_validator()


async def get_request_logger():
    """
    Зависимость для получения логгера запросов.
    
    Returns:
        RequestLogger: Логгер запросов

    """
    logger = container.async_request_logger()
    return logger


async def get_cache_service():
    """
    Зависимость для получения сервиса кэширования.
    
    Returns:
        CacheService: Сервис для работы с кэшем
    """
    return await container.async_cache_service()


# Внешние API
async def get_amadeus_token(
    client: AsyncClient = Depends(get_http_client)
) -> str:
    """
    Получение токена доступа Amadeus API.
    
    Args:
        client: HTTP-клиент
        
    Returns:
        str: Токен доступа
        
    Raises:
        HTTPException: Если не удалось получить токен
    """
    try:
        response = await client.post(
            url='https://test.api.amadeus.com/v1/security/oauth2/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.AMADEUS_CLIENT_ID,
                'client_secret': settings.AMADEUS_CLIENT_SECRET
            }
        )
        response.raise_for_status()
        return response.json()['access_token']
        
    except Exception as e:
        print(e)
        # raise HTTPException(
        #     status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        #     detail=f"Не удалось получить токен доступа Amadeus"
        # ) from e
