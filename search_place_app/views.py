from fastapi import APIRouter, Depends, HTTPException, status, Query
from .dependencies import (
    get_db,
    get_current_user,
    is_authorized,
    get_api_places_headers,
    get_optional_current_user,
    get_auth_service,
    get_place_service,
)
from .config import settings
from .schema import CreateUser, Token
 
from .services.auth_service import AuthService
from .services.place_service import PlaceService
from .models import User
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Annotated, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


API_PLACES_URL = settings.PLACES_API_URL
places_router = APIRouter()
users_router = APIRouter()



@users_router.post('')
async def add_user(payload: CreateUser, db: AsyncSession = Depends(get_db), auth_service: AuthService = Depends(get_auth_service)):
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
    return user.dict


@users_router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")



@users_router.get("/me")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return current_user.dict


@places_router.get("/{search_info}")
async def get_places(
    search_info: str,
    headers: dict = Depends(get_api_places_headers),
    place_service: PlaceService = Depends(get_place_service),
    min_price: Optional[int] = Query(None, ge=1, le=4),
    max_price: Optional[int] = Query(None, ge=1, le=4),
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)] = None,
):

    places = await place_service.fetch_places(API_PLACES_URL, headers, search_info)

    place_service.validate_price_bounds(min_price, max_price)

    places = place_service.filter_by_price(places, min_price, max_price)

    if isinstance(places, list) and current_user is not None:
        user_id = current_user.id
        weights_by_category = await place_service.get_user_category_weights(user_id)
        weights_by_place_name = await place_service.get_user_place_name_weights(user_id)
        weights_by_place_address = await place_service.get_user_place_address_weights(user_id)
        if weights_by_category or weights_by_place_name or weights_by_place_address:
            places = place_service.score_places(
                places,
                weights_by_category,
                weights_by_place_name,
                weights_by_place_address,
            )

    return places


@places_router.post('/placesadd/{search_info}')
async def places_add(
    search_info: str,
    authorized: bool = Depends(is_authorized),
    headers: dict = Depends(get_api_places_headers),
    place_service: PlaceService = Depends(get_place_service),
    min_price: Optional[int] = Query(None, ge=1, le=4),
    max_price: Optional[int] = Query(None, ge=1, le=4),
    current_user: Annotated[User, Depends(get_current_user)] = None,
):
    if authorized:
        places = await place_service.fetch_places(API_PLACES_URL, headers, search_info)

        place_service.validate_price_bounds(min_price, max_price)

        places = place_service.filter_by_price(places, min_price, max_price)

        user_id = current_user.id if current_user is not None else None
        await place_service.process_places(places, user_id)

        return {"results": places}
