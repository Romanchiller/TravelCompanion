from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from sqlalchemy import select
from ..config import settings
from ..models import User


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def hash_password(self, password: str) -> str:
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt)
        return hashed_password.decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        password_bytes = password.encode('utf-8')
        hashed_password_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_password_bytes)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    async def authenticate_user(self, username: str, password: str):
        result = await self.db.execute(select(User).where(User.email == username))
        user = result.scalar_one_or_none()
        if not user:
            return False
        if not self.verify_password(password, user.password):
            return False
        return user
        
    async def login_for_access_token(self, username: str, password: str):
        """
        Аутентификация пользователя и получение JWT токена.
        
        Args:
            username: Email пользователя
            password: Пароль
            
        Returns:
            Словарь с access_token и token_type
            
        Raises:
            HTTPException: Если аутентификация не удалась
        """
        user = await self.authenticate_user(username, password)
        if not user:
            raise ValueError("Неверный email или пароль")
            
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            data={"sub": user.email}, 
            expires_delta=access_token_expires
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
