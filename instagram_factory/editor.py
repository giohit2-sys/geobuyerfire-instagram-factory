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
    media_type = str(post.get("media_type") or "carousel").lower()
    slides = post.get("slides") or []
    caption = str(post.get("caption") or "")
    if media_type == "carousel":
        if not 2 <= len(slides) <= 20:
            reasons.append("slide_count_not_2_to_20")
        if any(len(str(slide).strip()) > 125 for slide in slides):
            reasons.append("slide_too_long")
        creative_texts = list(map(str, slides))
    elif media_type == "image":
        creative_texts = [str(post.get("on_image_text") or "")]
        if not creative_texts[0].strip() or len(creative_texts[0]) > 125:
            reasons.append("image_text_invalid")
    elif media_type == "reel":
        scenes = post.get("scenes") or []
        if not 1 <= len(scenes) <= 4:
            reasons.append("reel_scene_count_not_1_to_4")
        if any(not scene.get("source_asset") for scene in scenes):
            reasons.append("reel_scene_missing_source")
        creative_texts = [str(scene.get("text") or "") for scene in scenes]
        if any(len(text.strip()) > 125 for text in creative_texts):
            reasons.append("reel_text_too_long")
    elif media_type == "story":
        if not post.get("source_asset"):
            reasons.append("story_missing_source")
        creative_texts = [str(post.get("text") or "")]
        if len(creative_texts[0].strip()) > 125:
            reasons.append("story_text_too_long")
    else:
        creative_texts = []
        reasons.append("unsupported_media_type")
    combined = " ".join(creative_texts) + " " + caption
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
