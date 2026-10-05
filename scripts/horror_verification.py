"""Fail-closed factual, authenticity, and production gates for true-horror episodes."""
from __future__ import annotations
import re
from typing import Any

APPROVED = "APPROVED"
TYPES = {"true_case", "unexplained_event", "urban_legend"}
LABELS = {"REAL_EVENT", "UNEXPLAINED_EVENT", "URBAN_LEGEND"}
TIERS = {"primary", "official", "reputable_press", "academic", "archive", "interview", "public_reference"}

def _s(v: Any) -> str: return str(v or "").strip()
def _fail(msg: str) -> None: raise ValueError(f"HORROR GATE FAILED: {msg}")

def validate_source(source: Any, index: int) -> None:
    if not isinstance(source, dict): _fail(f"source {index} is not an object")
    required = ("title", "publisher_or_author", "date", "url", "tier", "supports")
    missing = [k for k in required if not _s(source.get(k))]
    if missing: _fail(f"source {index} missing: {', '.join(missing)}")
    if source.get("tier") not in TIERS: _fail(f"source {index} has invalid tier")
    if not re.match(r"^https?://", _s(source.get("url"))): _fail(f"source {index} URL is not verifiable")

def validate_report(report: Any, story_type: str) -> None:
    if not isinstance(report, dict): _fail("verification_report must be an object")
    required = ("case_name", "classification", "period", "location", "people", "facts", "sources", "confirmed_claims", "disputed_claims", "excluded_claims", "verified_quotes", "decision")
    missing = [k for k in required if k not in report]
    if missing: _fail("verification_report missing: " + ", ".join(missing))
    if report.get("decision") != APPROVED: _fail("decision must be APPROVED")
    if report.get("classification") != story_type: _fail("report classification mismatch")
    sources = report.get("sources")
    if not isinstance(sources, list) or len(sources) < 2: _fail("at least two independent sources are required")
    for i, source in enumerate(sources, 1): validate_source(source, i)
    if len({_s(s.get("url")) for s in sources}) < 2: _fail("sources must be independent")
    for key in ("confirmed_claims", "disputed_claims", "excluded_claims", "verified_quotes"):
        if not isinstance(report.get(key), list): _fail(f"{key} must be a list")

def validate_visual_plan(episode: dict[str, Any]) -> None:
    keywords = episode.get("visual_keywords")
    matches = episode.get("visual_match")
    if not isinstance(keywords, list) or not 7 <= len(keywords) <= 10: _fail("visual_keywords must contain 7–10 searches")
    if not isinstance(matches, list) or len(matches) != len(keywords): _fail("visual_match must align one-to-one with visual_keywords")
    for i, item in enumerate(matches, 1):
        if not isinstance(item, dict): _fail(f"visual_match {i} is not an object")
        for key in ("keyword", "scene", "place", "source_type", "authenticity", "status"):
            if not _s(item.get(key)): _fail(f"visual_match {i} missing {key}")
        if item.get("status") != "PASS": _fail(f"visual_match {i} is not approved")
        if item.get("authenticity") not in {"REAL_ARCHIVE", "REAL_LOCATION", "MAP", "SYMBOLIC", "REENACTMENT", "AI_RECONSTRUCTION"}: _fail(f"visual_match {i} has invalid authenticity")
        if item.get("authenticity") == "REENACTMENT" and "إعادة تمثيل" not in _s(item.get("label")):
            _fail(f"visual_match {i} reenactment is not labeled")
        if item.get("authenticity") == "AI_RECONSTRUCTION" and "Reconstruction" not in _s(item.get("label")):
            _fail(f"visual_match {i} AI reconstruction is not labeled")

def validate_production_table(table: Any) -> None:
    if not isinstance(table, list) or len(table) < 7: _fail("production_table must contain scene rows")
    for i, row in enumerate(table, 1):
        if not isinstance(row, dict): _fail(f"production row {i} is not an object")
        for key in ("time", "narration", "scene", "scene_source", "sound_effect", "music", "subtitle", "tension"):
            if key not in row: _fail(f"production row {i} missing {key}")
        if not isinstance(row.get("tension"), int) or not 1 <= row["tension"] <= 5: _fail(f"production row {i} tension must be 1–5")

def validate_episode(episode: dict[str, Any]) -> None:
    if not isinstance(episode, dict): _fail("episode must be an object")
    story_type = _s(episode.get("story_type"))
    label = _s(episode.get("authenticity_label"))
    if story_type not in TYPES: _fail("invalid story_type")
    if label not in LABELS: _fail("invalid authenticity_label")
    if story_type == "true_case" and label != "REAL_EVENT": _fail("true_case must use REAL_EVENT")
    if story_type == "urban_legend" and label != "URBAN_LEGEND": _fail("urban_legend must use URBAN_LEGEND")
    validate_report(episode.get("verification_report"), story_type)
    validate_visual_plan(episode)
    validate_production_table(episode.get("production_table"))
    validate_final_checks(episode.get("final_checks"))
    caption = _s(episode.get("caption"))
    if "#رعب" not in caption and "#رعب_حقيقي" not in caption: _fail("caption must identify the horror channel")
    narration = _s(episode.get("narration"))
    if any(phrase in narration for phrase in ("إنه شبح", "هذا شبح حقيقي", "قوة خارقة مؤكدة")) and story_type != "urban_legend": _fail("unproven supernatural claim presented as fact")

def validate_final_checks(checks: dict[str, Any]) -> None:
    required = ("fact_check", "visual_check", "horror_check", "authenticity_check", "audio_check", "subtitle_check", "sensitivity_check")
    if not isinstance(checks, dict): _fail("final_checks must be an object")
    failed = [key for key in required if checks.get(key) != "PASS"]
    if failed: _fail("final checks failed: " + ", ".join(failed))
