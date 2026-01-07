import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    PLACES_API_TOKEN: str
    PLACES_API_URL: str = "https://places-api.foursquare.com/places/search"
    PLACES_API_VERSION: str = "2025-06-17"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    CACHE_ENABLED: bool = True
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 300
    MAX_CONCURRENT: int = 10
    CACHE_ENABLED: bool
    MEMCACHED_HOST: str
    MEMCACHED_PORT: int
    CACHE_DEFAULT_TTL: int
    ENV_TYPE: str
    AMADEUS_CLIENT_ID: str
    AMADEUS_CLIENT_SECRET: str
    AMADEUS_API_URL: str = "https://test.api.amadeus.com/v1/reference-data/locations/hotel"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    )


settings = Settings()


def get_db_url():
    return f"mysql+asyncmy://{settings.DB_USER}:{settings.DB_PASSWORD}@" \
           f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
