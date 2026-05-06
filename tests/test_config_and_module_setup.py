import importlib
from pathlib import Path

from app import config


def test_config_helpers_cover_environment_branches(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RUN_MIGRATIONS_ON_STARTUP", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    assert config.is_frozen_build() is False
    assert config.get_database_url() is None
    assert config.get_data_dir() == tmp_path
    assert config.is_local_mode() is True
    assert config.is_local_auth_mode() is True
    assert config.should_use_secure_cookies() is False
    assert config.should_run_migrations_on_startup() is True
    assert config.get_secret_key() is None

    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    assert config.get_database_url() is None
    monkeypatch.delattr(config.sys, "frozen", raising=False)

    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")
    monkeypatch.setenv("SECRET_KEY", "secret")

    assert config.get_database_url() == "postgres://example"
    assert config.is_local_mode() is False
    assert config.should_use_secure_cookies() is True
    assert config.should_run_migrations_on_startup() is False
    assert config.get_secret_key() == "secret"


def test_constants_and_database_modules_cover_fallback_paths(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VERCEL", raising=False)

    import app.constants as constants_module
    import app.database as database_module
    import app.config as config_module

    monkeypatch.setattr(config_module, "get_database_url", lambda: None)
    monkeypatch.setattr(config_module, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(config_module, "is_vercel", lambda: True)

    constants = importlib.reload(constants_module)
    database = importlib.reload(database_module)
    try:
        assert constants.SCRAPE_STATUS_FILE.endswith("scrape_status.txt")
        assert "/tmp" in constants.SCRAPE_STATUS_FILE.replace("\\", "/")
        assert database.SQLALCHEMY_DATABASE_URL.startswith("sqlite:///")
        assert database.connect_args["check_same_thread"] is False
        assert Path(constants.get_resource_base_path()).exists()

        constants.set_resource_base_path(tmp_path)
        assert constants.get_resource_base_path() == tmp_path
    finally:
        importlib.reload(constants_module)
        importlib.reload(database_module)
