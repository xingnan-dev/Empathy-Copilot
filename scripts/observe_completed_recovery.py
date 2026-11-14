"""Experiment-only CLI wrapper: instrument the factory, then execute the original CLI main."""

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from scripts import resume_completed_recovery as original  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation-id", required=True)
    parser.add_argument("--control-case")
    args, remaining = parser.parse_known_args()
    engine = original.create_database_engine(original.DatabaseSettings.from_environment())
    factory = original.build_postgres_workflow
    actor = "offline-cli-" + uuid4().hex

    def event(kind: str) -> None:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO w3_observation.events(experiment,actor,kind,details) "
                    "VALUES (:experiment,:actor,:kind,CAST(:details AS jsonb))"
                ),
                dict(
                    experiment=args.observation_id,
                    actor=actor,
                    kind=kind,
                    details=json.dumps(dict(pid=os.getpid(), path="original CLI factory wrapper")),
                ),
            )

    def observed_factory(sessions):
        workflow = factory(sessions)
        execute = workflow.tools.execute

        def observed_execute(name, state, arguments):
            if name == "get_order_history":
                event("TOOL_ENTRY")
            result = execute(name, state, arguments)
            if name == "get_order_history":
                event("TOOL_RETURN")
            return result

        workflow.tools.execute = observed_execute
        event("CLI_OBSERVER_INSTALLED")
        return workflow

    original.build_postgres_workflow = observed_factory
    previous_argv = sys.argv
    try:
        if args.control_case:
            if args.control_case != args.observation_id:
                raise ValueError("control case must use its own observation identity")
            workflow = observed_factory(original.create_session_factory(engine))
            state = workflow.restore_case(args.control_case)
            workflow.tools.execute("get_order_history", state, {"consumer_id": state.consumer_id})
            print(json.dumps(dict(control_case=args.control_case, actor=actor)))
        else:
            sys.argv = [str(Path(original.__file__)), *remaining]
            original.main()
    finally:
        sys.argv = previous_argv
        original.build_postgres_workflow = factory
        engine.dispose()


if __name__ == "__main__":
    main()
