from fastapi import APIRouter, Depends, Query
from fastapi import Request, status
from ..logging_config import setup_logging
from ..utils.request_logger import RequestLogger
from typing import Dict, Any, Optional
from ..dependencies import get_amadeus_token, get_hotel_service, get_current_user, get_cache_service, get_optional_current_user
from loguru import logger
from fastapi.exceptions import HTTPException
import asyncio
import traceback
from ..services.cache_service import CacheService

setup_logging()

hotels_router = APIRouter(tags=["Отели"])


@hotels_router.get('/search/{search_info}',
                    status_code=status.HTTP_200_OK,
                    responses={status.HTTP_400_BAD_REQUEST: {"description": "Некорректные параметры запроса"},
                               status.HTTP_404_NOT_FOUND: {"description": "Отели не найдены"}, })
@RequestLogger.log_request()
async def hotels_search(request: Request,
                        search_info: str,
                        user = Depends(get_optional_current_user),
                        country_code: Optional[str] = None,
                        token = Depends(get_amadeus_token),
                        max_results: Optional[int] = Query(20, ge=1, le=20),
                        cache_service: CacheService = Depends(get_cache_service),
                        hotel_service = Depends(get_hotel_service)) -> Dict[str, Any]:
    user_id = user.id if user else "anonymous"
    cache_key = f"hotels:{user_id}:{country_code.lower() if country_code else 'all'}:{search_info.lower().replace(' ', '_')}"
    cached_result = await cache_service.get(cache_key)

    if cached_result is not None:
        logger.info(f"Кэш-попадание для {user_id}:{country_code}:{search_info}")
        return cached_result

    hotels_data = await hotel_service.search_hotel(token=token,
                                                   max_results=max_results,
                                                   country_code=country_code,
                                                   search_info=search_info)

    if user and hotels_data and 'data' in hotels_data:
        try:
            hotel_names = [hotel['name'] for hotel in hotels_data['data'] if 'name' in hotel]

            hotel_ids = await hotel_service.get_hotel_ids_by_names(hotel_names)

            if hotel_ids:
                hotel_weights = await hotel_service.get_hotel_weights(
                    user_id=user.id,
                    hotel_ids=hotel_ids
                )

            hotel_weights = await hotel_service.get_hotel_weights(
                user_id=user.id,
                hotel_ids=hotel_ids
            )

            for hotel in hotels_data['data']:
                hotel_name = hotel.get('name')
                if hotel_name in hotel_ids:  # Если нашли отель в базе
                    hotel_id = str(hotel_ids[hotel_name])
                    hotel['weight'] = hotel_weights.get(hotel_id, 0)
                else:
                    hotel['weight'] = 0

            # Сортируем отели по весу (по убыванию)
            hotels_data['data'].sort(key=lambda x: x.get('weight', 0), reverse=True)

        except Exception as e:
            logger.error(f"Ошибка при сортировке отелей по весу: {str(e)}", exc_info=True)
            # В случае ошибки оставляем исходный порядок

    if hotels_data:
        await cache_service.set(cache_key, hotels_data, ttl=3600)
    return hotels_data


@hotels_router.post('/search/{search_info}',
                    status_code=status.HTTP_200_OK,
                    responses={status.HTTP_400_BAD_REQUEST: {"description": "Некорректные параметры запроса"},
                               status.HTTP_404_NOT_FOUND: {"description": "Отели не найдены"}
                               }
                    )
@RequestLogger.log_request()
async def hotel_to_favorite(request: Request,
                            search_info: str,
                            user = Depends(get_current_user),
                            country_code: Optional[str] = None,
                            token = Depends(get_amadeus_token),
                            max_results: Optional[int] = Query(20, ge=1, le=20),
                            cache_service: CacheService = Depends(get_cache_service),
                            hotel_service = Depends(get_hotel_service)) -> Dict[str, Any]:

    cache_key = f"hotels_{country_code.lower()}:{search_info.lower()}"
    cached_result = await cache_service.get(cache_key)

    if cached_result is not None:
        logger.info(f"Кэш-попадание для {country_code}:{search_info}")
        result = await hotel_service.process_hotels_batch(
            cached_result['data'],
            user
        )
        return {
            "status": "success",
            "total_processed": len(cached_result['data']),
            "successful": result['successful'],
            "errors": result['errors']
        }
    try:
        hotels_data = await hotel_service.search_hotel(token=token,
                                                       max_results=max_results,
                                                       country_code=country_code,
                                                       search_info=search_info)
        if hotels_data:
            await cache_service.set(cache_key, hotels_data)

        if not hotels_data or 'data' not in hotels_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Отели не найдены")

        result = await hotel_service.process_hotels_batch(
            hotels_data['data'],
            user
        )

        return {
            "status": "success",
            "total_processed": len(hotels_data['data']),
            "successful": result['successful'],
            "errors": result['errors']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при обработке запроса"
        )
