from __future__ import annotations

import logging
from datetime import date
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)

class KeyArticle(BaseModel):
    article_number: str
    summary: str
    source_text: str | None = None

class GazetteExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decree_number: str
    publication_date: str
    sector: str
    local_content_requirement: float | None = Field(default=None, ge=0, le=100)
    key_articles: list[KeyArticle]

class LayoutParser(Protocol):
    def parse_pdf(self, pdf_path: str) -> dict[str, Any]:
        """Call an isolated Marker/Surya parser service and return layout JSON."""

class InstructorExtractor(Protocol):
    def extract(self, *, text: str, response_model: type[GazetteExtraction]
                ) -> GazetteExtraction:
        """Use an injected Instructor-configured client to return validated data."""

class GazetteParserService:
    """Service boundary keeps Marker/Surya copyleft dependencies out of core."""
    def __init__(self, layout_parser: LayoutParser, extractor: InstructorExtractor):
        self.layout_parser = layout_parser
        self.extractor = extractor

    def process(self, pdf_path: str) -> GazetteExtraction:
        if not pdf_path.lower().endswith(".pdf"):
            raise ValueError("Input must be a PDF")
        try:
            layout = self.layout_parser.parse_pdf(pdf_path)
            text = self._collect_text(layout)
            if not text.strip():
                raise ValueError("Parser returned no text")
            result = self.extractor.extract(text=text, response_model=GazetteExtraction)
            date.fromisoformat(result.publication_date)
            return result
        except Exception:
            log.exception("JORA document processing failed: %s", pdf_path)
            raise

    @classmethod
    def _collect_text(cls, node: Any) -> str:
        if isinstance(node, str):
            return node
        if isinstance(node, list):
            return "\n".join(filter(None, (cls._collect_text(x) for x in node)))
        if isinstance(node, dict):
            parts = [node[k] for k in ("text", "content", "markdown")
                     if isinstance(node.get(k), str)]
            parts.extend(cls._collect_text(v) for v in node.values()
                         if isinstance(v, (dict, list)))
            return "\n".join(filter(None, parts))
        return ""
