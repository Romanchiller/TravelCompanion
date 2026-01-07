from fastapi import Request, APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from ..dependencies import get_db, get_place_service, get_current_user, get_optional_current_user, get_cache_service
from ..services.place_service import PlaceService
from ..services.cache_service import CacheService
from ..models import User
from sqlalchemy.ext.asyncio import AsyncSession
from ..config import settings
from ..utils.request_logger import RequestLogger
import traceback
from loguru import logger
from ..logging_config import setup_logging

setup_logging()

places_router = APIRouter(tags=["Места"])


@places_router.post(
    '/add/{search_info}',
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Некорректные параметры запроса"},
        status.HTTP_404_NOT_FOUND: {"description": "Места не найдены"},
    }
)
@RequestLogger.log_request()
async def places_add(
        request: Request,
        search_info: str,
        place_service: PlaceService = Depends(get_place_service),
        db: AsyncSession = Depends(get_db),
        min_price: Optional[int] = Query(None, ge=1, le=4, description="Минимальная цена (1-4)"),
        max_price: Optional[int] = Query(None, ge=1, le=4, description="Максимальная цена (1-4)"),
        current_user: User = Depends(get_current_user),
        cache_service: CacheService = Depends(get_cache_service),
):
    cache_key = f"hotels:{search_info.lower().replace(' ', '_')}"
    if min_price is not None:
        cache_key = f"{cache_key}:min_{min_price}"
    if max_price is not None:
        cache_key = f"{cache_key}:max_{max_price}"

    cached_result = await cache_service.get(cache_key)

    if cached_result:
        logger.info(f"Кэш-попадание для {current_user.id}:{search_info}")
        search_result = await place_service.process_places(cached_result, current_user.id)

        return {
            "status": "success",
            "message": "Места успешно добавлены",
            "count": len(cached_result)
        }

    try:
        search_result = await place_service.search_place(search_info, min_price, max_price)
        
        if not search_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Места не найдены"
            )

        await place_service.process_places(search_result, current_user.id if current_user else None)
        await cache_service.set(cache_key, search_result, ttl=3600)  # Кэшируем на 1 час
        
        return {
            "status": "success", 
            "message": "Места успешно добавлены", 
            "count": len(search_result)
        }
    except Exception as e:
        logger.error(f"Ошибка при добавлении мест: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Произошла ошибка при обработке запроса: {str(e)}"
        )





@places_router.get('/search/{search_info}')
@RequestLogger.log_request()
async def places_search(
        request: Request,
        search_info: str,
        current_user = Depends(get_optional_current_user),  # Используем необязательную аутентификацию
        place_service = Depends(get_place_service),
        min_price: Optional[int] = Query(None, ge=1, le=4, description="Минимальная цена (1-4)"),
        max_price: Optional[int] = Query(None, ge=1, le=4, description="Максимальная цена (1-4)"),
        cache_service: CacheService = Depends(get_cache_service),
):
    if current_user:
        cache_key = f"hotels:{search_info.lower().replace(' ', '_'):{min_price if min_price else ''}:{max_price if max_price else ''}}"
        cached_result = await cache_service.get(cache_key)

        if cached_result is not None:
            logger.info(f"Кэш-попадание для {current_user.id}:{search_info}")
            return cached_result

    places = await place_service.search_place(search_info, min_price, max_price)

    if current_user:
        logger.info(f'Применение персонализации для пользователя {current_user.id}')
        try:

            places = await place_service.sort_places_by_preferences(places, current_user)
            cache_key = f"hotels:{search_info.lower().replace(' ', '_'):{min_price if min_price else ''}:{max_price if max_price else ''}}"
            await cache_service.set(cache_key, places)

        except Exception as e:
            logger.error(f"Ошибка при сортировке мест: {str(e)}")
            logger.error(traceback.format_exc())
    return places
