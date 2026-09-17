from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config

bearer = HTTPBearer(auto_error=False)
jwks_client = jwt.PyJWKClient(config.KEYCLOAK_JWKS_URL, cache_keys=True, lifespan=600)


@dataclass
class User:
    login: str
    roles: list[str]


def decode_token(token: str) -> dict:
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    # aud не проверяем: у access-токена публичного клиента Keycloak его по умолчанию нет,
    # вместо этого ниже сверяется azp
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=config.KEYCLOAK_ISSUER,
        options={"verify_aud": False, "require": ["exp", "iat", "iss"]},
    )


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется аутентификация",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_token(credentials.credentials)
    except (jwt.PyJWTError, jwt.PyJWKClientError):
        raise unauthorized

    login = claims.get("preferred_username")
    if not login or claims.get("azp") not in config.ALLOWED_CLIENTS:
        raise unauthorized

    return User(login=login, roles=claims.get("realm_access", {}).get("roles", []))


def report_user(user: User = Depends(current_user)) -> User:
    if config.REPORTS_ROLE not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Отчёты доступны только пользователям с ролью {config.REPORTS_ROLE}",
        )
    return user
