"""PDF-Text-Extraktion und Chunking für Swiss RAG Filings.

Verwendet pypdf für Text-Extraktion (pure Python, kein nativer Dep.).
Chunking: char-basiert mit konfigurierter Grösse + Overlap.
"""

from __future__ import annotations

import io
import logging

_logger = logging.getLogger(__name__)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


class PdfParser:
    """Extrahiert Text aus PDF-Bytes und zerlegt ihn in Chunks."""

    def extract_text(self, pdf_bytes: bytes) -> str:
        """Extrahiert vollen Text aus PDF. Gibt leeren String bei Fehler zurück."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages: list[str] = []
            for page in reader.pages:
                try:
                    page_text = page.extract_text() or ""
                    pages.append(page_text)
                except Exception as exc:
                    _logger.debug("Seite konnte nicht extrahiert werden: %s", exc)
            return "\n".join(pages)
        except Exception as exc:
            _logger.warning("PDF-Extraktion fehlgeschlagen: %s", exc)
            return ""

    def chunk_text(
        self,
        text: str,
        chunk_size: int = CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
    ) -> list[str]:
        """Teilt Text in Chunks mit Overlap auf."""
        if not text.strip():
            return []
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = end - overlap
        return chunks
