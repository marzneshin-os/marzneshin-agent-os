"""Grounded Notebook Knowledge Engine — Core Library.

Synthesizes the NotebookLM paradigm (citation-anchored knowledge exploration,
document grounding, source verification) with the Antigravity paradigm
(autonomous goal execution, tool orchestration, code generation).

Architectural Reference: Liam Turner (@liam_turner_ai, Oct 4, 2026).
Governing Standard: ADR-026, BUILD-SPEC.md v2.0 §4, ADR-001 (D6 virtual clock).

Pure Python standard library only.
Strictly compliant with scripts/verify.py --lint-imports and --lint-clock.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from scripts.lib import clock, paths
except ImportError:
    try:
        from lib import clock, paths
    except ImportError:
        import clock  # type: ignore


_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "this", "but", "they", "have",
    "had", "what", "when", "where", "who", "which", "why", "how",
}


def _tokenize(text: str) -> list[str]:
    """Extract lowercased alphanumeric tokens excluding standard stop words."""
    words = re.findall(r"[a-zA-Z0-9_-]{2,}", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class CitationAnchor:
    source_id: str
    source_name: str
    start_line: int
    end_line: int
    content_hash: str
    preview: str

    def format_citation(self) -> str:
        return f"[{self.source_name}#L{self.start_line}-L{self.end_line}]"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_hash": self.content_hash,
            "preview": self.preview,
            "citation": self.format_citation(),
        }


@dataclass
class SourceChunk:
    chunk_id: str
    source_id: str
    source_name: str
    start_line: int
    end_line: int
    content: str
    content_hash: str
    tokens: list[str] = field(default_factory=list)

    def to_citation(self) -> CitationAnchor:
        preview = self.content.strip().replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "..."
        return CitationAnchor(
            source_id=self.source_id,
            source_name=self.source_name,
            start_line=self.start_line,
            end_line=self.end_line,
            content_hash=self.content_hash,
            preview=preview,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "content_hash": self.content_hash,
            "token_count": len(self.tokens),
        }


@dataclass
class SourceDocument:
    source_id: str
    source_name: str
    source_path: str
    content_hash: str
    total_lines: int
    total_chunks: int
    added_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GroundedQueryResult:
    query: str
    total_chunks_matched: int
    citations: list[dict[str, Any]]
    excerpts: list[dict[str, Any]]
    synthesized_context: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GroundingVerification:
    statement: str
    supported: bool
    confidence: float
    supporting_citations: list[dict[str, Any]]
    unsupported_aspects: list[str]
    matched_terms: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceSynthesis:
    topic: str
    sources_consulted: list[str]
    citations: list[dict[str, Any]]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GroundedNotebook:
    """An isolated, citation-grounded knowledge notebook."""

    def __init__(
        self,
        notebook_id: str,
        title: str,
        description: str = "",
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> None:
        self.notebook_id = notebook_id
        self.title = title
        self.description = description
        now_iso = clock.now().isoformat()
        self.created_at = created_at or now_iso
        self.updated_at = updated_at or now_iso
        self.sources: dict[str, SourceDocument] = {}
        self.chunks: list[SourceChunk] = []

    def ingest_text(
        self,
        content: str,
        source_name: str,
        source_path: str = "inline",
        max_chunk_lines: int = 35,
        overlap_lines: int = 5,
    ) -> SourceDocument:
        """Ingests text, chunks deterministically, and preserves line spans."""
        source_id = "src-" + _sha256(source_name + ":" + content)[:12]
        lines = content.splitlines()
        total_lines = len(lines)
        doc_hash = _sha256(content)

        # Chunk lines deterministically
        start = 0
        doc_chunks: list[SourceChunk] = []
        while start < total_lines:
            end = min(start + max_chunk_lines, total_lines)
            chunk_slice = lines[start:end]
            chunk_text = "\n".join(chunk_slice)
            chunk_hash = _sha256(chunk_text)
            chunk_id = f"{source_id}-chk-{len(doc_chunks):04d}"
            
            sc = SourceChunk(
                chunk_id=chunk_id,
                source_id=source_id,
                source_name=source_name,
                start_line=start + 1,  # 1-indexed
                end_line=end,
                content=chunk_text,
                content_hash=chunk_hash,
                tokens=_tokenize(chunk_text),
            )
            doc_chunks.append(sc)
            if end >= total_lines:
                break
            start += max(1, max_chunk_lines - overlap_lines)

        self.chunks.extend(doc_chunks)
        doc = SourceDocument(
            source_id=source_id,
            source_name=source_name,
            source_path=source_path,
            content_hash=doc_hash,
            total_lines=total_lines,
            total_chunks=len(doc_chunks),
            added_at=clock.now().isoformat(),
        )
        self.sources[source_id] = doc
        self.updated_at = clock.now().isoformat()
        return doc

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> GroundedQueryResult:
        """Query notebook with BM25-style lexical scoring and citation generation."""
        q_tokens = _tokenize(query_text)
        if not q_tokens or not self.chunks:
            return GroundedQueryResult(
                query=query_text,
                total_chunks_matched=0,
                citations=[],
                excerpts=[],
                synthesized_context="No relevant grounded source chunks found.",
            )

        # Compute document frequencies
        df: dict[str, int] = {}
        for chk in self.chunks:
            seen = set(chk.tokens)
            for t in q_tokens:
                if t in seen:
                    df[t] = df.get(t, 0) + 1

        n_chunks = len(self.chunks)
        idf: dict[str, float] = {}
        for t, count in df.items():
            idf[t] = math.log((n_chunks - count + 0.5) / (count + 0.5) + 1.0)

        # Score chunks with BM25-style weighting
        avg_len = sum(len(c.tokens) for c in self.chunks) / max(1, n_chunks)
        k1 = 1.2
        b = 0.75

        scored_chunks: list[tuple[float, SourceChunk]] = []
        for chk in self.chunks:
            score = 0.0
            chk_len = len(chk.tokens) or 1
            matched_terms = 0
            for t in q_tokens:
                if t in chk.tokens:
                    matched_terms += 1
                    tf = chk.tokens.count(t)
                    term_score = idf.get(t, 1.0) * (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (chk_len / avg_len)))
                    score += term_score
            # Add coverage bonus for multi-word queries
            if matched_terms > 0:
                score *= (1.0 + 0.5 * (matched_terms / len(q_tokens)))
            if score > min_score:
                scored_chunks.append((score, chk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top = scored_chunks[:top_k]

        citations: list[dict[str, Any]] = []
        excerpts: list[dict[str, Any]] = []
        context_parts: list[str] = []

        for score, chk in top:
            anchor = chk.to_citation()
            citations.append(anchor.to_dict())
            excerpts.append({
                "citation": anchor.format_citation(),
                "score": round(score, 4),
                "start_line": chk.start_line,
                "end_line": chk.end_line,
                "content": chk.content,
            })
            context_parts.append(
                f"--- Citation: {anchor.format_citation()} (Score: {score:.3f}) ---\n{chk.content}"
            )

        synthesized = "\n\n".join(context_parts) if context_parts else "No matching chunks found."

        return GroundedQueryResult(
            query=query_text,
            total_chunks_matched=len(top),
            citations=citations,
            excerpts=excerpts,
            synthesized_context=synthesized,
        )

    def synthesize(self, topic: str, top_k: int = 5) -> SourceSynthesis:
        """Cross-references multiple sources matching a topic with source attribution."""
        res = self.query(topic, top_k=top_k, min_score=0.02)
        sources_seen = set()
        for c in res.citations:
            sources_seen.add(c["source_name"])

        summary_lines = [
            f"Topic Synthesis: '{topic}'",
            f"Sources Consulted: {', '.join(sorted(sources_seen)) if sources_seen else 'None'}",
            f"Matched Evidence Units: {len(res.citations)} citations.",
            "",
            "Key Grounded Insights:",
        ]
        for exc in res.excerpts:
            first_line = exc["content"].splitlines()[0] if exc["content"] else ""
            summary_lines.append(f"• {exc['citation']}: {first_line}")

        return SourceSynthesis(
            topic=topic,
            sources_consulted=sorted(list(sources_seen)),
            citations=res.citations,
            summary="\n".join(summary_lines),
        )

    def verify_grounding(self, statement: str, threshold: float = 0.2) -> GroundingVerification:
        """Adversarial verification: checks if a statement is supported by indexed sources."""
        st_tokens = _tokenize(statement)
        if not st_tokens:
            return GroundingVerification(
                statement=statement,
                supported=False,
                confidence=0.0,
                supporting_citations=[],
                unsupported_aspects=["Statement contains no extractable query tokens."],
                matched_terms=[],
            )

        res = self.query(statement, top_k=3, min_score=0.01)
        if not res.excerpts:
            return GroundingVerification(
                statement=statement,
                supported=False,
                confidence=0.0,
                supporting_citations=[],
                unsupported_aspects=["No indexed source chunks match statement terms."],
                matched_terms=[],
            )

        # Check token coverage in top excerpt
        matched: set[str] = set()
        for exc in res.excerpts:
            chunk_tokens = set(_tokenize(exc["content"]))
            matched.update(t for t in st_tokens if t in chunk_tokens)

        coverage = len(matched) / max(1, len(set(st_tokens)))
        is_supported = coverage >= threshold
        unsupported = [t for t in set(st_tokens) if t not in matched]

        return GroundingVerification(
            statement=statement,
            supported=is_supported,
            confidence=round(coverage, 3),
            supporting_citations=res.citations,
            unsupported_aspects=[f"Missing evidence for: {', '.join(unsupported[:5])}"] if unsupported else [],
            matched_terms=sorted(list(matched)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "notebook_id": self.notebook_id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "sources": {sid: doc.to_dict() for sid, doc in self.sources.items()},
            "chunks_count": len(self.chunks),
            "chunks": [c.to_dict() for c in self.chunks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroundedNotebook:
        nb = cls(
            notebook_id=data["notebook_id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
        for sid, sdata in data.get("sources", {}).items():
            nb.sources[sid] = SourceDocument(**sdata)
        for cdata in data.get("chunks", []):
            sc = SourceChunk(
                chunk_id=cdata["chunk_id"],
                source_id=cdata["source_id"],
                source_name=cdata["source_name"],
                start_line=cdata["start_line"],
                end_line=cdata["end_line"],
                content=cdata["content"],
                content_hash=cdata["content_hash"],
                tokens=_tokenize(cdata["content"]),
            )
            nb.chunks.append(sc)
        return nb


class NotebookStore:
    """Filesystem-backed persistence for knowledge notebooks in state/notebooks/."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        if root_dir is None:
            repo = Path(__file__).resolve().parent.parent.parent
            self.root_dir = repo / "state" / "notebooks"
        else:
            self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, notebook_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", notebook_id)
        return self.root_dir / f"{safe_id}.json"

    def save(self, nb: GroundedNotebook) -> Path:
        target = self._path(nb.notebook_id)
        target.write_text(json.dumps(nb.to_dict(), indent=2), encoding="utf-8")
        return target

    def load(self, notebook_id: str) -> Optional[GroundedNotebook]:
        target = self._path(notebook_id)
        if not target.is_file():
            return None
        data = json.loads(target.read_text(encoding="utf-8"))
        return GroundedNotebook.from_dict(data)

    def delete(self, notebook_id: str) -> bool:
        target = self._path(notebook_id)
        if target.is_file():
            target.unlink()
            return True
        return False

    def list_all(self) -> list[dict[str, Any]]:
        out = []
        for p in self.root_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                out.append({
                    "notebook_id": data.get("notebook_id"),
                    "title": data.get("title"),
                    "sources_count": len(data.get("sources", {})),
                    "chunks_count": data.get("chunks_count", len(data.get("chunks", []))),
                    "updated_at": data.get("updated_at"),
                })
            except Exception:
                continue
        out.sort(key=lambda x: str(x.get("updated_at", "")), reverse=True)
        return out
