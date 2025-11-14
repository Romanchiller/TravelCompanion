from fastapi import FastAPI
from .views import places_router, users_router
from .database import engine, Base
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.begin()
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)


app.include_router(places_router, tags=['Places'], prefix='/api/places')
app.include_router(users_router, tags=['Users'], prefix='/api/users')