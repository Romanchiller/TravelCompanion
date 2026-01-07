import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from httpx import AsyncClient, HTTPStatusError
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from search_place_app.config import settings

# Инициализация логгера
logger = logger.bind(module=__name__)

# Константы API
API_PLACES_URL = getattr(settings, 'PLACES_API_URL', '')

# Базовые настройки роутеров
router_config = {
    "responses": {
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Внутренняя ошибка сервера"
        }
    }
}

# Инициализация роутеров


hotel_router = APIRouter(tags=["Отели"], **router_config)

#
# async def places_add(
#     search_info: str,
#     place_service: PlaceService = Depends(get_place_service),
#     db: AsyncSession = Depends(get_db),
#     min_price: Optional[int] = Query(None, ge=1, le=4, description="Минимальная цена (1-4)"),
#     max_price: Optional[int] = Query(None, ge=1, le=4, description="Максимальная цена (1-4)"),
#     current_user: User = Depends(get_current_user),
# ):
#     """
#     Добавление мест в избранное.
#
#     - **search_info**: Поисковый запрос (название места, адрес и т.д.)
#     - **min_price**: Минимальная цена (1-4)
#     - **max_price**: Максимальная цена (1-4)
#     """
#     logger.info(f"Добавление мест по запросу: {search_info}")
#
#     try:
#         # Создаем новый экземпляр PlaceService с текущей сессией
#         # Если кэш не нужен, отключаем его в настройках
#         cache = None
#         if settings.CACHE_ENABLED:
#             cache = cache_manager
#
#         place_service = PlaceService(db, AsyncClient(), cache)
#
#         # Определяем заголовки для запроса
#         headers = {
#             'Content-Type': 'application/json',
#             'Accept': 'application/json'
#         }
#
#         places = await place_service.fetch_places(API_PLACES_URL, headers, search_info)
#
#         if not places:
#             logger.warning(f"Места по запросу '{search_info}' не найдены")
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Места не найдены"
#             )
#
#         place_service.validate_price_bounds(min_price, max_price)
#         places = place_service.filter_by_price(places, min_price, max_price)
#
#         # Обрабатываем места в транзакции
#         try:
#             await place_service.process_places(places, current_user.id)
#             await db.commit()
#             logger.info(f"Успешно обработано {len(places)} мест для пользователя {current_user.email}")
#             return {"results": places}
#         except Exception as e:
#             await db.rollback()
#             raise
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(
#             f"Ошибка при обработке мест: {str(e)}\n"
#             f"Тип ошибки: {type(e).__name__}\n"
#             f"Трассировка: {traceback.format_exc()}"
#         )
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Произошла ошибка при обработке мест: {str(e)}"
#         )
#
#
# @hotel_router.get(
#     '/{search_info}',
#     response_model=Dict[str, Any],
#     responses={
#         200: {"description": "Успешный запрос, возвращает список отелей"},
#         400: {"description": "Неверные параметры запроса"},
#         500: {"description": "Внутренняя ошибка сервера"}
#     }
# )
# @RequestLogger.log_http_errors()
# async def get_hotel(
#     request: Request,
#     search_info: str,
#     country_code: Optional[str] = None,
#     client: AsyncClient = Depends(get_http_client),
#     token = Depends(get_amadeus_token),
#     max_results: Optional[int] = Query(20, ge=1, le=20),
#     request_logger = Depends(get_request_logger),
#     cache_service: CacheService = Depends(get_cache_service),
#     country_validator = Depends(get_country_validator)
# ) -> Dict[str, Any]:
#     """
#     Получает данные об отелях из API Amadeus с кэшированием
#
#     - **search_info**: Поисковый запрос (название отеля, город и т.д.)
#     - **country_code**: Код страны (опционально, формат ISO 3166-1 alpha-2)
#     - **max_results**: Максимальное количество результатов (1-20)
#     """
#     # Логируем запрос
#     request_logger.log_request_data({
#         "search_info": search_info,
#         "country_code": country_code,
#         "max_results": max_results
#     })
#
#     try:
#         # Используем общую функцию поиска отелей
#         hotels_data = await search_hotels(
#             search_info=search_info,
#             country_code=country_code,
#             client=client,
#             token=token,
#             max_results=max_results,
#             cache_service=cache_service,
#             country_validator=country_validator
#         )
#
#         if not hotels_data or 'data' not in hotels_data:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Отели не найдены"
#             )
#
#         return hotels_data
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Ошибка при поиске отелей: {str(e)}\n{traceback.format_exc()}")
#         raise HTTPException(
#             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
#             detail="Сервис временно недоступен. Пожалуйста, попробуйте позже."
#         )
#
#
#     except HTTPStatusError as e:
#         error_msg = f"Ошибка при запросе к API Amadeus: {str(e)}"
#         logger.error(f"{error_msg}\n{e.response.text}")
#         raise HTTPException(
#             status_code=e.response.status_code,
#             detail=error_msg
#         )
#
#     except Exception as e:
#         error_msg = f"Неожиданная ошибка при поиске отелей: {str(e)}"
#         logger.error(f"{error_msg}\n{traceback.format_exc()}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=error_msg
#         )
#
#
# async def search_hotels(
#     search_info: str,
#     country_code: Optional[str],
#     max_results: Optional[int],
#     cache_service: CacheService,
#     token: str = Depends(get_amadeus_token),
#     country_validator = Depends(get_country_validator),
#     client : AsyncClient = Depends(get_http_client),
# )-> Dict[str, Any]:
#     """
#     Поиск отелей по заданным параметрам.
#
#     Args:
#         search_info: Поисковый запрос
#         country_code: Код страны (опционально)
#         client: HTTP-клиент
#         token: Токен аутентификации
#         max_results: Максимальное количество результатов
#         cache_service: Сервис кеширования
#         country_validator: Валидатор кода страны
#
#     Returns:
#         Словарь с данными об отелях
#     """
#     logger.info(f"Начало поиска отелей: {search_info}, страна: {country_code}")
#
#     safe_search_info = quote(search_info, safe='')
#     cache_key = f"hotel_search:{safe_search_info}:{country_code or 'any'}:{max_results}"
#     logger.debug(f"Ключ кэша: {cache_key}")
#
#     try:
#         cached_data = await cache_service.get(cache_key)
#         if cached_data is not None:
#             logger.info("Данные найдены в кеше")
#             return cached_data
#         logger.debug("Данные в кеше не найдены")
#     except Exception as e:
#         logger.error(f"Ошибка при работе с кешем: {str(e)}")
#
#     logger.info("Подготовка запроса к API отелей")
#     params = {'keyword': search_info,
#               'subType': 'HOTEL_GDS',
#               }
#     try:
#         # Валидируем код страны, если он указан
#         if country_code:
#             logger.debug(f"Валидация кода страны: {country_code}")
#             try:
#                 country_code = await country_validator.validate_country(country_code)
#                 params['countryCode'] = country_code
#                 logger.debug(f"Код страны прошел валидацию: {country_code}")
#             except Exception as e:
#                 logger.error(f"Ошибка валидации кода страны {country_code}: {str(e)}")
#                 raise HTTPException(
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     detail=f"Некорректный код страны: {country_code}"
#                 )
#
#         if max_results:
#             params['max'] = int(max_results)
#
#         hotels_data = await client.get(url='https://test.api.amadeus.com/v1/reference-data/locations/hotel',
#                                     headers={'accept': 'application/vnd.amadeus+json',
#                                              'Authorization': 'Bearer ' + token},
#                                     params=params
#                                     )
#         logger.info(f"Получено {len(hotels_data.get('data', []))} отелей")
#
#         # Сохраняем в кеш
#         try:
#             await cache_service.set(cache_key, hotels_data, expire=3600)  # Кешируем на 1 час
#             logger.debug("Данные успешно сохранены в кеш")
#         except Exception as e:
#             logger.error(f"Ошибка при сохранении в кеш: {str(e)}")
#
#         return hotels_data.json()
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Критическая ошибка при поиске отелей: {str(e)}\n{traceback.format_exc()}")
#         raise HTTPException(
#             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
#             detail="Сервис временно недоступен. Пожалуйста, попробуйте позже."
#         )
#
# @hotel_router.post('/{search_info}', response_model=dict)
# async def add_hotel(
#     request: Request,
#     search_info: str,
#     country_code: Optional[str] = None,
#     client: AsyncClient = Depends(get_http_client),
#     token = Depends(get_amadeus_token),
#     max_results: Optional[int] = Query(20, ge=1, le=20),
#     current_user: User = Depends(get_current_user),
#     request_logger = Depends(get_request_logger),
#     db: AsyncSession = Depends(get_db),
#     cache_service: CacheService = Depends(get_cache_service),
#     country_validator = Depends(get_country_validator)
# ):
#     """
#     Добавляет отели в избранное пользователя конкурентно
#
#     - **search_info**: Поисковый запрос (название отеля, город и т.д.)
#     - **country_code**: Код страны (опционально)
#     - **max_results**: Максимальное количество результатов (1-20)
#     """
#     # Логируем запрос
#     request_logger.log_request_data(
#         {
#             "search_info": search_info,
#             "country_code": country_code,
#             "max_results": max_results,
#             "user_id": current_user.id
#         }
#     )
#
#     try:
#         # Получаем данные об отелях
#         hotels_data = await search_hotels(
#             search_info=search_info,
#             country_code=country_code,
#             client=client,
#             token=token,
#             max_results=max_results,
#             cache_service=cache_service,
#             country_validator=country_validator
#         )
#
#         if not hotels_data or 'data' not in hotels_data or not hotels_data['data']:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Отели не найдены"
#             )
#
#         # Инициализируем сервис отелей
#         hotel_service = HotelService(db)
#
#         # Обрабатываем отели
#         success_count = 0
#         errors = []
#
#         for hotel_data in hotels_data['data']:
#             try:
#                 # Обрабатываем отель через сервис
#                 result = await hotel_service.process_hotel(hotel_data, current_user)
#
#                 if result.get('status') == 'success':
#                     success_count += 1
#                 else:
#                     errors.append(result)
#
#             except Exception as e:
#                 logger.error(f"Ошибка при обработке отеля {hotel_data.get('name')}: {str(e)}")
#                 errors.append({
#                     "status": "error",
#                     "message": str(e),
#                     "hotel": hotel_data.get('name')
#                 })
#
#         # Формируем ответ
#         response_data = {
#             "status": "success",
#             "total_processed": len(hotels_data['data']),
#             "saved_count": success_count,
#             "errors": errors
#         }
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Ошибка при обработке отелей: {str(e)}\n{traceback.format_exc()}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Произошла ошибка при обработке отелей: {str(e)}"
#         )
