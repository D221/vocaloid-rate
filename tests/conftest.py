import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import main, models  # noqa: E402
from app.database import Base  # noqa: E402


@asynccontextmanager
async def noop_lifespan(_app):
    yield


@pytest.fixture
def session_factory() -> Iterator[sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(session_factory) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client_factory(monkeypatch, session_factory):
    monkeypatch.setattr(main.app.router, "lifespan_context", noop_lifespan)

    def _make_client(
        current_user: SimpleNamespace | models.User | None = None,
        optional_user: SimpleNamespace | models.User | None = None,
    ) -> TestClient:
        def override_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides = {main.get_db: override_db}
        if current_user is not None:
            main.app.dependency_overrides[main.get_current_user] = lambda: current_user
        if optional_user is not None:
            main.app.dependency_overrides[main.get_optional_current_user] = lambda: (
                optional_user
            )
        return TestClient(main.app)

    yield _make_client
    main.app.dependency_overrides = {}


@pytest.fixture
def user(db_session: Session) -> models.User:
    db_user = models.User(
        email="user@example.com",
        hashed_password="hashed",
        is_active=True,
        is_admin=False,
    )
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)
    return db_user


@pytest.fixture
def admin_user(db_session: Session) -> models.User:
    db_user = models.User(
        email="admin@example.com",
        hashed_password="hashed",
        is_active=True,
        is_admin=True,
    )
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)
    return db_user


@pytest.fixture
def sample_tracks(db_session: Session) -> list[models.Track]:
    now = datetime.now(timezone.utc)
    tracks = [
        models.Track(
            title="First Track",
            producer="Producer A",
            voicebank="Miku",
            published_date=now - timedelta(days=3),
            link="https://example.com/1",
            title_jp="",
            producer_jp="",
            voicebank_jp="",
            image_url=None,
            rank=1,
        ),
        models.Track(
            title="Second Track",
            producer="Producer B",
            voicebank="Luka",
            published_date=now - timedelta(days=8),
            link="https://example.com/2",
            title_jp="",
            producer_jp="",
            voicebank_jp="",
            image_url=None,
            rank=2,
        ),
        models.Track(
            title="Old Track",
            producer="Producer A",
            voicebank="Rin",
            published_date=now - timedelta(days=60),
            link="https://example.com/3",
            title_jp="",
            producer_jp="",
            voicebank_jp="",
            image_url=None,
            rank=None,
        ),
    ]
    db_session.add_all(tracks)
    db_session.commit()
    for track in tracks:
        db_session.refresh(track)
    return tracks


@pytest.fixture
def playlist(db_session: Session, user: models.User, sample_tracks: list[models.Track]):
    db_playlist = models.Playlist(
        user_id=user.id,
        name="Favorites",
        description="Test playlist",
    )
    db_session.add(db_playlist)
    db_session.commit()
    db_session.refresh(db_playlist)

    associations = [
        models.PlaylistTrack(
            playlist_id=db_playlist.id,
            track_id=sample_tracks[0].id,
            position=0,
        ),
        models.PlaylistTrack(
            playlist_id=db_playlist.id,
            track_id=sample_tracks[1].id,
            position=1,
        ),
    ]
    db_session.add_all(associations)
    db_session.commit()
    db_session.refresh(db_playlist)
    return db_playlist
