from __future__ import annotations

from difflib import SequenceMatcher
import re


BANNED_CLAIMS = (
    "омолодит", "стройнит на", "идеально всем", "гарантированно", "100% оригинал",
    "лучшая цена", "последний шанс", "1:1", "точная копия", "реплика",
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^а-яёa-z0-9 ]", " ", text.lower())).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def validate_post(post: dict, previous_texts: list[str] | None = None) -> list[str]:
    reasons: list[str] = []
    slides = post.get("slides") or []
    caption = str(post.get("caption") or "")
    if not 2 <= len(slides) <= 20:
        reasons.append("slide_count_not_2_to_20")
    if any(len(str(slide).strip()) > 125 for slide in slides):
        reasons.append("slide_too_long")
    combined = " ".join(map(str, slides)) + " " + caption
    low = combined.lower()
    for claim in BANNED_CLAIMS:
        if claim in low:
            reasons.append(f"banned_claim:{claim}")
    for previous in previous_texts or []:
        if similarity(combined, previous) >= 0.78:
            reasons.append("near_duplicate")
            break
    if not post.get("rights_status") == "original":
        reasons.append("rights_not_confirmed")
    if post.get("commercial") and not post.get("commercial_reviewed"):
        reasons.append("commercial_review_required")
    return reasons
