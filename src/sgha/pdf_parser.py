from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .corpus_manifest import read_manifest
from .extraction_schemas import ParsedPaper
from .utils import model_dump, read_text, safe_symlink_or_copy, write_json, write_text


SECTION_PATTERNS = {
    "abstract": r"\babstract\b",
    "introduction": r"\b(1\.?\s*)?introduction\b",
    "related_work": r"\brelated work\b|\bbackground\b",
    "method": r"\b(method|methodology|approach|model)\b",
    "experiments": r"\b(experiment|evaluation|results)\b",
    "limitations": r"\blimitations?\b",
    "conclusion": r"\bconclusions?\b",
}


def parse_papers(ctx: Any) -> list[ParsedPaper]:
    ctx.stage_start("parse_papers")
    parsed: list[ParsedPaper] = []
    quality: dict[str, Any] = {}
    for paper in read_manifest(ctx.run_dir):
        if not paper.local_pdf_path or not Path(paper.local_pdf_path).exists():
            quality[paper.arxiv_id] = {"status": "missing_pdf", "error": paper.download_status}
            ctx.audit.failure("parse_papers", "missing_pdf", arxiv_id=paper.arxiv_id)
            continue
        try:
            text, pages, parser = _extract_pdf_text(Path(paper.local_pdf_path))
            sections = detect_sections(text)
            canonical_text = ctx.dataset_path("arxiv", "paper_texts", f"{paper.arxiv_id.replace('/', '_')}.txt")
            canonical_sections = ctx.dataset_path("arxiv", "paper_sections", f"{paper.arxiv_id.replace('/', '_')}.json")
            write_text(canonical_text, text)
            write_json(canonical_sections, sections)
            run_text = ctx.path("parsed", "paper_texts", canonical_text.name)
            run_sections = ctx.path("parsed", "paper_sections", canonical_sections.name)
            safe_symlink_or_copy(canonical_text, run_text)
            safe_symlink_or_copy(canonical_sections, run_sections)
            q = {
                "status": "ok" if len(text) >= int(ctx.config.get("parse", {}).get("min_text_chars_ok", 1000)) else "short_text",
                "full_text_chars": len(text),
                "pages": pages,
                "parser": parser,
                "sections_detected": list(sections.keys()),
            }
            quality[paper.arxiv_id] = q
            parsed.append(
                ParsedPaper(
                    paper_id=paper.arxiv_id,
                    arxiv_id=paper.arxiv_id,
                    title=paper.title,
                    text_path=str(run_text),
                    sections_path=str(run_sections),
                    parser=parser,
                    full_text_chars=len(text),
                    pages=pages,
                    quality=q,
                )
            )
        except Exception as exc:
            quality[paper.arxiv_id] = {"status": "failed", "error": str(exc)}
            ctx.audit.failure("parse_papers", exc, arxiv_id=paper.arxiv_id)
    write_json(ctx.path("parsed", "parse_quality.json"), quality)
    write_json(ctx.path("parsed", "parsed_manifest.json"), [model_dump(p) for p in parsed])
    ctx.stage_end("parse_papers", parsed=len(parsed))
    return parsed


def _extract_pdf_text(pdf_path: Path) -> tuple[str, int, str]:
    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        pages = [page.get_text("text") for page in doc]
        return "\n\n".join(pages), len(pages), "pymupdf"
    except Exception:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages), len(pages), "pypdf"


def detect_sections(text: str) -> dict[str, dict[str, Any]]:
    lines = text.splitlines()
    headings: list[tuple[str, int]] = []
    char_pos = 0
    for line in lines:
        stripped = line.strip()
        if 0 < len(stripped) <= 80:
            lowered = stripped.lower()
            for name, pattern in SECTION_PATTERNS.items():
                if re.fullmatch(rf".*{pattern}.*", lowered, flags=re.IGNORECASE):
                    headings.append((name, char_pos))
                    break
        char_pos += len(line) + 1
    if not headings:
        return {"full_text": {"start_char": 0, "end_char": len(text), "text": text[:5000]}}
    sections: dict[str, dict[str, Any]] = {}
    for idx, (name, start) in enumerate(headings):
        end = headings[idx + 1][1] if idx + 1 < len(headings) else len(text)
        if name not in sections:
            sections[name] = {"start_char": start, "end_char": end, "text": text[start:end]}
    return sections


def load_parsed_manifest(ctx: Any) -> list[ParsedPaper]:
    from .utils import model_validate, read_json

    return [model_validate(ParsedPaper, item) for item in read_json(ctx.path("parsed", "parsed_manifest.json"), default=[])]
