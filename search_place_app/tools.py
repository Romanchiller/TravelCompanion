
from sqlalchemy.exc import IntegrityError
from asyncio import Semaphore
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from .config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import User, Category, Place, UserPlace, PlaceCategory, UserCategory
from .database import SessionLocal
from typing import Optional, Any
from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException
from operator import itemgetter
from sqlalchemy import func

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

oauth2_optional_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def hash_password(password: str) -> str:

    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)

    return hashed_password.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')

    return bcrypt.checkpw(password_bytes, hashed_password_bytes)


async def add_item(item, db: AsyncSession):
    db.add(item)

async def get_user(email: str, db: AsyncSession):
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    if user:
        return user
    return None


async def authenticate_user(db: AsyncSession, username: str, password: str):
    user = await get_user(username, db)
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_or_create_category(name: str, session: AsyncSession) -> Category:
    result = await session.execute(select(Category).where(Category.name == name))
    category_obj = result.scalar_one_or_none()
    if category_obj:
        return category_obj
    category_obj = Category(name=name)
    session.add(category_obj)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        result = await session.execute(select(Category).where(Category.name == name))
        category_obj = result.scalar_one()
    return category_obj


async def process_place(place_item: dict, sem: Semaphore, user_id: int | None = None) -> None:
    async with sem:
        async with SessionLocal() as session:
            category_objs: list[Category] = []
            for category_dict in place_item.get('categories', []):
                name = category_dict.get('name')
                if not name:
                    continue
                category = await get_or_create_category(name, session)
                category_objs.append(category)
            address = place_item.get('location', {}).get('formatted_address')
            place = Place(name=place_item['name'], address=address)
            for category_obj in category_objs:
                place.categories.append(category_obj)
            session.add(place)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
            if user_id is not None:
                result_user_place = await session.execute(
                    select(UserPlace).where(
                        UserPlace.user_id == user_id, UserPlace.place_id == place.id
                    )
                )
                user_place_record: UserPlace | None = result_user_place.scalar_one_or_none()
                if user_place_record is None:
                    user_place_record = UserPlace(user_id=user_id, place_id=place.id, weight=1)
                    session.add(user_place_record)
                else:
                    user_place_record.weight = int(user_place_record.weight) + 1
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()

                for category_obj in category_objs:
                    result_user_category = await session.execute(
                        select(UserCategory).where(
                            UserCategory.user_id == user_id,
                            UserCategory.category_id == category_obj.id,
                        )
                    )
                    user_category_record: UserCategory | None = result_user_category.scalar_one_or_none()
                    if user_category_record is None:
                        user_category_record = UserCategory(user_id=user_id, category_id=category_obj.id, weight=1)
                        session.add(user_category_record)
                    else:
                        user_category_record.weight = int(user_category_record.weight) + 1
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()

def get_price_value(item: dict) -> Optional[int]:
    price = item.get('price')
    if price:
        return int(price)
    return None


def passes_range(value: Optional[float], lo: Optional[float], hi: Optional[float]) -> bool:
    if lo is not None:
        if value is None or value < lo:
            return False
    if hi is not None:
        if value is None or value > hi:
            return False
    return True


def filter_items_by_price(items: list[dict] | None, min_price: Optional[int], max_price: Optional[int]) -> list[dict] | None:
    if not isinstance(items, list):
        return items
    if all(v is None for v in (min_price, max_price)):
        return items

    filtered: list[dict] = []
    for item in items:
        price_value = get_price_value(item)
        if not passes_range(
            float(price_value) if price_value is not None else None,
            float(min_price) if min_price is not None else None,
            float(max_price) if max_price is not None else None,
        ):
            continue
        filtered.append(item)
    return filtered


def validate_price_bounds(min_price: Optional[int], max_price: Optional[int]) -> None:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=400, detail="min_price must be <= max_price")


async def fetch_places(client: Any, url: str, headers: dict, query: str) -> list[dict]:
    params = {"query": query}
    response = await client.get(url, headers=headers, params=params)
    data = response.json() or {}
    results = data.get("results")
    return results if isinstance(results, list) else []


async def get_user_category_weights(db: AsyncSession, user_id: int) -> dict[str, int]:
    stmt = (
        select(Category.name, func.sum(UserCategory.weight).label("w"))
        .join(UserCategory, UserCategory.category_id == Category.id)
        .where(UserCategory.user_id == user_id)
        .group_by(Category.name)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return {name: int(weight_sum) for name, weight_sum in rows}


async def get_user_place_name_weights(db: AsyncSession, user_id: int) -> dict[str, int]:
    stmt = (
        select(Place.name, func.sum(UserPlace.weight).label("w"))
        .join(UserPlace, UserPlace.place_id == Place.id)
        .where(UserPlace.user_id == user_id)
        .group_by(Place.name)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return {name: int(w) for name, w in rows}


async def get_user_place_address_weights(db: AsyncSession, user_id: int) -> dict[str, int]:

    stmt = (
        select(Place.address, func.sum(UserPlace.weight).label("w"))
        .join(UserPlace, UserPlace.place_id == Place.id)
        .where(UserPlace.user_id == user_id)
        .group_by(Place.address)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return {address: int(weight_sum) for address, weight_sum in rows if address is not None}


def compute_place_score(
    item: dict,
    weights_by_category: dict[str, int],
    weights_by_place_name: Optional[dict[str, int]] = None,
    weights_by_place_address: Optional[dict[str, int]] = None,
) -> int:
    total = 0
    for category_dict in item.get("categories", []) or []:
        name = category_dict.get("name")
        if not name:
            continue
        total += int(weights_by_category.get(name, 0))
    if weights_by_place_name:
        place_name = item.get("name")
        if place_name:
            total += int(weights_by_place_name.get(place_name, 0))
    if weights_by_place_address:
        address = (item.get("location") or {}).get("formatted_address")
        if address:
            total += int(weights_by_place_address.get(address, 0))
    return total


def score_places_by_prefs(
    items: list[dict],
    weights_by_category: dict[str, int],
    weights_by_place_name: Optional[dict[str, int]] = None,
    weights_by_place_address: Optional[dict[str, int]] = None,
) -> list[dict]:
    scored = [
        (
            compute_place_score(
                item,
                weights_by_category,
                weights_by_place_name,
                weights_by_place_address,
            ),
            item,
        )
        for item in items
    ]
    scored.sort(key=itemgetter(0), reverse=True)
    return [item for _, item in scored]





