"""Run the deterministic demo seed against DATABASE_URL."""

from .config import DatabaseSettings
from .database import create_database_engine, create_session_factory
from .seed import seed_demo_data_transactionally


def main() -> None:
    engine = create_database_engine(DatabaseSettings.from_environment())
    sessions = create_session_factory(engine)
    with sessions() as session:
        seed_demo_data_transactionally(session)
    engine.dispose()


if __name__ == "__main__":
    main()
