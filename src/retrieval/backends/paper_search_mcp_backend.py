"""Backend that delegates to the paper-search-mcp CLI if available."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseBackend, PaperCandidate


class PaperSearchMCPBackend(BaseBackend):
    """Calls the `paper-search` CLI from openags/paper-search-mcp."""

    def __init__(self, *, sources: list[str] | None = None):
        self._sources = sources or ["arxiv", "semantic_scholar", "openalex", "crossref"]
        self._exe: str | None = None
        self._use_python_module: bool = False
        self._detected: bool = False

    @property
    def name(self) -> str:
        return "paper_search_mcp"

    @property
    def available(self) -> bool:
        if not self._detected:
            self._detect()
        return self._exe is not None or self._use_python_module

    def _detect(self) -> None:
        self._detected = True
        # 1. Check PATH for `paper-search`
        found = shutil.which("paper-search")
        if found:
            self._exe = found
            return
        # 2. Check env var pointing to cloned repo
        repo = os.environ.get("PAPER_SEARCH_MCP_REPO", "")
        if repo:
            cli = Path(repo) / "paper_search_mcp" / "cli.py"
            if cli.exists():
                self._use_python_module = True
                self._repo_path = repo
                return
            # try top-level cli.py
            cli2 = Path(repo) / "cli.py"
            if cli2.exists():
                self._use_python_module = True
                self._repo_path = repo
                self._cli_script = str(cli2)
                return
        # 3. Check if importable as Python package
        try:
            import paper_search_mcp  # noqa: F401
            self._use_python_module = True
            self._repo_path = ""
        except ImportError:
            pass

    def search(self, query: str, *, max_results: int = 50) -> list[PaperCandidate]:
        if not self.available:
            return []
        sources_str = ",".join(self._sources)
        if self._exe:
            return self._search_via_cli(self._exe, query, max_results, sources_str)
        if self._use_python_module:
            return self._search_via_python(query, max_results, sources_str)
        return []

    def _search_via_cli(self, exe: str, query: str, max_results: int, sources: str) -> list[PaperCandidate]:
        # First probe for JSON flag
        try:
            help_out = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=10).stdout
        except Exception:
            help_out = ""
        json_flag = "--format json" if "--format" in help_out else ("--json" if "--json" in help_out else "")
        cmd = [exe, "--query", query, "--limit", str(max_results), "--sources", sources]
        if json_flag:
            cmd += json_flag.split()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return self._parse_output(result.stdout, query)
        except Exception:
            return []

    def _search_via_python(self, query: str, max_results: int, sources: str) -> list[PaperCandidate]:
        try:
            from paper_search_mcp import search as ps_search  # type: ignore
            raw = ps_search(query=query, limit=max_results, sources=sources.split(","))
            return self._parse_output(json.dumps(raw) if not isinstance(raw, str) else raw, query)
        except Exception:
            return []

    def _parse_output(self, output: str, query: str) -> list[PaperCandidate]:
        output = output.strip()
        if not output:
            return []
        # Try JSON parse
        try:
            data = json.loads(output)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("results", data.get("papers", data.get("data", [])))
            else:
                return []
            return [_normalize_mcp_paper(item, query) for item in items if item]
        except json.JSONDecodeError:
            return []


def _normalize_mcp_paper(item: dict[str, Any], query: str) -> PaperCandidate:
    title = (item.get("title") or "").strip()
    arxiv_id = item.get("arxiv_id") or item.get("externalIds", {}).get("ArXiv")
    doi = item.get("doi") or item.get("externalIds", {}).get("DOI")
    ss_id = item.get("paperId") or item.get("semantic_scholar_id")
    pid = f"doi:{doi}" if doi else (f"arxiv:{arxiv_id}" if arxiv_id else f"mcp:{hash(title)}")
    year = item.get("year") or item.get("publication_year")
    if isinstance(year, str) and year.isdigit():
        year = int(year)
    return PaperCandidate(
        paper_id=pid,
        source_ids={k: v for k, v in {"arxiv": arxiv_id, "doi": doi, "semantic_scholar": ss_id}.items() if v},
        title=title,
        abstract=item.get("abstract") or "",
        authors=item.get("authors") or [],
        year=year,
        published_date=str(item.get("published_date") or item.get("publicationDate") or ""),
        venue=str(item.get("venue") or ""),
        source_names=item.get("sources") or ["paper_search_mcp"],
        arxiv_id=arxiv_id,
        semantic_scholar_id=ss_id,
        doi=doi,
        url=item.get("url") or "",
        pdf_url=item.get("pdf_url") or "",
        citation_count=item.get("citation_count") or item.get("citationCount"),
        fields_of_study=item.get("fields_of_study") or item.get("fieldsOfStudy") or [],
        raw_source_payloads={"paper_search_mcp": item},
        retrieval_queries=[query],
        retrieval_backend="paper_search_mcp",
    )
