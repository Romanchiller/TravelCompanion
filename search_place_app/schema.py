from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, model_validator
from typing import Optional, Type


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

class UserPublic(BaseModel):
    id: int
    name: str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)
