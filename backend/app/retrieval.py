"""Hybrid retrieval (CLAUDE.md §12): semantic (cosine over embeddings) + keyword
overlap + structured filters, fused and reranked. At KB scale (~dozens of entities)
brute-force numpy is exact and instant — no vector DB needed (ADR-002)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import settings
from .models import EntityType, EvidenceRef, KBEntity, SUPPORTED_STATUSES
from .providers.embeddings import EmbeddingProvider, get_embedding_provider
from .text_utils import keyword_overlap


@dataclass
class ScoredEntity:
    entity: KBEntity
    score: float
    semantic: float
    keyword: float

    def to_evidence(self) -> EvidenceRef:
        snippet = self.entity.content
        return EvidenceRef(
            entity_id=self.entity.id, entity_type=self.entity.entity_type,
            name=self.entity.name, snippet=snippet[:240],
            score=round(self.score, 4), status=self.entity.status)


class RetrievalIndex:
    def __init__(self, entities: list[KBEntity], embedder: EmbeddingProvider | None = None):
        self.entities = entities
        self.embedder = embedder or get_embedding_provider()
        corpus = [e.content for e in entities]
        self.embedder.fit(corpus)
        self.matrix = (self.embedder.embed(corpus) if entities
                       else np.zeros((0, 1)))

    def search(self, query: str, *, top_k: int | None = None,
               entity_types: list[EntityType] | None = None) -> list[ScoredEntity]:
        if not self.entities:
            return []
        top_k = top_k or settings.retrieval_top_k
        qvec = self.embedder.embed([query])[0]
        sims = self.matrix @ qvec  # rows are L2-normalised -> cosine
        sw, kw_w = settings.semantic_weight, settings.keyword_weight

        scored: list[ScoredEntity] = []
        for i, ent in enumerate(self.entities):
            if entity_types and ent.entity_type not in entity_types:
                continue
            sem = float(sims[i])
            kw = keyword_overlap(query, ent.content)
            scored.append(ScoredEntity(ent, sw * sem + kw_w * kw, sem, kw))

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]


def build_index(candidate_id: int, *, supported_only: bool = True) -> RetrievalIndex:
    from . import db
    statuses = SUPPORTED_STATUSES if supported_only else None
    entities = db.get_entities(candidate_id, statuses=statuses)
    return RetrievalIndex(entities)
