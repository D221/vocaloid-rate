from app.routers import scraping as scraping_router


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


def test_cron_scrape_requires_secret(client_factory):
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
