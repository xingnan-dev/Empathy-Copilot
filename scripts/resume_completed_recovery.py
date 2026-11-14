"""Offline continuation only: stop and wait for the single API process before running."""

import argparse
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.persistence.config import DatabaseSettings  # noqa: E402
from backend.app.persistence.database import (  # noqa: E402
    create_database_engine,
    create_session_factory,
)
from backend.app.persistence.factory import build_postgres_workflow  # noqa: E402
from backend.app.services.tool_recovery import ToolRecoveryService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--request-id", required=True, type=UUID)
    args = parser.parse_args()
    engine = create_database_engine(DatabaseSettings.from_environment())
    try:
        workflow = build_postgres_workflow(create_session_factory(engine))
        service = ToolRecoveryService(workflow)
        service.resume_completed(args.case_id, args.request_id)
        print(service.get(args.case_id, args.request_id).model_dump_json())
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
