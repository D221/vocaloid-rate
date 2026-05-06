from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.requests import Request

from app.dependencies import get_locale
from app.utils.uploads import read_upload_with_size_limit


def make_request(
    query_string: bytes = b"",
    cookies: list[tuple[bytes, bytes]] | None = None,
    accept_language: str | None = None,
) -> Request:
    headers = []
    if cookies:
        cookie_value = b"; ".join([name + b"=" + value for name, value in cookies])
        headers.append((b"cookie", cookie_value))
    if accept_language is not None:
        headers.append((b"accept-language", accept_language.encode()))

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": query_string,
        "headers": headers,
    }
    return Request(scope)


def test_get_locale_prefers_query_then_cookie_then_header():
    assert get_locale(make_request(query_string=b"lang=ja")) == "ja"
    assert get_locale(make_request(cookies=[(b"language", b"ja")])) == "ja"
    assert get_locale(make_request(accept_language="ja,en;q=0.8")) == "ja"
    assert get_locale(make_request()) == "en"


@pytest.mark.anyio
async def test_read_upload_with_size_limit_rejects_large_payload():
    upload = UploadFile(filename="large.json", file=BytesIO(b"x" * 10))

    with pytest.raises(Exception) as exc_info:
        await read_upload_with_size_limit(upload, max_bytes=5)

    assert "File is too large" in str(exc_info.value)
