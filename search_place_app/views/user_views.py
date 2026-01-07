from fastapi import APIRouter, Request, Depends, HTTPException, status
from loguru import logger
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from ..schema import CreateUser, Token, UserResponse, TokenRequest
from ..services.auth_service import AuthService
from typing import Annotated
from ..models import User
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from ..dependencies import (
    get_db,
    get_auth_service,
    get_current_user,
)
from ..utils.request_logger import RequestLogger

users_router = APIRouter(tags=["Пользователи"])


@users_router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Некорректные данные пользователя"},
        status.HTTP_409_CONFLICT: {"description": "Пользователь с таким email уже существует"},
    },
)
@RequestLogger.log_request()
async def register_user(
    request: Request,
    payload: CreateUser,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Попытка регистрации пользователя: {payload.email}")

    try:
        user_data = payload.model_dump()
        user_data['password'] = auth_service.hash_password(payload.password)
        result = await db.execute(select(User).where(User.email == user_data["email"]))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

        user = User(**user_data)
        db.add(user)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
        await db.refresh(user)

        logger.info(f"Пользователь успешно зарегистрирован: {user.email}")
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.is_active
        )




    except ValueError as e:
        logger.error(f"Ошибка при регистрации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при регистрации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при регистрации пользователя"
        )


@users_router.post("/token", response_model=Token)
@RequestLogger.log_request()
async def login_for_access_token(
        request: Request,
        payload : TokenRequest,
        auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    """
    Аутентификация пользователя и получение JWT токена.

    - **username**: Email пользователя
    - **password**: Пароль

    Возвращает access_token для аутентификации в API.
    """
    try:
        token =  await auth_service.login_for_access_token(payload.email, payload.password)

        return Token(access_token=token['access_token'], token_type=token['token_type'])


    except ValueError as e:
        logger.warning(f"Ошибка аутентификации для пользователя {payload.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )


@users_router.get("/me")
@RequestLogger.log_request()
async def read_users_me(request: Request,
                        # token: Token,
                        user = Depends(get_current_user)
):
    user = UserResponse(id=user.id,
                        name=user.name,
                        email=user.email,)

    return user