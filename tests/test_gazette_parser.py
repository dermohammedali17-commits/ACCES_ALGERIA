from datetime import date

import pytest

from src.document.gazette_parser import (
    GazetteExtraction,
    GazetteParserService,
)


class FakeLayoutParser:
    def __init__(self, result):
        self.result = result

    def parse_pdf(self, pdf_path):
        return self.result


class FakeExtractor:
    def __init__(self, result):
        self.result = result
        self.received_text = None

    def extract(self, *, text, response_model):
        self.received_text = text
        return self.result


@pytest.fixture
def extraction():
    return GazetteExtraction(
        decree_number="2026-01",
        publication_date="2026-01-15",
        sector="Industry",
        local_content_requirement=25,
        key_articles=[],
    )


def test_process_collects_layout_text_and_validates_date(extraction):
    parser = FakeLayoutParser({"blocks": [{"text": "Article 1"}, "Article 2"]})
    extractor = FakeExtractor(extraction)

    result = GazetteParserService(parser, extractor).process("decree.pdf")

    assert result.publication_date == date(2026, 1, 15).isoformat()
    assert extractor.received_text == "Article 1\nArticle 2"


def test_process_rejects_non_pdf(extraction):
    service = GazetteParserService(FakeLayoutParser("text"), FakeExtractor(extraction))

    with pytest.raises(ValueError, match="PDF"):
        service.process("decree.docx")


def test_process_rejects_empty_extracted_text(extraction):
    service = GazetteParserService(FakeLayoutParser({"blocks": []}), FakeExtractor(extraction))

    with pytest.raises(ValueError, match="no text"):
        service.process("decree.pdf")


def test_process_rejects_invalid_publication_date(extraction):
    extraction.publication_date = "15/01/2026"
    service = GazetteParserService(FakeLayoutParser("Article 1"), FakeExtractor(extraction))

    with pytest.raises(ValueError):
        service.process("decree.pdf")
