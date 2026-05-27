import logging
from datetime import timedelta

from babel.support import Translations
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.auth import create_access_token, get_optional_current_user, get_current_user
from app.dependencies import get_db, get_translations, templates
from app.security import ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(tags=["Authentication"])


def _main_module():
    from app import main

    return main


@router.post("/token", status_code=204)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Response:
    main = _main_module()
    if main.is_local_auth_mode():
        raise HTTPException(
            status_code=404, detail="Authentication is disabled in local mode"
        )

    logging.info("Login attempt for username: %s", form_data.username)
    user = main.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        logging.warning(
            "Login failed: Incorrect username or password for %s",
            form_data.username,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logging.info("Login successful for user: %s", user.email)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    response = Response(status_code=204)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=main.should_use_secure_cookies(),
    )
    return response


@router.post("/users/", response_model=schemas.User)
def create_user(
    response: Response, user: schemas.UserCreate, db: Session = Depends(get_db)
) -> models.User:
    main = _main_module()
    if main.is_local_auth_mode():
        raise HTTPException(
            status_code=404, detail="Authentication is disabled in local mode"
        )

    logging.info("Registration attempt for email: %s", user.email)
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        logging.warning("Registration failed: Email %s already exists", user.email)
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        new_user = crud.create_user(db=db, user=user)
        logging.info(
            "Successfully created user: %s with ID: %s",
            new_user.email,
            new_user.id,
        )

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": new_user.email}, expires_delta=access_token_expires
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            secure=main.should_use_secure_cookies(),
        )

        return new_user
    except Exception as exc:
        logging.error("Database error during user creation: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during registration"
        )


@router.get("/users/me/")
async def read_users_me(
    request: Request,
    current_user: models.User | None = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
) -> Response:
    if _main_module().is_local_auth_mode():
        return Response(content="", media_type="text/html")

    context = {
        "request": request,
        "_": translations.gettext,
        "current_user": current_user,
    }
    return templates.TemplateResponse(request, "partials/user_status.html", context)


@router.post("/logout")
async def logout(response: Response) -> Response:
    main = _main_module()
    response.status_code = 204
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="lax",
        secure=main.should_use_secure_cookies(),
    )
    return response


@router.put("/api/users/me/profile", status_code=204)
def update_profile(
    profile_data: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> Response:
    main = _main_module()
    if main.is_local_auth_mode():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile settings are not available in local mode",
        )

    # Check if username is already taken by another user
    existing_user = (
        db.query(models.User)
        .filter(
            models.User.username.ilike(profile_data.username),
            models.User.id != current_user.id,
        )
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already taken"
        )

    crud.update_user_profile(
        db,
        user=current_user,
        username=profile_data.username,
        is_profile_public=profile_data.is_profile_public,
    )
    return Response(status_code=204)
