"""Small application-service factory suitable for future FastAPI dependencies."""

from sqlalchemy.orm import Session, sessionmaker

from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.repositories.postgres import PostgresRepositoryBundle
from backend.app.services.tools import default_tool_registry

from .checkpoints import PostgresCheckpointStore


def build_postgres_workflow(
    sessions: sessionmaker[Session],
) -> InvestigationWorkflow:
    repositories = PostgresRepositoryBundle(sessions)
    return InvestigationWorkflow(
        checkpoint_store=PostgresCheckpointStore(sessions),
        tool_registry=default_tool_registry(repositories),
    )
