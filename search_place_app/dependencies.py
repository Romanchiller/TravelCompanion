from httpx import AsyncClient
from .database import SessionLocal
from .tools import get_user, oauth2_scheme
from .config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, Depends
import jwt
from typing import Annotated
from .schema import TokenData
from typing import Optional, Annotated
from .models import User
from .tools import oauth2_optional_scheme
from .services.auth_service import AuthService
from .services.place_service import PlaceService

async def get_http_client():
    async with AsyncClient() as client:
        yield client


async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except jwt.InvalidTokenError:
        raise credentials_exception
    user = await get_user(token_data.email, db)
    if user is None:
        raise credentials_exception

    return user


async def is_authorized(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "bearer"},
            )
        return True
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "bearer"},
        )


async def get_optional_current_user(
    token: Annotated[Optional[str], Depends(oauth2_optional_scheme)],
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        if email is None:
            return None
        token_data = TokenData(email=email)
    except jwt.InvalidTokenError:
        return None
    user = await get_user(token_data.email, db)
    return user
def get_api_places_headers():
    return {
        'X-Places-Api-Version': settings.PLACES_API_VERSION,
        'accept': 'application/json',
        'Authorization': settings.PLACES_API_TOKEN
    }


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    return AuthService(db)


async def get_place_service(
    db: AsyncSession = Depends(get_db),
    client: AsyncClient = Depends(get_http_client),
) -> PlaceService:
    return PlaceService(db, client)