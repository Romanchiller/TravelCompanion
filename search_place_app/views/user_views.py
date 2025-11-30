from fastapi import APIRouter, Request, Depends, HTTPException, status
from loguru import logger
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from ..schema import CreateUser, Token, UserResponse
from ..services.auth_service import AuthService
from typing import Annotated
from ..models import User
from ..dependencies import (
    get_db,
    get_auth_service,
    get_request_logger,
)

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
async def register_user(
        request: Request,
        payload: CreateUser,
        auth_service: AuthService = Depends(get_auth_service),
        request_logger=Depends(get_request_logger),
        db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Регистрация нового пользователя.

    - **email**: Email пользователя (должен быть уникальным)
    - **password**: Пароль (минимум 8 символов)
    - **full_name**: Полное имя пользователя
    """
    logger.info(f"Попытка регистрации пользователя: {payload.email}")
    await request_logger.log_request(
        request=request,
        endpoint="POST /register",
        method="POST",
        payload=payload.model_dump()
    )
    password = auth_service.hash_password(payload.password)
    try:
        user = User(name=payload.name, email=payload.email, password=password)
        await db.add(user)

        # return UserResponse()

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
async def login_for_access_token(
        request: Request,
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        auth_service: AuthService = Depends(get_auth_service),
        request_logger=Depends(get_request_logger)
) -> Token:
    """
    Аутентификация пользователя и получение JWT токена.

    - **username**: Email пользователя
    - **password**: Пароль

    Возвращает access_token для аутентификации в API.
    """
    await request_logger.log_request(
        request=request,
        endpoint="POST /token",
        method="POST",
        payload={"username": form_data.username}
    )

    try:
        token = await auth_service.authenticate_user(
            email=form_data.username,
            password=form_data.password
        )
        return Token(access_token=token, token_type="bearer")

    except ValueError as e:
        logger.warning(f"Ошибка аутентификации для пользователя {form_data.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )


