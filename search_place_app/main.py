import sys
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
import traceback
from .views.user_views import users_router
from .views.place_views import places_router
from .views.hotel_views import hotels_router

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from search_place_app.database import engine, Base
from search_place_app.logging_config import setup_logging

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Контекстный менеджер для управления жизненным циклом приложения."""
    try:
        logger.info("Запуск приложения")
        engine.begin()
        logger.info("Инициализация базы данных выполнена")
        yield
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        await engine.dispose()
        logger.info("Приложение завершило работу")

app = FastAPI(
    title="TravelCompanion API",
    description="API для сервиса TravelCompanion",
    version="1.0.0",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальный обработчик исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Необработанное исключение: {str(exc)}\n"
        f"URL: {request.url}\n"
        f"Метод: {request.method}\n"
        f"Клиент: {request.client}\n"
        f"Трассировка: {traceback.format_exc()}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Внутренняя ошибка сервера"},
    )

# Обработчик ошибок валидации
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(
        f"Ошибка валидации запроса: {exc.errors()}\n"
        f"URL: {request.url}\n"
        f"Метод: {request.method}\n"
        f"Тело запроса: {await request.body()}"
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )


# Подключаем роутеры с префиксами
app.include_router(places_router, prefix="/api/places")
app.include_router(users_router, prefix="/api/users")
app.include_router(hotels_router, prefix="/api/hotel")


# Эндпоинт для проверки работоспособности
@app.get("/health", tags=["Система"])
async def health_check():
    """Проверка работоспособности сервиса"""
    return {"status": "ok", "message": "Сервис работает нормально"}