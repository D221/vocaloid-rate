from gettext import NullTranslations

import pytest
from fastapi import Response
from starlette.requests import Request

from app import dependencies


class BrokenInfoTranslation(NullTranslations):
    def __init__(self):
        super().__init__()
        self.custom_attr = "custom"

    def info(self):
        raise RuntimeError("broken")


def make_request(path: str = "/", headers=None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
            "headers": headers or [],
        }
    )


@pytest.mark.anyio
async def test_get_slim_mode_true_and_false():
    assert await dependencies.get_slim_mode("true") is True
    assert await dependencies.get_slim_mode("false") is False


def test_translation_proxy_handles_broken_info_and_passthrough():
    proxy = dependencies.TranslationProxy(BrokenInfoTranslation(), "ja")

    assert proxy.gettext("hello") == "hello"
    assert proxy.ngettext("a", "b", 2) == "b"
    assert proxy.info()["language"] == "ja"
    assert proxy.custom_attr == "custom"


def test_get_translations_success_and_fallback(monkeypatch):
    monkeypatch.setattr(
        dependencies.gettext,
        "translation",
        lambda domain, localedir, languages: NullTranslations(),
    )
    success = dependencies.get_translations("en")
    assert success.info()["language"] == "en"

    monkeypatch.setattr(
        dependencies.gettext,
        "translation",
        lambda domain, localedir, languages: (_ for _ in ()).throw(FileNotFoundError()),
    )
    fallback = dependencies.get_translations("ja")
    assert fallback.info()["language"] == "ja"


@pytest.mark.anyio
async def test_locale_template_response_injects_user_and_language_cookie(monkeypatch):
    class DummyDb:
        def close(self):
            pass

    async def fake_optional_current_user(request, token, db):
        return "user"

    monkeypatch.setattr(dependencies, "SessionLocal", lambda: DummyDb())
    monkeypatch.setattr(
        dependencies,
        "get_optional_current_user",
        fake_optional_current_user,
    )
    monkeypatch.setattr(dependencies, "is_local_mode", lambda: False)
    monkeypatch.setattr(
        dependencies.templates,
        "TemplateResponse",
        lambda request, template_name, context: Response("ok"),
    )

    request = make_request(headers=[(b"accept-language", b"ja")])
    translations = dependencies.TranslationProxy(NullTranslations(), "ja")

    response = await dependencies.LocaleTemplateResponse(
        "options.html",
        {"request": request, "_": translations.gettext},
        request,
        translations,
    )

    assert response.headers["set-cookie"].startswith("language=ja")


def test_get_db_closes_session(monkeypatch):
    seen = {"closed": False}

    class DummyDb:
        def close(self):
            seen["closed"] = True

    monkeypatch.setattr(dependencies, "SessionLocal", lambda: DummyDb())
    generator = dependencies.get_db()
    db = next(generator)
    assert db is not None
    with pytest.raises(StopIteration):
        next(generator)
    assert seen["closed"] is True
