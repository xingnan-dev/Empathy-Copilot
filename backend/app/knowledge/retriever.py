import json
import re
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter

from .schemas import KnowledgeItem, KnowledgeType


class KnowledgeRetriever(Protocol):
    def retrieve(
        self, query: str, *, knowledge_types: set[KnowledgeType] | None = None, limit: int = 3
    ) -> list[KnowledgeItem]: ...


class LocalKnowledgeRetriever:
    def __init__(self, path: Path | None = None) -> None:
        source = path or (
            Path(__file__).resolve().parents[2] / "data" / "knowledge" / "phase8_demo.json"
        )
        with source.open(encoding="utf-8") as handle:
            self.items = TypeAdapter(list[KnowledgeItem]).validate_python(json.load(handle))

    def retrieve(
        self, query: str, *, knowledge_types: set[KnowledgeType] | None = None, limit: int = 3
    ) -> list[KnowledgeItem]:
        terms = {term.casefold() for term in re.findall(r"[\w\u4e00-\u9fff]+", query)}
        ranked = []
        for item in self.items:
            if knowledge_types and item.knowledge_type not in knowledge_types:
                continue
            text = f"{item.title} {item.section} {item.content}".casefold()
            matches = sum(term in text for term in terms)
            if matches:
                ranked.append(
                    item.model_copy(update={"retrieval_score": min(1.0, matches / len(terms))})
                )
        return sorted(ranked, key=lambda item: item.retrieval_score or 0, reverse=True)[:limit]
