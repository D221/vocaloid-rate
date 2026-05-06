from pathlib import Path

import pytest

from app import main


@pytest.mark.anyio
async def test_app_lifespan_skips_migrations_and_scrape_when_tracks_exist(monkeypatch):
    class FakeQuery:
        def count(self):
            return 1

    class FakeSession:
        def query(self, model):
            return FakeQuery()

        def close(self):
            pass

    called = {"migrations": False, "resource": None}

    monkeypatch.setattr(main, "should_run_migrations_on_startup", lambda: False)
    monkeypatch.setattr(main, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        main, "set_resource_base_path", lambda path: called.update(resource=path)
    )
    monkeypatch.setattr(
        main,
        "set_initial_scrape_in_progress",
        lambda value: (_ for _ in ()).throw(AssertionError("should not scrape")),
    )

    async with main.app_lifespan(main.app):
        pass

    assert isinstance(called["resource"], Path)


@pytest.mark.anyio
async def test_app_lifespan_runs_migrations_and_initial_scrape_when_empty(monkeypatch):
    class FakeQuery:
        def count(self):
            return 0

    class FakeSession:
        def query(self, model):
            return FakeQuery()

        def close(self):
            pass

    seen = {"upgrade": False, "scrape_started": False, "thread_started": False}

    class FakeThread:
        def __init__(self, target):
            seen["scrape_started"] = target is main.initial_scrape_task

        def start(self):
            seen["thread_started"] = True

    monkeypatch.setattr(main, "should_run_migrations_on_startup", lambda: True)
    monkeypatch.setattr(main, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        main.command, "upgrade", lambda cfg, head: seen.update(upgrade=True)
    )
    monkeypatch.setattr(main.threading, "Thread", FakeThread)
    monkeypatch.setattr(main, "set_initial_scrape_in_progress", lambda value: None)
    monkeypatch.setattr(main, "write_scrape_status", lambda value: None)

    async with main.app_lifespan(main.app):
        pass

    assert seen["upgrade"] is True
    assert seen["scrape_started"] is True
    assert seen["thread_started"] is True
