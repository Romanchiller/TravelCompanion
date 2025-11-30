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
# app.include_router(places_router, prefix="/api/places")
app.include_router(users_router, prefix="/api/users")
# app.include_router(hotel_router, prefix="/api/hotel")

# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(
        f"Запрос: {request.method} {request.url} | "
        f"Клиент: {request.client.host}:{request.client.port} | "
        f"Параметры запроса: {dict(request.query_params)}"
    )
    
    try:
        # Логируем заголовки для отладки
        logger.debug(f"Заголовки запроса: {dict(request.headers)}")
        
        # Получаем тело запроса для POST/PUT запросов
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
                logger.debug(f"Тело запроса: {body}")
            except Exception as e:
                logger.debug(f"Не удалось прочитать тело запроса: {str(e)}")
        
        response = await call_next(request)
        
        logger.info(
            f"Ответ: {request.method} {request.url} | "
            f"Статус: {response.status_code}"
        )
        
        # Логируем заголовки ответа
        logger.debug(f"Заголовки ответа: {dict(response.headers)}")
        
        return response
        
    except Exception as e:
        logger.error(
            f"Непредвиденная ошибка при обработке запроса {request.method} {request.url}:",
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Внутренняя ошибка сервера"}
        )
        raise

# Эндпоинт для проверки работоспособности
@app.get("/health", tags=["Система"])
async def health_check():
    """Проверка работоспособности сервиса"""
    return {"status": "ok", "message": "Сервис работает нормально"}