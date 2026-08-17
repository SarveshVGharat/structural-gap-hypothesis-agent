"""Venue registry — maps VenueConfig.mode to a list of OpenReview invitation specs.

Modes
-----
a_star       : All A* ML/NLP/CV/IR venues on OpenReview (broadest)
top_ml       : NeurIPS, ICML, ICLR, TMLR, AISTATS
top_nlp      : ACL, EMNLP, NAACL, EACL, COLM
top_cv       : CVPR, ICCV, ECCV  (limited OpenReview presence)
top_ir       : SIGIR, WSDM, CIKM, WWW
custom       : user-provided venue list (VenueConfig.custom_venues)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import VenueConfig


@dataclass
class VenueSpec:
    name: str                # human-readable name, e.g. "ICLR 2025"
    invitation: str          # OpenReview invitation ID
    venueid: str             # OpenReview venue group ID
    has_openreview: bool = True


# ── Venue catalogue ───────────────────────────────────────────────────────────
# Each tuple: (invitation, venueid, display_name)

_ML_VENUES: list[tuple[str, str, str]] = [
    ("ICLR.cc/2025/Conference/-/Submission",    "ICLR.cc/2025/Conference",    "ICLR 2025"),
    ("NeurIPS.cc/2024/Conference/-/Submission", "NeurIPS.cc/2024/Conference", "NeurIPS 2024"),
    ("ICML.cc/2024/Conference/-/Submission",    "ICML.cc/2024/Conference",    "ICML 2024"),
    ("ICLR.cc/2024/Conference/-/Submission",    "ICLR.cc/2024/Conference",    "ICLR 2024"),
    ("NeurIPS.cc/2023/Conference/-/Submission", "NeurIPS.cc/2023/Conference", "NeurIPS 2023"),
    ("ICML.cc/2023/Conference/-/Submission",    "ICML.cc/2023/Conference",    "ICML 2023"),
    ("ICLR.cc/2023/Conference/-/Submission",    "ICLR.cc/2023/Conference",    "ICLR 2023"),
    ("NeurIPS.cc/2022/Conference/-/Submission", "NeurIPS.cc/2022/Conference", "NeurIPS 2022"),
    ("ICML.cc/2022/Conference/-/Submission",    "ICML.cc/2022/Conference",    "ICML 2022"),
    ("ICLR.cc/2022/Conference/-/Submission",    "ICLR.cc/2022/Conference",    "ICLR 2022"),
    ("TMLR/-/Submission",                        "TMLR",                       "TMLR"),
    ("AISTATS.cc/2024/Conference/-/Submission", "AISTATS.cc/2024/Conference", "AISTATS 2024"),
    ("AISTATS.cc/2023/Conference/-/Submission", "AISTATS.cc/2023/Conference", "AISTATS 2023"),
    ("UAI.cc/2024/Conference/-/Submission",     "UAI.cc/2024/Conference",     "UAI 2024"),
    ("UAI.cc/2023/Conference/-/Submission",     "UAI.cc/2023/Conference",     "UAI 2023"),
]

# NLP venues — ACL Anthology is the canonical source; OpenReview coverage is partial
_NLP_VENUES: list[tuple[str, str, str]] = [
    ("aclanthology.org/2024.acl-long",   "aclanthology.org/2024.acl-long",   "ACL 2024"),
    ("aclanthology.org/2024.emnlp-main", "aclanthology.org/2024.emnlp-main", "EMNLP 2024"),
    ("aclanthology.org/2024.naacl-long", "aclanthology.org/2024.naacl-long", "NAACL 2024"),
    ("aclanthology.org/2024.eacl-long",  "aclanthology.org/2024.eacl-long",  "EACL 2024"),
    ("aclanthology.org/2024.colm-main",  "aclanthology.org/2024.colm-main",  "COLM 2024"),
    ("aclanthology.org/2023.acl-long",   "aclanthology.org/2023.acl-long",   "ACL 2023"),
    ("aclanthology.org/2023.emnlp-main", "aclanthology.org/2023.emnlp-main", "EMNLP 2023"),
]

# CV venues — mostly not on OpenReview; retrieval comes from arXiv/S2 for these
_CV_VENUES: list[tuple[str, str, str]] = [
    ("CVPR.cc/2024/Conference/-/Submission", "CVPR.cc/2024/Conference", "CVPR 2024"),
    ("CVPR.cc/2023/Conference/-/Submission", "CVPR.cc/2023/Conference", "CVPR 2023"),
]

# IR venues — mainly not on OpenReview
_IR_VENUES: list[tuple[str, str, str]] = []

_VENUE_MODE_MAP: dict[str, list[tuple[str, str, str]]] = {
    "top_ml":  _ML_VENUES,
    "top_nlp": _NLP_VENUES,
    "top_cv":  _CV_VENUES,
    "top_ir":  _IR_VENUES,
    "a_star":  _ML_VENUES + _NLP_VENUES + _CV_VENUES,
}


def get_venue_specs(config: "VenueConfig") -> list[VenueSpec]:
    """Return the list of VenueSpec objects for the given VenueConfig."""
    mode = config.mode
    if mode == "custom":
        return _parse_custom_venues(config.custom_venues)

    tuples = _VENUE_MODE_MAP.get(mode, _ML_VENUES)
    return [VenueSpec(name=name, invitation=inv, venueid=vid) for inv, vid, name in tuples]


def _parse_custom_venues(names: list[str]) -> list[VenueSpec]:
    """Attempt to match custom venue names against the catalogue."""
    all_tuples = _ML_VENUES + _NLP_VENUES + _CV_VENUES + _IR_VENUES
    result: list[VenueSpec] = []
    for raw in names:
        low = raw.lower()
        matched = [
            VenueSpec(name=name, invitation=inv, venueid=vid)
            for inv, vid, name in all_tuples
            if low in name.lower() or low in vid.lower()
        ]
        result.extend(matched)
    return result or [VenueSpec(name=n, invitation=n, venueid=n) for n in names]


def venue_spec_to_openreview_params(spec: VenueSpec) -> dict[str, str]:
    return {"invitation": spec.invitation, "venueid": spec.venueid, "venue_name": spec.name}
