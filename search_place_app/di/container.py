import sys
from pathlib import Path
from dependency_injector import containers, providers

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent))

from search_place_app.database import SessionLocal
from search_place_app.services.hotel_service import HotelService
from search_place_app.services.cache_service import CacheService
from search_place_app.validators.country_validator import CountryValidator
from search_place_app.utils.request_logger import RequestLogger

class Container(containers.DeclarativeContainer):
    """
    Контейнер зависимостей приложения.
    Обеспечивает централизованное управление зависимостями и их внедрение.
    """
    
    # Конфигурация
    config = providers.Configuration()
    
    # Сессия базы данных
    db_session = providers.Singleton(
        SessionLocal
    )
    
    # Сервисы
    hotel_service = providers.Factory(
        HotelService,
        db=db_session
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
    
    # Асинхронные версии для зависимостей
    async def async_cache_service(self) -> CacheService:
        return self.cache_service()
        
    async def async_country_validator(self) -> CountryValidator:
        return self.country_validator()
        
    async def async_request_logger(self) -> RequestLogger:
        return self.request_logger()
    


# Создаем глобальный экземпляр контейнера
container = Container()

# Функция для получения контейнера
def get_container() -> Container:
    """
    Возвращает глобальный экземпляр контейнера зависимостей.
    
    Returns:
        Container: Экземпляр контейнера зависимостей
    """
    return container

# Функция для переопределения зависимостей в тестах
def override_providers(test_container: Container) -> None:
    """
    Переопределяет провайдеры в глобальном контейнере.
    Используется в тестах для подмены зависимостей на моки.
    
    Args:
        test_container: Тестовый контейнер с переопределенными зависимостями
    """
    global container
    container = test_container
