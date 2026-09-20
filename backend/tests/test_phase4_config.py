import pytest

from backend.app.persistence.config import DatabaseSettings


def test_database_settings_require_postgresql() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        DatabaseSettings("sqlite:///local.db").validate()


def test_test_database_name_must_be_explicitly_isolated() -> None:
    with pytest.raises(ValueError, match="contain 'test'"):
        DatabaseSettings("postgresql+psycopg://u:p@localhost/production").validate(test=True)


def test_missing_database_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        DatabaseSettings.from_environment()
