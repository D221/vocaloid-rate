from contextlib import asynccontextmanager

import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import main


@asynccontextmanager
async def noop_lifespan(_app):
    yield


@pytest.fixture
def bare_client(monkeypatch):
    monkeypatch.setattr(main.app.router, "lifespan_context", noop_lifespan)
    return TestClient(main.app)


def test_static_assets_get_cache_control_header(bare_client):
    response = bare_client.get("/static/js/main.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=86400"


def test_service_worker_route_sets_allowed_header(bare_client):
    response = bare_client.get("/static/sw.js")

    assert response.status_code == 200
    assert response.headers["service-worker-allowed"] == "/"


def test_service_worker_404_when_missing(monkeypatch, bare_client):
    class MissingPath:
        def __truediv__(self, other):
            return self

        def exists(self):
            return False

    monkeypatch.setattr(main, "BASE_DIR", MissingPath())

    response = bare_client.get("/static/sw.js")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_cache_middleware_leaves_non_static_requests_untouched():
    async def call_next(_request):
        return Response("ok")

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [],
        }
    )

    response = await main.add_cache_control_header(request, call_next)

    assert "Cache-Control" not in response.headers
