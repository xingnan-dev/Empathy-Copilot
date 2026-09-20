"""Environment-only database configuration."""

import os
from dataclasses import dataclass

from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True)
class DatabaseSettings:
    database_url: str

    @classmethod
    def from_environment(cls, *, test: bool = False) -> "DatabaseSettings":
        variable = "TEST_DATABASE_URL" if test else "DATABASE_URL"
        value = os.getenv(variable)
        if not value:
            raise RuntimeError(f"{variable} is required")
        settings = cls(database_url=value)
        settings.validate(test=test)
        return settings

    def validate(self, *, test: bool = False) -> URL:
        url = make_url(self.database_url)
        if url.get_backend_name() != "postgresql":
            raise ValueError("PostgreSQL DATABASE_URL is required")
        if test and "test" not in (url.database or "").casefold():
            raise ValueError("TEST_DATABASE_URL database name must contain 'test'")
        return url
