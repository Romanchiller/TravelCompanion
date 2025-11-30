from fastapi.security import OAuth2PasswordBearer

# Инициализация OAuth2 схем
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
oauth2_optional_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)