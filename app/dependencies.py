import gettext
import logging
from gettext import NullTranslations
from typing import Optional

from babel.support import Translations
from fastapi import Cookie, Depends, Request
from fastapi.templating import Jinja2Templates

from app.auth import get_optional_current_user
from app.config import is_local_mode
from app.constants import (
    BASE_DIR,
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    get_resource_base_path,
)
from app.database import SessionLocal

templates = Jinja2Templates(directory=BASE_DIR / "templates")


async def get_slim_mode(viewModeSlim: Optional[str] = Cookie(None)) -> bool:
    return viewModeSlim == "true"


def get_locale(request: Request) -> str:
    lang_query = request.query_params.get("lang")
    if lang_query and lang_query in SUPPORTED_LOCALES:
        return lang_query

    lang_cookie = request.cookies.get("language")
    if lang_cookie and lang_cookie in SUPPORTED_LOCALES:
        return lang_cookie

    accept_language = request.headers.get("accept-language")
    if accept_language:
        for lang_code in accept_language.split(","):
            lang_code_clean = lang_code.strip().split(";")[0].lower()

            if lang_code_clean in SUPPORTED_LOCALES:
                return lang_code_clean

            base_lang = lang_code_clean.split("-")[0]
            if base_lang in SUPPORTED_LOCALES:
                return base_lang

    return DEFAULT_LOCALE


class TranslationProxy(Translations):
    def __init__(
        self, inner_translation: Translations | NullTranslations, language: str
    ):
        self._inner = inner_translation
        self._language = language

    def gettext(self, message: str) -> str:
        return self._inner.gettext(message)

    def ngettext(self, msgid1: str, msgid2: str, n: int) -> str:
        return self._inner.ngettext(msgid1, msgid2, n)

    def info(self) -> dict:
        data = {}
        if hasattr(self._inner, "info"):
            try:
                data.update(self._inner.info())
            except Exception:
                data = {}
        data.setdefault("language", self._language)
        return data

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def get_translations(
    locale: str = Depends(get_locale),
) -> Translations | NullTranslations:
    base_path = get_resource_base_path()
    locales_path = base_path / "locales"

    try:
        logging.info(
            "Attempting to load translations from: %s for locale %s",
            locales_path,
            locale,
        )
        translations = gettext.translation(
            "messages", localedir=str(locales_path), languages=[locale]
        )
        return TranslationProxy(translations, locale)
    except Exception:
        logging.warning(
            "Translations not found for %s at %s. Falling back to default.",
            locale,
            locales_path,
        )
        return TranslationProxy(NullTranslations(), locale)


async def locale_template_response(
    template_name: str,
    context: dict,
    request: Request,
    translations: Translations,
):
    context["locale"] = translations.info()["language"]
    context["is_local_env"] = is_local_mode()

    if "current_user" not in context:
        db = SessionLocal()
        try:
            user = await get_optional_current_user(request, None, db)
            context["current_user"] = user
        finally:
            db.close()

    response = templates.TemplateResponse(request, template_name, context)
    response.set_cookie(key="language", value=get_locale(request))
    return response


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
