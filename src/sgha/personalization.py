"""Author-profile personalization for SGHA (Feature B) — Google-Scholar-title-seed mode.

Part of SGHA, not a side pipeline. Disabled by default. Author/scholar-profile only — NO role
labels (mentor/student/advisor) and NO `personalization_target`.

Desired behavior (this revision):
1. Use a Google Scholar profile URL ONLY to extract the author's paper TITLES.
2. Resolve those exact titles on arXiv (exact/near-exact title match).
3. Include only the successfully resolved arXiv papers as author-profile seed papers.
4. All other (non-author) corpus papers come from the normal OpenReview topic retrieval.
5. Final personalized corpus = resolved author arXiv papers + OpenReview topic papers.

Explicitly NOT done here: no Google Scholar cited-by / related-articles crawl; no fetching of
papers citing or cited by the author; no Semantic Scholar / OpenAlex; no fabricated matches.
"""
from __future__ import annotations

import difflib
import re
import time
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .utils import ensure_dir, write_json, read_json

# ---------------------------------------------------------------------------
# Forbidden keys + slug / run-id helpers
# ---------------------------------------------------------------------------

FORBIDDEN_CONFIG_KEYS = {"personalization_target"}
_ROLE_WORDS = {"mentor", "student", "advisor", "supervisor", "advisee", "mentee"}

RelationToAuthor = Literal[
    "author_profile_title_arxiv_resolved",  # primary mode: GS title -> arXiv match
    "openreview_topic_retrieval",           # normal topic corpus paper
    "author_paper", "seed_manual",          # offline seed/bibtex fallbacks
    # legacy values retained for backward-compatible deserialization (not produced here):
    "cited_by_author", "cites_author", "coauthor_related", "recent_related",
]


def validate_no_forbidden_personalization_keys(config: dict) -> None:
    """Raise a clear error if a forbidden key (e.g. personalization_target) appears anywhere."""
    def _walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k) in FORBIDDEN_CONFIG_KEYS:
                    raise ValueError(
                        f"Forbidden config key '{k}' at '{path or 'root'}'. SGHA personalization "
                        f"is author-profile based (scholar_profile_url / seed_papers_file / IDs); "
                        f"there is no 'personalization_target' and no mentor/student/advisor roles.")
                _walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _walk(v, f"{path}[{i}]")
    _walk(config or {})


def slugify(text: str | None, *, fallback: str = "") -> str:
    if not text:
        return fallback
    norm = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii").lower()
    norm = re.sub(r"[^a-z0-9]+", "_", norm)
    norm = re.sub(r"_+", "_", norm).strip("_")
    return norm or fallback


def derive_author_slug(config: dict, resolved_name: str | None = None) -> str:
    pers = (config or {}).get("personalization", {}) or {}
    explicit = pers.get("author_slug")
    if explicit and explicit != "auto":
        return slugify(explicit, fallback="unknown_author")
    name = resolved_name
    if not name:
        cfg_name = pers.get("author_name")
        if cfg_name and cfg_name != "auto":
            name = cfg_name
    return slugify(name, fallback="unknown_author")


def derive_topic_slug(config: dict) -> str:
    pers = (config or {}).get("personalization", {}) or {}
    topic = pers.get("topic")
    if topic and topic != "auto":
        return slugify(topic, fallback="topic")
    q = (config or {}).get("query", "")
    qtext = q.get("text", "") if isinstance(q, dict) else str(q)
    if not qtext:
        qtext = ((config or {}).get("venue_retrieval", {}) or {}).get("topic_description", "")
    return slugify(" ".join(qtext.split()[:4]), fallback="topic") or "topic"


def build_personalized_run_id(config: dict, resolved_name: str | None = None,
                              timestamp: str | None = None) -> str:
    pers = (config or {}).get("personalization", {}) or {}
    template = (pers.get("output", {}) or {}).get(
        "directory_template", "personalized_{seed_label_slug}_{topic_slug}_{timestamp}")
    ts = timestamp or time.strftime("%Y%m%d_%H%M%S")
    # provide all known placeholders so either the seed-label or legacy author template works
    return template.format(seed_label_slug=derive_seed_label_slug(config),
                           author_slug=derive_author_slug(config, resolved_name),
                           topic_slug=derive_topic_slug(config), timestamp=ts)


# ---------------------------------------------------------------------------
# Title normalization + matching
# ---------------------------------------------------------------------------

def normalize_title(t: str | None) -> str:
    if not t:
        return ""
    s = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_match_score(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ProfilePaper(BaseModel):
    model_config = ConfigDict(extra="allow")
    paper_id: str
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: str = ""
    abstract: str = ""
    url: str = ""
    doi: str = ""
    arxiv_id: str = ""
    arxiv_url: str = ""
    pdf_url: str = ""
    openreview_id: str = ""
    semantic_scholar_id: str = ""
    openalex_id: str = ""
    citation_count: int = 0
    relation_to_author_profile: RelationToAuthor = "author_profile_title_arxiv_resolved"
    source: str = ""
    provenance: list[str] = Field(default_factory=list)
    is_author_profile_seed: bool = False
    original_scholar_title: str = ""
    title_match_score: float = 0.0
    source_profile_paper_ids: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0


class PersonalizedPaperRelationship(BaseModel):
    model_config = ConfigDict(extra="allow")
    paper_id: str
    relation_to_author_profile: RelationToAuthor
    related_author_paper_id: str = ""
    provenance: list[str] = Field(default_factory=list)
    reason: str = ""
    score: float = 0.0


class ScholarProfile(BaseModel):
    model_config = ConfigDict(extra="allow")
    author_name: str = ""
    author_slug: str = ""
    profile_url: str = ""
    scholar_user_id: str = ""
    semantic_scholar_author_id: str = ""
    openalex_author_id: str = ""
    orcid: str = ""
    scholar_titles: list[str] = Field(default_factory=list)
    papers: list[ProfilePaper] = Field(default_factory=list)  # arXiv-resolved author papers
    coauthors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    venues: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)
    source: str = ""
    raw_metadata_path: str = ""


class ProfileResolutionError(RuntimeError):
    """Raised when a profile cannot be resolved; carries actionable guidance."""


_FALLBACK_GUIDANCE = (
    "Could not resolve the author profile from Google Scholar. Direct Scholar fetching is "
    "brittle/blocked. Provide one of: personalization.google_scholar_html_file (a saved profile "
    "page), personalization.google_scholar_csv_file (a Scholar CSV export), "
    "personalization.seed_papers_file (jsonl), or personalization.bibtex_file."
)


# ---------------------------------------------------------------------------
# Google Scholar TITLE extraction (Task 4) — titles only, no citation crawl
# ---------------------------------------------------------------------------

class GoogleScholarTitleExtractor:
    """Extract ONLY paper titles from a Google Scholar profile (live URL or saved HTML/CSV).

    Never fetches cited-by / related-articles / reference pages.
    """

    def __init__(self, config: dict, *, http_get: Callable[[str], str] | None = None):
        self.config = config
        self.pers = (config or {}).get("personalization", {}) or {}
        self.gs = self.pers.get("google_scholar", {}) or {}
        # http_get injectable for tests; default uses urllib (NOT called in tests/dry-run)
        self._http_get = http_get

    @staticmethod
    def parse_user_id(url: str | None) -> str:
        if not url:
            return ""
        m = re.search(r"[?&]user=([^&]+)", url)
        return m.group(1) if m else ""

    @staticmethod
    def parse_titles_from_html(html_text: str) -> list[str]:
        """Titles live in <a class="gsc_a_at">TITLE</a> on a Scholar profile page."""
        titles = re.findall(r'class="gsc_a_at"[^>]*>(.*?)</a>', html_text or "", re.S | re.I)
        out = []
        for t in titles:
            t = re.sub(r"<[^>]+>", "", t)  # strip nested tags
            t = re.sub(r"\s+", " ", t).strip()
            if t:
                out.append(t)
        return out

    @staticmethod
    def parse_author_name_from_html(html_text: str) -> str:
        m = re.search(r'id="gsc_prf_in"[^>]*>(.*?)</div>', html_text or "", re.S | re.I)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""

    @staticmethod
    def parse_titles_from_csv(csv_text: str) -> list[str]:
        import csv as _csv
        import io
        rows = list(_csv.DictReader(io.StringIO(csv_text)))
        col = None
        if rows:
            for k in rows[0].keys():
                if k and k.strip().lower() == "title":
                    col = k
                    break
        titles = []
        for r in rows:
            t = (r.get(col, "") if col else "").strip()
            if t:
                titles.append(t)
        return titles

    def _live_fetch_html(self, url: str) -> str:
        if self._http_get is not None:
            return self._http_get(url)
        # default live fetch (NOT used in tests/dry-run); polite + may be blocked
        delay = float(self.gs.get("request_delay_seconds", 5))
        time.sleep(min(delay, 5))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SGHA)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", "ignore")

    def extract(self, run_dir: Path | None = None) -> dict:
        """Return {author_name, scholar_user_id, titles, raw_html(optional)} or raise."""
        # saved exports first (offline, deterministic) — honored even if live disabled
        html_file = self.pers.get("google_scholar_html_file")
        csv_file = self.pers.get("google_scholar_csv_file")
        if html_file:
            p = Path(html_file)
            if not p.exists():
                raise ProfileResolutionError(f"google_scholar_html_file not found: {p}. {_FALLBACK_GUIDANCE}")
            html_text = p.read_text(errors="ignore")
            titles = self.parse_titles_from_html(html_text)
            if not titles:
                raise ProfileResolutionError(f"no titles parsed from saved Scholar HTML: {p}. {_FALLBACK_GUIDANCE}")
            return {"author_name": self.parse_author_name_from_html(html_text),
                    "scholar_user_id": self.parse_user_id(self.pers.get("scholar_profile_url")),
                    "titles": titles[: int(self.gs.get("max_profile_papers", 100))], "raw_html": html_text}
        if csv_file:
            p = Path(csv_file)
            if not p.exists():
                raise ProfileResolutionError(f"google_scholar_csv_file not found: {p}. {_FALLBACK_GUIDANCE}")
            titles = self.parse_titles_from_csv(p.read_text(errors="ignore"))
            if not titles:
                raise ProfileResolutionError(f"no titles parsed from Scholar CSV: {p}. {_FALLBACK_GUIDANCE}")
            return {"author_name": "", "scholar_user_id": "",
                    "titles": titles[: int(self.gs.get("max_profile_papers", 100))], "raw_html": ""}

        # live profile fetch
        url = self.pers.get("scholar_profile_url")
        if not url:
            raise ProfileResolutionError(f"no scholar_profile_url and no saved HTML/CSV. {_FALLBACK_GUIDANCE}")
        if not self.gs.get("fetch_live_profile", True):
            raise ProfileResolutionError(
                f"google_scholar.fetch_live_profile is false and no saved HTML/CSV provided. {_FALLBACK_GUIDANCE}")
        try:
            html_text = self._live_fetch_html(url)
        except Exception as exc:
            raise ProfileResolutionError(f"Google Scholar fetch failed/blocked ({exc}). {_FALLBACK_GUIDANCE}")
        # crude block/captcha detection
        if not html_text or "gsc_a_at" not in html_text:
            raise ProfileResolutionError(
                f"Google Scholar returned no parseable profile (likely blocked/captcha). {_FALLBACK_GUIDANCE}")
        titles = self.parse_titles_from_html(html_text)
        if not titles:
            raise ProfileResolutionError(f"Google Scholar page had no titles. {_FALLBACK_GUIDANCE}")
        # cache raw html
        if run_dir is not None and self.gs.get("cache_raw_html", True):
            raw_dir = Path(run_dir) / "profile" / "google_scholar_raw"
            ensure_dir(raw_dir)
            (raw_dir / "profile.html").write_text(html_text)
        return {"author_name": self.parse_author_name_from_html(html_text),
                "scholar_user_id": self.parse_user_id(url),
                "titles": titles[: int(self.gs.get("max_profile_papers", 100))], "raw_html": html_text}


# ---------------------------------------------------------------------------
# arXiv exact-title resolver (Task 5)
# ---------------------------------------------------------------------------

class ArxivTitleResolver:
    """Resolve author paper TITLES to arXiv papers by exact/near-exact title match.

    `search_fn(title, max_results) -> list[dict]` is injectable for testing. Each candidate dict:
    {arxiv_id, title, authors, year, abstract, url, pdf_url}. The default production search_fn
    issues a `ti:"…"` arXiv API query (NOT invoked in tests/dry-run).
    """

    def __init__(self, config: dict, *, search_fn: Callable[[str, int], list[dict]] | None = None):
        self.config = config
        ap = (config or {}).get("personalization", {}).get("author_papers", {}) or {}
        self.threshold = float(ap.get("arxiv_title_match_threshold", 0.92))
        self.search_fn = search_fn or self._default_search_fn

    def _default_search_fn(self, title: str, max_results: int = 5) -> list[dict]:  # pragma: no cover
        import urllib.parse
        q = urllib.parse.urlencode({"search_query": f'ti:"{title}"', "max_results": max_results})
        req = urllib.request.Request("http://export.arxiv.org/api/query?" + q,
                                     headers={"User-Agent": "SGHA"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            feed = resp.read().decode("utf-8", "ignore")
        out = []
        for entry in re.findall(r"<entry>(.*?)</entry>", feed, re.S):
            t = re.search(r"<title>(.*?)</title>", entry, re.S)
            idm = re.search(r"<id>(.*?)</id>", entry, re.S)
            if not t or not idm:
                continue
            aid = idm.group(1).rsplit("/", 1)[-1]
            out.append({"arxiv_id": aid, "title": re.sub(r"\s+", " ", t.group(1)).strip(),
                        "url": idm.group(1), "pdf_url": f"https://arxiv.org/pdf/{aid}"})
        return out

    def resolve_title(self, title: str, max_results: int = 5) -> dict:
        cands = self.search_fn(title, max_results) or []
        scored = sorted(((title_match_score(title, c.get("title", "")), c) for c in cands),
                        key=lambda x: -x[0])
        if not scored:
            return {"resolved": False, "original_scholar_title": title, "reason": "no arxiv candidates",
                    "best_candidate_title": "", "best_candidate_score": 0.0}
        best_score, best = scored[0]
        if best_score >= self.threshold:
            return {"resolved": True, "original_scholar_title": title, "candidate": best,
                    "title_match_score": best_score,
                    "alternatives": [c for _, c in scored[1:3]]}
        return {"resolved": False, "original_scholar_title": title,
                "reason": f"best match {best_score:.3f} < threshold {self.threshold}",
                "best_candidate_title": best.get("title", ""), "best_candidate_score": best_score}

    def resolve_all(self, titles: list[str]) -> tuple[list[ProfilePaper], list[dict]]:
        resolved: list[ProfilePaper] = []
        unresolved: list[dict] = []
        for t in titles:
            r = self.resolve_title(t)
            if r.get("resolved"):
                c = r["candidate"]
                aid = c.get("arxiv_id", "")
                resolved.append(ProfilePaper(
                    paper_id=f"arxiv:{aid}" if aid else f"title:{slugify(t)}",
                    title=c.get("title", ""), authors=c.get("authors", []) or [],
                    year=c.get("year"), abstract=c.get("abstract", ""),
                    arxiv_id=aid, arxiv_url=c.get("url", ""), pdf_url=c.get("pdf_url", ""),
                    url=c.get("url", ""), original_scholar_title=t,
                    title_match_score=r["title_match_score"],
                    relation_to_author_profile="author_profile_title_arxiv_resolved",
                    source="google_scholar_title_seed", is_author_profile_seed=True,
                    provenance=["author_profile_title_arxiv_resolved"]))
            else:
                unresolved.append(r)
        return resolved, unresolved


# ---------------------------------------------------------------------------
# Profile ingestion (Task 4+5 orchestration)
# ---------------------------------------------------------------------------

class ScholarProfileIngestor:
    """Resolve a ScholarProfile: Google-Scholar titles -> arXiv author papers (primary), with
    seed_papers_file / bibtex_file offline fallbacks. Never returns an empty/hallucinated profile.
    """

    def __init__(self, config: dict, *, http_get=None, arxiv_search_fn=None):
        self.config = config
        self.pers = (config or {}).get("personalization", {}) or {}
        self.http_get = http_get
        self.arxiv_search_fn = arxiv_search_fn

    def _from_seed_file(self) -> list[ProfilePaper]:
        p = self.pers.get("seed_papers_file")
        if not p:
            return []
        path = Path(p)
        if not path.exists():
            raise ProfileResolutionError(f"seed_papers_file not found: {path}. {_FALLBACK_GUIDANCE}")
        import json
        out = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            d.setdefault("relation_to_author_profile", "seed_manual")
            d.setdefault("is_author_profile_seed", True)
            out.append(ProfilePaper(**d))
        return out

    def _from_bibtex(self) -> list[ProfilePaper]:
        p = self.pers.get("bibtex_file")
        if not p:
            return []
        path = Path(p)
        if not path.exists():
            raise ProfileResolutionError(f"bibtex_file not found: {path}. {_FALLBACK_GUIDANCE}")
        text = path.read_text()
        papers: list[ProfilePaper] = []
        for m in re.finditer(r"@\w+\s*\{([^,]+),(.*?)\n\}", text, re.S):
            key, body = m.group(1).strip(), m.group(2)
            def field(name):
                mm = re.search(rf"{name}\s*=\s*[{{\"]+(.*?)[}}\"]+\s*,?", body, re.S | re.I)
                return " ".join(mm.group(1).split()) if mm else ""
            authors = [a.strip() for a in re.split(r"\s+and\s+", field("author")) if a.strip()]
            yr = field("year")
            papers.append(ProfilePaper(
                paper_id=f"bibtex:{key}", title=field("title"), authors=authors,
                year=int(yr) if yr.isdigit() else None, venue=field("journal") or field("booktitle"),
                doi=field("doi"), relation_to_author_profile="seed_manual",
                is_author_profile_seed=True, provenance=["seed_manual"]))
        if not papers:
            raise ProfileResolutionError(f"no entries parsed from bibtex_file: {path}. {_FALLBACK_GUIDANCE}")
        return papers

    def resolve(self, run_dir: Path | None = None) -> ScholarProfile:
        gs = self.pers.get("google_scholar", {}) or {}
        titles: list[str] = []
        scholar_user_id = ""
        gs_author = ""
        source = ""
        unresolved: list[dict] = []
        resolved_papers: list[ProfilePaper] = []

        use_gs = gs.get("enabled", True) and (
            self.pers.get("scholar_profile_url") or self.pers.get("google_scholar_html_file")
            or self.pers.get("google_scholar_csv_file"))
        if use_gs:
            extractor = GoogleScholarTitleExtractor(self.config, http_get=self.http_get)
            info = extractor.extract(run_dir=run_dir)  # may raise ProfileResolutionError
            titles = info["titles"]; scholar_user_id = info["scholar_user_id"]; gs_author = info["author_name"]
            resolver = ArxivTitleResolver(self.config, search_fn=self.arxiv_search_fn)
            resolved_papers, unresolved = resolver.resolve_all(titles)
            source = "google_scholar_title_seed"
            if not resolved_papers and self.pers.get("author_papers", {}).get("include_only_resolved_arxiv_matches", True):
                # titles extracted but none resolved on arXiv: clear, non-empty failure
                raise ProfileResolutionError(
                    f"extracted {len(titles)} Scholar titles but none resolved on arXiv at threshold "
                    f"{self.pers.get('author_papers',{}).get('arxiv_title_match_threshold',0.92)}. "
                    f"Lower the threshold or provide seed_papers_file. {_FALLBACK_GUIDANCE}")
        else:
            resolved_papers = self._from_seed_file()
            source = "seed_papers_file" if resolved_papers else ""
            if not resolved_papers:
                resolved_papers = self._from_bibtex()
                source = "bibtex_file" if resolved_papers else ""
            if not resolved_papers:
                raise ProfileResolutionError(f"no usable profile source. {_FALLBACK_GUIDANCE}")

        name = self.pers.get("author_name")
        if not name or name == "auto":
            name = gs_author or ""
            if not name:
                from collections import Counter
                allauth = Counter(a for pp in resolved_papers for a in pp.authors)
                name = allauth.most_common(1)[0][0] if allauth else ""
        prof = ScholarProfile(
            author_name=name or "", author_slug=derive_author_slug(self.config, name or None),
            profile_url=self.pers.get("scholar_profile_url") or "", scholar_user_id=scholar_user_id,
            scholar_titles=titles, papers=resolved_papers,
            venues=sorted({pp.venue for pp in resolved_papers if pp.venue}),
            years=sorted({pp.year for pp in resolved_papers if pp.year}), source=source)
        # stash unresolved on the model (extra="allow")
        prof.unresolved_titles = unresolved  # type: ignore[attr-defined]
        return prof

    def write_profile(self, run_dir: Path, profile: ScholarProfile) -> dict:
        from .utils import model_dump
        import json
        pdir = Path(run_dir) / "profile"
        ensure_dir(pdir)
        write_json(pdir / "author_profile.json", model_dump(profile))
        # titles + resolved + unresolved
        with open(pdir / "google_scholar_titles.jsonl", "w") as f:
            for t in profile.scholar_titles:
                f.write(json.dumps({"title": t}) + "\n")
        with open(pdir / "author_titles_from_scholar.jsonl", "w") as f:
            for t in profile.scholar_titles:
                f.write(json.dumps({"original_scholar_title": t}) + "\n")
        with open(pdir / "author_arxiv_resolved.jsonl", "w") as f:
            for pp in profile.papers:
                f.write(json.dumps(model_dump(pp)) + "\n")
        unresolved = getattr(profile, "unresolved_titles", []) or []
        with open(pdir / "author_arxiv_unresolved.jsonl", "w") as f:
            for u in unresolved:
                f.write(json.dumps(u) + "\n")
        # seed_papers.jsonl kept for backward compatibility (= resolved author papers)
        with open(pdir / "seed_papers.jsonl", "w") as f:
            for pp in profile.papers:
                f.write(json.dumps(model_dump(pp)) + "\n")
        (pdir / "profile_summary.md").write_text(
            f"""# Author Profile Summary (Google-Scholar title-seed mode)

- author: {profile.author_name or '(unknown)'}
- slug: {profile.author_slug}
- scholar user id: {profile.scholar_user_id or '(none)'}
- profile url: {profile.profile_url or '(none)'}
- source: {profile.source or '(none)'}
- Scholar titles extracted: {len(profile.scholar_titles)}
- resolved on arXiv (author seeds): {len(profile.papers)}
- unresolved titles: {len(unresolved)}

This mode extracts ONLY titles from Google Scholar and resolves them on arXiv. It does NOT
crawl cited-by / related-articles, and does not fetch papers citing or cited by the author.

## Unresolved titles (not substituted)
{chr(10).join(f"- {u.get('original_scholar_title','')}: {u.get('reason','')}" for u in unresolved) or '- none'}
""")
        return {"author_profile": str(pdir / "author_profile.json"),
                "resolved": str(pdir / "author_arxiv_resolved.jsonl"),
                "unresolved": str(pdir / "author_arxiv_unresolved.jsonl")}


# ---------------------------------------------------------------------------
# Personalized corpus builder (Task 6): author arXiv seeds + OpenReview topic papers
# ---------------------------------------------------------------------------

def _as_profile_paper(obj: Any, relation: RelationToAuthor) -> ProfilePaper:
    if isinstance(obj, ProfilePaper):
        return obj
    d = dict(obj)
    d.setdefault("paper_id", d.get("openreview_id") or d.get("arxiv_id") or d.get("id") or slugify(d.get("title", "")))
    d.setdefault("relation_to_author_profile", relation)
    return ProfilePaper(**{k: v for k, v in d.items() if k in ProfilePaper.model_fields or True})


def _dedupe_key(pp: ProfilePaper) -> str:
    return (pp.arxiv_id and f"arxiv:{pp.arxiv_id}") or (pp.openreview_id and f"or:{pp.openreview_id}") \
        or (pp.doi and f"doi:{pp.doi.lower()}") or f"title:{normalize_title(pp.title)}"


class PersonalizedCorpusBuilder:
    """Final personalized corpus = resolved author arXiv papers + OpenReview topic papers.
    NO Google Scholar citing/cited/related papers; no Semantic Scholar/OpenAlex."""

    def __init__(self, config: dict):
        self.config = config
        self.ccfg = ((config or {}).get("personalization", {}) or {}).get("corpus", {}) or {}

    def build(self, profile: ScholarProfile, *, openreview_papers: list | None = None) -> dict:
        author_papers: list[ProfilePaper] = []
        if self.ccfg.get("include_author_profile_papers", True):
            for pp in profile.papers:
                pp.is_author_profile_seed = True
                if "author_profile_title_arxiv_resolved" not in pp.provenance and pp.relation_to_author_profile == "author_profile_title_arxiv_resolved":
                    pp.provenance = list(dict.fromkeys(pp.provenance + ["author_profile_title_arxiv_resolved"]))
                author_papers.append(pp)
        or_papers: list[ProfilePaper] = []
        if self.ccfg.get("include_openreview_topic_papers", True):
            for obj in (openreview_papers or []):
                pp = _as_profile_paper(obj, "openreview_topic_retrieval")
                pp.relation_to_author_profile = pp.relation_to_author_profile or "openreview_topic_retrieval"
                if "openreview_topic_retrieval" not in pp.provenance:
                    pp.provenance = list(dict.fromkeys(pp.provenance + ["openreview_topic_retrieval"]))
                or_papers.append(pp)

        merged: dict[str, ProfilePaper] = {}
        rels: list[PersonalizedPaperRelationship] = []
        # author papers first so overlaps keep author provenance + seed flag
        for pp in author_papers + or_papers:
            key = _dedupe_key(pp)
            if key in merged:
                ex = merged[key]
                ex.provenance = list(dict.fromkeys(ex.provenance + pp.provenance))
                ex.is_author_profile_seed = ex.is_author_profile_seed or pp.is_author_profile_seed
                continue
            merged[key] = pp
        for pp in merged.values():
            rels.append(PersonalizedPaperRelationship(
                paper_id=pp.paper_id, relation_to_author_profile=pp.relation_to_author_profile,
                provenance=pp.provenance, score=pp.title_match_score,
                reason="author_profile seed (GS title -> arXiv)" if pp.is_author_profile_seed
                       else "openreview topic retrieval"))
        return {"selected_papers": list(merged.values()), "relationships": rels,
                "author_papers": author_papers, "openreview_papers": or_papers}

    def write(self, run_dir: Path, result: dict) -> dict:
        from .utils import model_dump
        import json
        cdir = Path(run_dir) / "corpus"
        ensure_dir(cdir)
        with open(cdir / "selected_papers.jsonl", "w") as f:
            for pp in result["selected_papers"]:
                row = model_dump(pp)
                row["is_author_profile_seed"] = pp.is_author_profile_seed
                f.write(json.dumps(row) + "\n")
        with open(cdir / "paper_relationships.jsonl", "w") as f:
            for r in result["relationships"]:
                f.write(json.dumps(model_dump(r)) + "\n")
        return {"selected_papers": str(cdir / "selected_papers.jsonl"),
                "paper_relationships": str(cdir / "paper_relationships.jsonl")}


# ---------------------------------------------------------------------------
# Personalized scoring (Task 7) + alignment explanation (Task 8)
# ---------------------------------------------------------------------------

def personalized_score(*, structural_gap_score: float, author_alignment_score: float = 0.0,
                       novelty_score: float, feasibility_score: float, config: dict,
                       seed_alignment_score: float | None = None) -> float:
    """Weighted blend. The alignment term is seed-paper alignment in manual-seed mode
    (seed_alignment_score), falling back to author alignment for the legacy GS path. Weight key
    seed_alignment_weight is preferred, falling back to author_alignment_weight."""
    r = ((config or {}).get("personalization", {}) or {}).get("ranking", {}) or {}
    align = seed_alignment_score if seed_alignment_score is not None else author_alignment_score
    w_align = float(r.get("seed_alignment_weight", r.get("author_alignment_weight", 0.30)))
    return (float(r.get("structural_gap_weight", 0.35)) * float(structural_gap_score)
            + w_align * float(align)
            + float(r.get("novelty_weight", 0.20)) * float(novelty_score)
            + float(r.get("feasibility_weight", 0.15)) * float(feasibility_score))


def compute_author_alignment_score(hyp_papers: list[str], profile: ScholarProfile,
                                   relationships: list[PersonalizedPaperRelationship] | None = None) -> float:
    """Fraction of a hypothesis's supporting papers that are AUTHOR-PROFILE SEED papers
    (GS-title→arXiv resolved). Citing/cited/related papers are intentionally NOT considered."""
    if not hyp_papers:
        return 0.0
    seed_ids = {pp.paper_id for pp in profile.papers}
    seed_ids |= {f"arxiv:{pp.arxiv_id}" for pp in profile.papers if pp.arxiv_id}
    seed_ids |= {pp.arxiv_id for pp in profile.papers if pp.arxiv_id}
    # only author-seed relationships count
    seed_ids |= {r.paper_id for r in (relationships or [])
                 if r.relation_to_author_profile == "author_profile_title_arxiv_resolved"}
    hit = sum(1 for p in hyp_papers if p in seed_ids)
    return min(1.0, hit / max(1, len(hyp_papers)))


def deterministic_author_alignment(hyp: dict, profile: ScholarProfile,
                                   relationships: list[PersonalizedPaperRelationship] | None = None) -> dict:
    """Author-profile-framed explanation using ONLY author-seed papers. No role words; cited/
    citing left empty (not part of this feature)."""
    seed_ids = {pp.paper_id for pp in profile.papers} | {pp.arxiv_id for pp in profile.papers if pp.arxiv_id}
    related_author = [p for p in (hyp.get("supporting_papers", []) or []) if p in seed_ids]
    if related_author:
        reason = ("This problem extends the author's profile papers "
                  f"({', '.join(related_author[:3])}) toward their remaining open scope.")
        rel = "extends author-profile papers"
    else:
        reason = "This problem is only weakly related to the author profile on current evidence."
        rel = "weakly related"
    return {
        "author_alignment_reason": _strip_role_words(reason),
        "related_author_papers": related_author[:5],
        "related_cited_papers": [],   # not part of this feature
        "related_citing_papers": [],  # not part of this feature
        "relationship_to_author_profile": rel,
    }


def _strip_role_words(text: str) -> str:
    out = text
    for w in _ROLE_WORDS:
        out = re.sub(rf"\b{w}\b", "author", out, flags=re.I)
    return out


def contains_role_words(text: str) -> bool:
    return any(re.search(rf"\b{w}\b", text or "", flags=re.I) for w in _ROLE_WORDS)


# ===========================================================================
# MANUAL SEED-PAPER personalization (recommended path). Google Scholar above is
# now LEGACY/experimental. Manual seed papers + OpenReview expansion only — no
# citation crawl, no Semantic Scholar/OpenAlex, no WebSearch.
# ===========================================================================

RelationToSeed = Literal[
    "uploaded_seed_paper", "openreview_topic_retrieval", "seed_and_openreview_overlap",
]
SEED_FILE_TYPES = {".pdf", ".jsonl", ".bib", ".bibtex", ".csv"}


class SeedPaper(BaseModel):
    model_config = ConfigDict(extra="allow")
    seed_paper_id: str
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: str = ""
    abstract: str = ""
    local_pdf_path: str = ""
    arxiv_id: str = ""
    openreview_id: str = ""
    doi: str = ""
    url: str = ""
    source: str = "manual_seed"
    relation_to_seed_profile: RelationToSeed = "uploaded_seed_paper"
    is_manual_seed_paper: bool = True
    seed_label: str = ""
    metadata_incomplete: bool = False
    provenance: list[str] = Field(default_factory=lambda: ["uploaded_seed_paper"])


def derive_seed_label_slug(config: dict) -> str:
    pers = (config or {}).get("personalization", {}) or {}
    lbl = pers.get("seed_label")
    if lbl and lbl != "auto":
        return slugify(lbl, fallback="manual_seed")
    sdir = pers.get("seed_paper_dir")
    if sdir:
        return slugify(Path(str(sdir)).name, fallback="manual_seed")
    return "manual_seed"


class SeedMetadataIncomplete(RuntimeError):
    pass


class ManualSeedPaperIngestor:
    """Import manually-provided seed papers from a directory, a JSONL file, or a BibTeX file.
    PDFs get best-effort title extraction; if unreliable, the paper is kept with
    metadata_incomplete=True (never a hallucinated title). No network."""

    def __init__(self, config: dict, *, pdf_text_fn: Callable[[Path], str] | None = None):
        self.config = config
        self.pers = (config or {}).get("personalization", {}) or {}
        self.sp = self.pers.get("seed_papers", {}) or {}
        self.seed_label = derive_seed_label_slug(config)
        self._pdf_text_fn = pdf_text_fn  # injectable for tests

    def _pdf_text(self, path: Path) -> str:
        if self._pdf_text_fn is not None:
            return self._pdf_text_fn(path)
        from .pdf_parser import _extract_pdf_text
        text, _, _ = _extract_pdf_text(path)
        return text

    @staticmethod
    def _title_from_pdf_text(text: str) -> str:
        # Heuristic: first reasonably-long non-numeric line of the first page.
        for line in (text or "").splitlines():
            s = line.strip()
            if len(s) >= 12 and not s.replace(" ", "").isdigit() and any(c.isalpha() for c in s):
                return re.sub(r"\s+", " ", s)[:300]
        return ""

    def _from_jsonl(self, path: Path) -> list[SeedPaper]:
        import json
        out = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            d.setdefault("seed_paper_id", d.get("arxiv_id") or d.get("openreview_id")
                         or d.get("doi") or f"seed:{slugify(d.get('title',''))}")
            d["seed_label"] = self.seed_label
            out.append(SeedPaper(**{k: v for k, v in d.items()}))
        return out

    def _from_bibtex(self, path: Path) -> list[SeedPaper]:
        text = path.read_text()
        out = []
        for m in re.finditer(r"@\w+\s*\{([^,]+),(.*?)\n\}", text, re.S):
            key, body = m.group(1).strip(), m.group(2)
            def field(name):
                mm = re.search(rf"{name}\s*=\s*[{{\"]+(.*?)[}}\"]+\s*,?", body, re.S | re.I)
                return " ".join(mm.group(1).split()) if mm else ""
            yr = field("year")
            out.append(SeedPaper(
                seed_paper_id=f"bibtex:{key}", title=field("title"),
                authors=[a.strip() for a in re.split(r"\s+and\s+", field("author")) if a.strip()],
                year=int(yr) if yr.isdigit() else None, venue=field("journal") or field("booktitle"),
                doi=field("doi"), seed_label=self.seed_label))
        return out

    def _from_csv(self, path: Path) -> list[SeedPaper]:
        import csv as _csv, io
        rows = list(_csv.DictReader(io.StringIO(path.read_text())))
        out = []
        for r in rows:
            low = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            title = low.get("title", "")
            if not title:
                continue
            yr = low.get("year", "")
            out.append(SeedPaper(seed_paper_id=low.get("arxiv_id") or low.get("doi") or f"seed:{slugify(title)}",
                                 title=title, year=int(yr) if yr.isdigit() else None,
                                 venue=low.get("venue", ""), doi=low.get("doi", ""),
                                 arxiv_id=low.get("arxiv_id", ""), seed_label=self.seed_label))
        return out

    def _from_pdf(self, path: Path) -> SeedPaper:
        try:
            text = self._pdf_text(path)
        except Exception:
            text = ""
        title = self._title_from_pdf_text(text)
        return SeedPaper(seed_paper_id=f"pdf:{slugify(path.stem)}", title=title,
                         local_pdf_path=str(path), seed_label=self.seed_label,
                         metadata_incomplete=(not title), abstract="")

    def ingest(self) -> tuple[list[SeedPaper], list[dict]]:
        papers: list[SeedPaper] = []
        # A) directory scan
        sdir = self.pers.get("seed_paper_dir")
        if sdir:
            d = Path(sdir)
            if not d.exists():
                raise SeedMetadataIncomplete(f"seed_paper_dir not found: {d}")
            for f in sorted(d.iterdir()):
                if f.suffix.lower() not in SEED_FILE_TYPES:
                    continue
                if f.suffix.lower() == ".pdf":
                    papers.append(self._from_pdf(f))
                elif f.suffix.lower() == ".jsonl":
                    papers += self._from_jsonl(f)
                elif f.suffix.lower() in (".bib", ".bibtex"):
                    papers += self._from_bibtex(f)
                elif f.suffix.lower() == ".csv":
                    papers += self._from_csv(f)
        # B) explicit jsonl
        if self.pers.get("seed_papers_file"):
            p = Path(self.pers["seed_papers_file"])
            if not p.exists():
                raise SeedMetadataIncomplete(f"seed_papers_file not found: {p}")
            papers += self._from_jsonl(p)
        # C) explicit bibtex
        if self.pers.get("bibtex_file"):
            p = Path(self.pers["bibtex_file"])
            if not p.exists():
                raise SeedMetadataIncomplete(f"bibtex_file not found: {p}")
            papers += self._from_bibtex(p)

        # dedupe
        if self.sp.get("deduplicate", True):
            seen, deduped = set(), []
            for pp in papers:
                k = pp.arxiv_id or pp.openreview_id or (pp.doi.lower() if pp.doi else "") or normalize_title(pp.title) or pp.seed_paper_id
                if k in seen:
                    continue
                seen.add(k); deduped.append(pp)
            papers = deduped

        issues = [{"seed_paper_id": pp.seed_paper_id, "local_pdf_path": pp.local_pdf_path,
                   "reason": "title/abstract not extracted from PDF — provide JSONL/BibTeX metadata"}
                  for pp in papers if pp.metadata_incomplete]
        need = int(self.sp.get("require_at_least_n_seed_papers", 1))
        if len(papers) < need:
            raise SeedMetadataIncomplete(
                f"only {len(papers)} seed papers found; require_at_least_n_seed_papers={need}. "
                f"Provide a seed_paper_dir / seed_papers_file / bibtex_file with seed metadata.")
        return papers, issues

    def write(self, run_dir: Path, papers: list[SeedPaper], issues: list[dict]) -> dict:
        import json
        from .utils import model_dump
        pdir = Path(run_dir) / "profile"; ensure_dir(pdir)
        with open(pdir / "seed_papers.jsonl", "w") as f:
            for pp in papers:
                f.write(json.dumps(model_dump(pp)) + "\n")
        with open(pdir / "seed_papers_metadata_issues.jsonl", "w") as f:
            for it in issues:
                f.write(json.dumps(it) + "\n")
        (pdir / "seed_profile_summary.md").write_text(
            f"""# Seed Profile Summary

- seed_label: {self.seed_label}
- seed papers imported: {len(papers)}
- with complete metadata: {sum(1 for p in papers if not p.metadata_incomplete)}
- metadata-incomplete (PDF title not extracted): {len(issues)}
- sources: dir={bool(self.pers.get('seed_paper_dir'))} jsonl={bool(self.pers.get('seed_papers_file'))} bibtex={bool(self.pers.get('bibtex_file'))}

Manual seed papers are the personalized seed set. OpenReview supplies all other (non-seed)
papers. No Google Scholar, no citation crawl, no Semantic Scholar/OpenAlex.
{"" if not issues else chr(10).join("- incomplete: "+i["local_pdf_path"] for i in issues)}
""")
        return {"seed_papers": str(pdir / "seed_papers.jsonl"),
                "issues": str(pdir / "seed_papers_metadata_issues.jsonl")}


# ---------------------------------------------------------------------------
# Seed topic profile -> OpenReview queries (deterministic; no external search)
# ---------------------------------------------------------------------------

_STOP = set("the a an of for and or to in on with without via using under over from into is are "
            "we our this that these those new towards toward analysis study problem method "
            "algorithm algorithms learning based optimal efficient simple robust general".split())


def _keyphrases(texts: list[str], k: int = 15) -> list[str]:
    from collections import Counter
    uni, bi = Counter(), Counter()
    for t in texts:
        toks = [w for w in re.findall(r"[a-z][a-z0-9\-]+", (t or "").lower()) if w not in _STOP and len(w) > 2]
        uni.update(toks)
        for a, b in zip(toks, toks[1:]):
            bi.update([f"{a} {b}"])
    phrases = [p for p, _ in bi.most_common(k)] + [w for w, _ in uni.most_common(k)]
    seen, out = set(), []
    for p in phrases:
        if p not in seen:
            seen.add(p); out.append(p)
    return out[:k]


def build_seed_topic_profile(config: dict, seed_papers: list[SeedPaper]) -> dict:
    pers = (config or {}).get("personalization", {}) or {}
    ore = pers.get("openreview_expansion", {}) or {}
    topic = pers.get("topic")
    if not topic or topic == "auto":
        q = (config or {}).get("query", "")
        topic = (q.get("text", "") if isinstance(q, dict) else str(q)) or "topic"
    titles = [p.title for p in seed_papers if p.title]
    abstracts = [p.abstract for p in seed_papers if p.abstract]
    kps = _keyphrases(titles + abstracts, k=15)
    method_terms = [p for p in kps if any(x in p for x in ("algorithm", "sampling", "bound", "ucb", "descent", "transformer", "model"))]
    task_terms = [p for p in kps if any(x in p for x in ("bandit", "identification", "monitoring", "regression", "classification", "learning"))]
    # generated queries: topic + seed-derived keyphrases (capped)
    cap = int(ore.get("max_seed_derived_queries", 12))
    queries = []
    if ore.get("use_topic_queries", True):
        queries.append(str(topic))
    if ore.get("derive_queries_from_seed_papers", True):
        for kp in kps:
            queries.append(f"{topic} {kp}" if topic and topic != kp else kp)
    # dedupe + cap
    seen, q2 = set(), []
    for q in queries:
        if q and q not in seen:
            seen.add(q); q2.append(q)
    queries = q2[: cap]
    venues = sorted({p.venue for p in seed_papers if p.venue})
    return {
        "seed_label": derive_seed_label_slug(config), "topic": topic,
        "seed_titles": titles, "keyphrases": kps,
        "method_terms": method_terms, "task_terms": task_terms,
        "assumption_terms": [p for p in kps if "assum" in p],
        "benchmark_terms": [p for p in kps if any(x in p for x in ("benchmark", "dataset"))],
        "generated_openreview_queries": queries, "venues": venues,
        "exclusion_terms": [], "profile_summary": f"{len(titles)} seed titles; {len(queries)} OpenReview queries",
    }


def write_seed_topic_profile(run_dir: Path, profile: dict) -> dict:
    pdir = Path(run_dir) / "profile"; ensure_dir(pdir)
    write_json(pdir / "seed_topic_profile.json", profile)
    md = ["# Seed Topic Profile\n", f"- seed_label: {profile['seed_label']}", f"- topic: {profile['topic']}",
          f"- seed titles: {len(profile['seed_titles'])}", f"- keyphrases: {profile['keyphrases']}",
          f"- method_terms: {profile['method_terms']}", f"- task_terms: {profile['task_terms']}",
          "\n## Generated OpenReview queries"]
    md += [f"- {q}" for q in profile["generated_openreview_queries"]]
    (pdir / "seed_topic_profile.md").write_text("\n".join(md))
    return {"json": str(pdir / "seed_topic_profile.json"), "md": str(pdir / "seed_topic_profile.md")}


# ---------------------------------------------------------------------------
# Manual-seed corpus = seed papers + OpenReview topic papers (dedupe + provenance)
# ---------------------------------------------------------------------------

def _seed_dedupe_key(d: dict) -> str:
    return ((d.get("arxiv_id") and f"arxiv:{d['arxiv_id']}") or (d.get("openreview_id") and f"or:{d['openreview_id']}")
            or (d.get("doi") and f"doi:{str(d['doi']).lower()}") or f"title:{normalize_title(d.get('title',''))}")


def build_manual_seed_corpus(config: dict, seed_papers: list[SeedPaper],
                             openreview_papers: list | None = None) -> dict:
    from .utils import model_dump
    ccfg = ((config or {}).get("personalization", {}) or {}).get("corpus", {}) or {}
    selected: dict[str, dict] = {}
    rels: list[dict] = []
    # 1) seed papers first
    if ccfg.get("include_manual_seed_papers", True):
        for pp in seed_papers:
            d = model_dump(pp); d["provenance"] = ["uploaded_seed_paper"]
            d["relation_to_seed_profile"] = "uploaded_seed_paper"; d["is_manual_seed_paper"] = True
            selected[_seed_dedupe_key(d)] = d
    # 2) OpenReview topic papers
    if ccfg.get("include_openreview_topic_papers", True):
        for obj in (openreview_papers or []):
            d = dict(obj) if not isinstance(obj, SeedPaper) else model_dump(obj)
            d.setdefault("title", d.get("title", ""))
            key = _seed_dedupe_key(d)
            if key in selected:  # overlap with a seed paper
                ex = selected[key]
                ex["provenance"] = list(dict.fromkeys(ex.get("provenance", []) + ["openreview_topic_retrieval"]))
                ex["relation_to_seed_profile"] = "seed_and_openreview_overlap"
                continue
            d["provenance"] = ["openreview_topic_retrieval"]
            d["relation_to_seed_profile"] = "openreview_topic_retrieval"
            d["is_manual_seed_paper"] = False
            d.setdefault("source", "openreview"); d.setdefault("openreview_id", d.get("openreview_id", ""))
            selected[key] = d
    out = list(selected.values())
    for d in out:
        rels.append({"paper_id": d.get("seed_paper_id") or d.get("openreview_id") or d.get("arxiv_id") or _seed_dedupe_key(d),
                     "relation_to_seed_profile": d["relation_to_seed_profile"], "provenance": d["provenance"],
                     "is_manual_seed_paper": d.get("is_manual_seed_paper", False)})
    return {"selected_papers": out, "relationships": rels}


def write_manual_seed_corpus(run_dir: Path, result: dict) -> dict:
    import json
    cdir = Path(run_dir) / "corpus"; ensure_dir(cdir)
    # canonical name is selected_papers.jsonl (normal corpus name); keep selected_seed_papers.jsonl
    # as a backward-compatible alias.
    for name in ("selected_papers.jsonl", "selected_seed_papers.jsonl"):
        with open(cdir / name, "w") as f:
            for d in result["selected_papers"]:
                f.write(json.dumps(d) + "\n")
    with open(cdir / "paper_relationships.jsonl", "w") as f:
        for r in result["relationships"]:
            f.write(json.dumps(r) + "\n")
    return {"selected": str(cdir / "selected_papers.jsonl"),
            "relationships": str(cdir / "paper_relationships.jsonl")}


def build_personalized_corpus(ctx: Any, *, openreview_papers: list | None = None,
                              openreview_fetch_fn: Callable[[Any, list[str]], list] | None = None) -> dict:
    """Entrypoint orchestrator for personalized corpus construction (manual-seed mode).

    1) ingest manual seed papers -> profile/seed_papers.jsonl (+ issues + summary)
    2) build seed topic profile -> profile/seed_topic_profile.json/.md
    3) obtain OpenReview topic papers (injected list, or openreview_fetch_fn(ctx, queries) for
       the live path) when include_openreview_topic_papers is true
    4) merge seeds + OpenReview (dedupe + provenance) -> corpus/selected_papers.jsonl +
       corpus/paper_relationships.jsonl
    No Google Scholar, no citation crawl, no Semantic Scholar/OpenAlex. Returns a summary dict.
    """
    cfg = ctx.config
    pers = (cfg.get("personalization", {}) or {})
    run_dir = ctx.run_dir
    # 1) seeds
    ing = ManualSeedPaperIngestor(cfg)
    seeds, issues = ing.ingest()
    ing.write(run_dir, seeds, issues)
    # 2) seed topic profile
    profile = build_seed_topic_profile(cfg, seeds)
    write_seed_topic_profile(run_dir, profile)
    # 3) OpenReview topic papers (only if requested)
    ccfg = pers.get("corpus", {}) or {}
    or_papers = list(openreview_papers or [])
    if not or_papers and ccfg.get("include_openreview_topic_papers", True) and openreview_fetch_fn is not None:
        or_papers = list(openreview_fetch_fn(ctx, profile.get("generated_openreview_queries", [])) or [])
    # 4) merge + write
    result = build_manual_seed_corpus(cfg, seeds, openreview_papers=or_papers)
    paths = write_manual_seed_corpus(run_dir, result)
    n_seed = sum(1 for p in result["selected_papers"] if p.get("is_manual_seed_paper"))
    n_or = len(result["selected_papers"]) - n_seed
    return {"seed_papers": len(seeds), "metadata_incomplete": len(issues),
            "openreview_papers": n_or, "selected_corpus": len(result["selected_papers"]),
            "queries": profile.get("generated_openreview_queries", []),
            "paths": paths, "result": result}


# ---------------------------------------------------------------------------
# Seed-paper alignment scoring (replaces author/citation alignment for this mode)
# ---------------------------------------------------------------------------

def _seed_id_set(seed_papers: list, relationships: list[dict] | None = None) -> set[str]:
    """All identifier forms that should match a seed paper in a hypothesis's supporting_papers
    (bare + arxiv:/or: prefixed), so id-formatting differences don't drop alignments."""
    ids: set[str] = set()
    for p in seed_papers:
        d = p if isinstance(p, dict) else (p.model_dump() if hasattr(p, "model_dump") else {})
        if d.get("seed_paper_id"): ids.add(d["seed_paper_id"])
        if d.get("arxiv_id"): ids |= {d["arxiv_id"], f"arxiv:{d['arxiv_id']}"}
        if d.get("openreview_id"): ids |= {d["openreview_id"], f"or:{d['openreview_id']}"}
        if d.get("doi"): ids.add(str(d["doi"]).lower())
    for r in (relationships or []):
        if r.get("is_manual_seed_paper") or r.get("relation_to_seed_profile") in ("uploaded_seed_paper", "seed_and_openreview_overlap"):
            pid = r.get("paper_id")
            if pid:
                ids.add(pid)
                if pid.startswith("arxiv:"): ids.add(pid.split(":", 1)[1])
                else: ids.add(f"arxiv:{pid}")
    return ids


def compute_seed_alignment_score(hyp_papers: list[str], seed_papers: list,
                                 relationships: list[dict] | None = None) -> float:
    if not hyp_papers:
        return 0.0
    seed_ids = _seed_id_set(seed_papers, relationships)
    hit = sum(1 for p in hyp_papers if p in seed_ids)
    return min(1.0, hit / max(1, len(hyp_papers)))


def deterministic_seed_alignment(hyp: dict, seed_papers: list, relationships: list[dict] | None = None) -> dict:
    seed_ids = _seed_id_set(seed_papers, relationships)
    related = [p for p in (hyp.get("supporting_papers", []) or []) if p in seed_ids]
    if related:
        reason = f"This problem builds on the uploaded seed papers ({', '.join(related[:3])})."
        rel = "extends seed papers"
    else:
        reason = "This problem is only weakly aligned with the uploaded seed papers on current evidence."
        rel = "weakly related to seed papers"
    return {"seed_alignment_reason": _strip_role_words(reason), "related_seed_papers": related[:5],
            "relationship_to_seed_profile": rel}


# ---------------------------------------------------------------------------
# Google Scholar deprecation guidance (recommended path is manual seed papers)
# ---------------------------------------------------------------------------

_GS_DEPRECATION_MSG = (
    "Google Scholar profile ingestion is deprecated for the recommended workflow. Please provide "
    "seed_paper_dir, seed_papers_file, or bibtex_file."
)


def deprecated_scholar_warning(config: dict) -> str | None:
    """Return a deprecation message if scholar_profile_url is set without any manual seed input;
    else None. Used to steer users to the manual seed-paper path (no live fetch is done)."""
    pers = (config or {}).get("personalization", {}) or {}
    if not pers.get("enabled", False):
        return None
    has_seed = bool(pers.get("seed_paper_dir") or pers.get("seed_papers_file") or pers.get("bibtex_file"))
    if pers.get("scholar_profile_url") and not has_seed:
        return _GS_DEPRECATION_MSG
    return None
