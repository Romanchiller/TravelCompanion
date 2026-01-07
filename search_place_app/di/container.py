import sys
from pathlib import Path
from dependency_injector import containers, providers
from httpx import AsyncClient

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent))

from search_place_app.database import SessionLocal
from search_place_app.services.hotel_service import HotelService
from search_place_app.services.cache_service import CacheService
from search_place_app.services.place_service import PlaceService
from search_place_app.validators.country_validator import CountryValidator
from search_place_app.utils.request_logger import RequestLogger

class Container(containers.DeclarativeContainer):
    """
    Контейнер зависимостей приложения.
    Обеспечивает централизованное управление зависимостями и их внедрение.
    """
    
    # Конфигурация
    config = providers.Configuration()
    http_client = providers.Factory(AsyncClient)
    
    # Сессия базы данных
    db_session = providers.Singleton(
        SessionLocal
    )
    
    # Сервисы
    hotel_service = providers.Factory(
        HotelService,
        db=db_session,
        client=http_client
    )
    
    # Утилиты
    cache_service = providers.Singleton(
        CacheService
    )
    
    country_validator = providers.Singleton(
        CountryValidator
    )
    
    request_logger = providers.Singleton(
        RequestLogger
    )
    place_service = providers.Factory(
        PlaceService,
        db=db_session,
        client=http_client,
        cache=cache_service,
    )


async def async_request_logger():
    return container.request_logger()

async def async_cache_service() -> CacheService:
    return container.cache_service()

async def async_country_validator() -> CountryValidator:
    return container.country_validator()

async def async_hotel_service() -> HotelService:
        return container.hotel_service()



# Создаем глобальный экземпляр контейнера
container = Container()
container.async_request_logger = async_request_logger
container.async_cache_service = async_cache_service
container.async_country_validator = async_country_validator
container.async_hotel_service = async_hotel_service

# Функция для получения контейнера
def get_container() -> Container:
    """
    Возвращает глобальный экземпляр контейнера зависимостей.
    
    Returns:
        Container: Экземпляр контейнера зависимостей
    """
    return container

__all__ = ['Container', 'container', 'get_container']

