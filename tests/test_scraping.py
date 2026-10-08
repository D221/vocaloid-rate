from app.routers import scraping as scraping_router


def _ranking_row(
    title="Test Song",
    producer="Test Producer",
    voicebank="Miku",
    published="2026/09/20",
    image="https://i.ytimg.com/vi/abc/mqdefault.jpg",
    rank="3",
    link="https://www.youtube.com/watch?v=abc",
):
    return f"""
    <div class="RankingItem area">
      <a href="{link}">watch</a>
      <span class="song-title">{title}</span>
      <span class="artists">{producer}</span>
      <span class="singers">{voicebank}</span>
      <span class="published">{published}</span>
      <span class="image-area"><img src="{image}" /></span>
      <span class="rank-p">{rank}</span>
    </div>
    """


def _fake_fetch_factory(monkeypatch, html_en, html_jp, seen_urls=None):
    from types import SimpleNamespace

    from app import scraper as scraper_module

    def fake_fetch(url):
        if seen_urls is not None:
            seen_urls.append(url)
        if "injpok.tokyo/en" in url:
            return SimpleNamespace(content=html_en.encode("utf-8"))
        return SimpleNamespace(content=html_jp.encode("utf-8"))

    monkeypatch.setattr(scraper_module, "_fetch_page", fake_fetch)


def test_scrape_requires_admin_when_not_local(client_factory, monkeypatch, user):
    client = client_factory(current_user=user)
    monkeypatch.setattr(scraping_router, "is_local_mode", lambda: False)

    response = client.post("/scrape")

    assert response.status_code == 403
    assert (
        response.json()["detail"] == "Only admins can trigger scraping in cloud mode."
    )


def test_scrape_starts_for_admin_and_resets_status(
    client_factory,
    monkeypatch,
    admin_user,
):
    client = client_factory(current_user=admin_user)
    seen = {"status": None, "called": False}

    monkeypatch.setattr(
        scraping_router, "write_scrape_status", lambda value: seen.update(status=value)
    )
    monkeypatch.setattr(
        scraping_router,
        "scrape_and_populate_task",
        lambda: seen.update(called=True),
    )

    response = client.post("/scrape")

    assert response.status_code == 200
    assert seen["status"] == "idle"
    assert seen["called"] is True


def test_cron_scrape_requires_secret(client_factory, monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    client = client_factory()

    response = client.get("/api/cron/scrape")

    assert response.status_code == 503


def test_cron_scrape_requires_valid_bearer_token(client_factory, monkeypatch):
    client = client_factory()
    monkeypatch.setenv("CRON_SECRET", "secret")
    seen = {"called": False}
    monkeypatch.setattr(
        scraping_router,
        "scrape_and_populate_task",
        lambda: seen.update(called=True),
    )

    bad_response = client.get("/api/cron/scrape")
    good_response = client.get(
        "/api/cron/scrape",
        headers={"Authorization": "Bearer secret"},
    )

    assert bad_response.status_code == 401
    assert good_response.status_code == 200
    assert seen["called"] is True


def test_scrape_status_endpoint_uses_service_read(client_factory, monkeypatch):
    client = client_factory()
    monkeypatch.setattr(
        scraping_router, "read_scrape_status", lambda: "in_progress:2/6"
    )

    response = client.get("/api/scrape-status")

    assert response.status_code == 200
    assert response.json() == {"status": "in_progress:2/6"}


def test_scrape_single_page_parses_en_and_jp_rows(monkeypatch):
    from app import scraper as scraper_module

    html_en = (
        f"<html><body>{_ranking_row()}"
        f"{_ranking_row(title='Second', rank='4')}</body></html>"
    )
    html_jp = (
        f"<html><body>{_ranking_row(title='テストソング')}"
        f"{_ranking_row(title='Second', rank='4')}</body></html>"
    )
    _fake_fetch_factory(monkeypatch, html_en, html_jp)

    tracks = scraper_module._scrape_single_page(1)

    assert len(tracks) == 2
    first = tracks[0]
    assert first["title"] == "Test Song"
    assert first["title_jp"] == "テストソング"
    assert first["producer"] == "Test Producer"
    assert first["voicebank"] == "Miku"
    assert first["rank"] == 3
    assert first["link"] == "https://www.youtube.com/watch?v=abc"
    assert first["image_url"] == "https://i.ytimg.com/vi/abc/mqdefault.jpg"
    assert (first["published_date"].year, first["published_date"].month) == (
        2026,
        9,
    )
    assert tracks[1]["title_jp"] is None


def test_scrape_single_page_returns_empty_on_fetch_error(monkeypatch):
    import requests

    from app import scraper as scraper_module

    def boom(url):
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(scraper_module, "_fetch_page", boom)

    assert scraper_module._scrape_single_page(1) == []


def test_scrape_single_page_skips_rows_missing_elements(monkeypatch):
    from app import scraper as scraper_module

    broken = '<div class="RankingItem area"><span class="song-title">Nope</span></div>'
    html = f"<html><body>{broken}{_ranking_row()}</body></html>"
    _fake_fetch_factory(monkeypatch, html, html)

    tracks = scraper_module._scrape_single_page(1)

    assert [track["title"] for track in tracks] == ["Test Song"]


def test_scrape_single_page_uses_historical_urls_for_date(monkeypatch):
    from app import scraper as scraper_module

    seen = []
    html = f"<html><body>{_ranking_row()}</body></html>"
    _fake_fetch_factory(monkeypatch, html, html, seen_urls=seen)

    scraper_module._scrape_single_page(2, date="2026-09-01")

    assert len(seen) == 2
    assert any("?d=2026-09-01&g=2" in url for url in seen)
    assert any(url.startswith("https://vocaloard.injpok.tokyo/en/") for url in seen)
    assert "https://vocaloard.injpok.tokyo/?d=2026-09-01&g=2" in seen


def test_fetch_page_returns_response_on_success(monkeypatch):
    import requests

    from app import scraper as scraper_module

    seen = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            seen["raised"] = True

    monkeypatch.setattr(requests, "get", lambda url, timeout: FakeResponse())

    response = scraper_module._fetch_page("https://example.com/x")

    assert response.status_code == 200
    assert seen == {"raised": True}


def test_fetch_page_raises_for_http_error(monkeypatch):
    import requests

    from app import scraper as scraper_module

    class BadResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("500")

    monkeypatch.setattr(requests, "get", lambda url, timeout: BadResponse())

    try:
        scraper_module._fetch_page("https://example.com/x")
    except requests.exceptions.HTTPError:
        pass
    else:
        raise AssertionError("expected HTTPError")


def test_scrape_single_page_skips_row_with_bad_date(monkeypatch):
    from app import scraper as scraper_module

    html = (
        f"<html><body>{_ranking_row(published='not-a-date')}"
        f"{_ranking_row(title='Good')}</body></html>"
    )
    _fake_fetch_factory(monkeypatch, html, html)

    tracks = scraper_module._scrape_single_page(1)

    assert [track["title"] for track in tracks] == ["Good"]
