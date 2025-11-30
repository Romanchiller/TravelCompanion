from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, model_validator
from typing import Optional, Type, List


class AbstractUser(BaseModel):
    name: str
    password: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Name must be between 3 and 50 characters long")
        return v


    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 20:
            raise ValueError("Password must be between 8 and 20 characters long")
        return v

    @field_validator('email')
    @classmethod
    def email_length(cls, v: EmailStr) -> EmailStr:
        if len(v) > 100:
            raise ValueError('Максимальная длина email 100')
        return v

class CreateUser(AbstractUser):
    pass


class UpdateUser(AbstractUser):
    name: Optional[str] = None
    password: Optional[str] = None
    email: Optional[EmailStr] = None

    @field_validator('name')
    @classmethod
    def validate_name_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Name must be between 3 and 50 characters long")
        return v

    @field_validator('password')
    @classmethod
    def validate_password_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) < 8 or len(v) > 20:
            raise ValueError("Password must be between 8 and 20 characters long")
        return v

    @field_validator('email')
    @classmethod
    def validate_email_optional(cls, v: Optional[EmailStr]) -> Optional[EmailStr]:
        if v is None:
            return v
        if len(v) > 100:
            raise ValueError('Максимальная длина email 100')
        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateUser":
        if self.name is None and self.password is None and self.email is None:
            raise ValueError("At least one of 'name', 'password', or 'email' must be provided")
        return self


class UserInDB(AbstractUser):
    id: int
    name: str
    email: EmailStr
    password: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: EmailStr | None = None


class UserResponse(BaseModel):
    """Схема для ответа с данными пользователя."""
    id: int
    name: str
    email: EmailStr
    is_active: bool = True
    
    model_config = ConfigDict(from_attributes=True)

class UserPublic(BaseModel):
    id: int
    name: str
    email: EmailStr
    
    model_config = ConfigDict(from_attributes=True)


class PlaceBase(BaseModel):
    """Базовая схема для места."""
    name: str
    address: Optional[str] = None


class PlaceCreate(PlaceBase):
    """Схема для создания места."""
    pass


class PlaceUpdate(PlaceBase):
    """Схема для обновления места."""
    name: Optional[str] = None
    address: Optional[str] = None


class Place(PlaceBase):
    """Схема для отображения места."""
    id: int
    categories: List['Category'] = []
    users: List['UserPublic'] = []
    
    model_config = ConfigDict(from_attributes=True)


class PlaceInDB(Place):
    """Схема для хранения места в базе данных."""
    pass


class CategoryBase(BaseModel):
    """Базовая схема для категории."""
    name: str


class Category(BaseModel):
    """Схема для отображения категории."""
    id: int
    model_config = ConfigDict(from_attributes=True)


class HotelBase(BaseModel):
    """Базовая схема для отеля."""
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    price: Optional[float] = None
    currency: Optional[str] = None


class HotelCreate(HotelBase):
    """Схема для создания отеля."""
    pass


class HotelUpdate(BaseModel):
    """Схема для обновления отеля."""
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    price: Optional[float] = None
    currency: Optional[str] = None


class Hotel(HotelBase):
    """Схема для отображения отеля."""
    id: int
    model_config = ConfigDict(from_attributes=True)


class HotelInDB(HotelBase):
    """Схема для хранения отеля в базе данных."""
    id: int
    model_config = ConfigDict(from_attributes=True)
