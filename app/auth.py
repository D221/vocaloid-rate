import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import crud, schemas
from app.config import get_secret_key, is_local_auth_mode
from app.database import SessionLocal
from app.security import ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
LOCAL_DEFAULT_EMAIL = "local@vocaloid-rate.local"


def get_or_create_local_user(db: Session) -> crud.models.User:
    user = crud.get_user_by_email(db, email=LOCAL_DEFAULT_EMAIL)
    if user:
        if not user.is_admin:
            user.is_admin = True
            db.commit()
            db.refresh(user)
        return user

    temp_password = secrets.token_urlsafe(24)
    user = crud.create_user(
        db, schemas.UserCreate(email=LOCAL_DEFAULT_EMAIL, password=temp_password)
    )
    user.is_admin = True
    db.commit()
    db.refresh(user)
    return user


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt expects bytes
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    # bcrypt expects bytes, and returns a hashed byte string
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    return hashed_password.decode("utf-8")


def authenticate_user(
    db: Session, identifier: str, password: str
) -> Optional[crud.models.User]:
    user = crud.get_user_by_email(db, email=identifier)
    if not user:
        user = crud.get_user_by_username(db, username=identifier)

    if not user:
        logging.warning("Auth failed: User %s not found", identifier)
        return None

    if not verify_password(password, user.hashed_password):
        logging.warning("Auth failed: Incorrect password for user %s", identifier)
        return None

    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    secret_key = get_secret_key()
    if secret_key is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: SECRET_KEY not set",
        )
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    request: Request,  # Add request
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> crud.models.User:
    if is_local_auth_mode():
        return get_or_create_local_user(db)

    if token is None:
        token = request.cookies.get("access_token")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret_key = get_secret_key()
    if secret_key is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: SECRET_KEY not set",
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user


async def get_optional_current_user(
    request: Request,  # Add request
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[crud.models.User]:
    if is_local_auth_mode():
        return get_or_create_local_user(db)

    if token is None:
        token = request.cookies.get("access_token")

    if token is None:
        return None
    secret_key = get_secret_key()
    if secret_key is None:
        return None
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None
    return crud.get_user_by_email(db, email=email)
