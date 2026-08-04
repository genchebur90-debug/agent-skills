#!/usr/bin/env python3
"""
planlint.py — refuse to produce a shot that is guaranteed to drift.

Why this exists
---------------
production-order.md states the law: "every generation names its parents", and
"each thing is described in words exactly once — a product never, because a
product comes from a photograph". Both were prose. packet.py required only `id`
and `prompt`, so a shot containing a locked product could go out as
text-to-video with the bottle described in words, and nothing objected. The
documentation was right and the toolchain didn't enforce it, which is the same
as not having the rule.

This module is the enforcement, and it is also the one place that knows what
the plan fields are called. packet.py and generate.py import `normalize_plan`
from here instead of each inventing their own spelling of "reference".

Usage
-----
    planlint.py --plan plan.json                 # human summary, exit 1 on errors
    planlint.py --plan plan.json --json
    planlint.py --plan plan.json --strict        # warnings become errors
    planlint.py --plan plan.json --campaign perfume-noir

Exit codes: 0 clean (or warnings only), 1 errors, 2 could not read the plan.

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

STATE_DIR = Path(".campaign")

# Field spellings seen in the wild, mapped to the canonical name.
REF_KEYS = ("parents", "parent_plates", "refs", "reference", "references",
            "reference_images", "reference_image_urls", "init_image", "first_frame")
LOCK_KEYS = ("locks", "locked", "locked_in_frame")

TEXT_TO_VIDEO = re.compile(r"text[-_ ]?to[-_ ]?video|t2v", re.I)
IMAGE_ROUTE = re.compile(r"image[-_ ]?to[-_ ]?video|i2v|reference[-_ ]?to[-_ ]?video|"
                         r"first[-_ ]?last|motion[-_ ]?control", re.I)
VIDEO_EXT = re.compile(r"\.(mp4|mov|webm|mkv|avi)$", re.I)

GRADE_WORDS = re.compile(r"\b(colou?r[- ]graded|teal and orange|LUT|film emulation|"
                         r"kodak \d|instagram filter|heavily graded)\b", re.I)
LETTERING_WORDS = re.compile(r"\b(text overlay|subtitle|caption|lower third|"
                             r"title card|end card|watermark|logo appears|"
                             r"typography on screen)\b", re.I)
BLANK_PRODUCT = re.compile(r"\b(no text on|blank label|unbranded|no logo|plain bottle|"
                           r"generic packaging|label[- ]free)\b", re.I)


# ---------------------------------------------------------------------------
# Normalisation — the single source of truth for plan field names
# ---------------------------------------------------------------------------

def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if str(x).strip()]
    return []


def normalize_shot(shot: dict) -> dict:
    """Return a copy with canonical `parents` and `locks`, originals kept."""
    out = dict(shot)
    parents: list[str] = []
    for k in REF_KEYS:
        for p in _as_list(shot.get(k)):
            if p not in parents:
                parents.append(p)
    out["parents"] = parents

    locks: list[str] = []
    for k in LOCK_KEYS:
        for l in _as_list(shot.get(k)):
            l = l.strip()
            if l and l not in locks:
                locks.append(l)
    out["locks"] = locks
    out["route"] = str(shot.get("need") or shot.get("route") or "").strip()
    return out


def normalize_plan(plan: dict) -> dict:
    out = dict(plan)
    out["shots"] = [normalize_shot(s) for s in plan.get("shots", [])]
    return out


def lock_kind(lock: str) -> tuple[str, str]:
    """'product:noir-50' -> ('product', 'noir-50'). Bare names are 'thing'."""
    if ":" in lock:
        kind, _, name = lock.partition(":")
        return kind.strip().lower(), name.strip()
    return "thing", lock.strip()


# ---------------------------------------------------------------------------
# Campaign lookup (optional — planlint works standalone)
# ---------------------------------------------------------------------------

def load_campaign(name: str | None) -> dict:
    try:
        if not name:
            active = STATE_DIR / "active.json"
            if not active.is_file():
                return {}
            name = json.loads(active.read_text(encoding="utf-8")).get("name")
        p = STATE_DIR / f"{name}.json"
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {}


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def lint(plan: dict, campaign: dict | None = None) -> dict:
    campaign = campaign or {}
    plan = normalize_plan(plan)
    shots = plan.get("shots", [])
    errors: list[dict] = []
    warnings: list[dict] = []

    def err(shot_id: str, code: str, msg: str, fix: str) -> None:
        errors.append({"shot": shot_id, "code": code, "problem": msg, "fix": fix})

    def warn(shot_id: str, code: str, msg: str, fix: str) -> None:
        warnings.append({"shot": shot_id, "code": code, "problem": msg, "fix": fix})

    if not shots:
        return {"ok": False, "errors": [{"shot": None, "code": "E0",
                "problem": "plan has no shots",
                "fix": "write the shot ledger first — production-order.md step 1"}],
                "warnings": [], "shots": 0}

    known_products = set(campaign.get("products", {}))
    known_chars = set(campaign.get("characters", {}))
    shot_ids = [str(s.get("id") or "") for s in shots]
    seen: set[str] = set()

    for s in shots:
        sid = str(s.get("id") or "?")
        prompt = str(s.get("prompt") or "")
        locks = s.get("locks", [])
        parents = s.get("parents", [])
        route = s.get("route", "")
        note = str(s.get("note") or "")

        # --- structural -----------------------------------------------------
        if not s.get("id"):
            err(sid, "E1", "shot has no id",
                "give every shot a stable id — the inbox contract is inbox/<id>.<ext>")
        if sid in seen:
            err(sid, "E1", f"duplicate shot id {sid!r}", "ids must be unique")
        seen.add(sid)
        if not prompt.strip():
            err(sid, "E1", "shot has no prompt", "write one, or drop the shot")

        # --- the one law: every generation names its parents ----------------
        if locks and not parents:
            err(sid, "E3",
                f"shot locks {', '.join(locks)} but names no parent plate",
                "add \"parents\": [\"plates/<thing>.png\"]. A locked thing enters a "
                "prompt as an image; if there is no plate yet, build it first "
                "(production-order.md, Tier 0-2).")

        if locks and TEXT_TO_VIDEO.search(route):
            err(sid, "E4",
                f"route is {route!r} but the shot contains locked things: "
                f"{', '.join(locks)}",
                "text-to-video cannot hold identity. Use image-to-video or "
                "reference-to-video from the plate.")

        if locks and not route:
            warn(sid, "W5", "no route declared for a shot with locked things",
                 "set \"need\": \"image-to-video\" or \"reference-to-video\"")

        if parents and not locks:
            warn(sid, "W7", "parents given but nothing declared locked",
                 "list what must stay identical in \"locks\" so verification knows "
                 "what to check")

        # --- no chaining generations ---------------------------------------
        for p in parents:
            if VIDEO_EXT.search(p):
                err(sid, "E8", f"parent {p!r} is a video file",
                    "never continue from the last frame of the previous clip — drift "
                    "compounds. Return to the plate every time.")
            base = Path(p).stem
            if base in shot_ids and base != sid:
                err(sid, "E8", f"parent {p!r} is another shot's output",
                    "generate from the Tier 0-2 plates, not from a sibling shot")

        # --- two locked things in one frame ---------------------------------
        heavy = [l for l in locks if lock_kind(l)[0] in ("product", "character",
                                                         "person", "thing")]
        if len(heavy) >= 2 and not s.get("accepted_risk"):
            err(sid, "E6",
                f"{len(heavy)} locked things in one frame: {', '.join(heavy)}",
                "no current model holds two referenced subjects reliably. Split the "
                "shot, put one out of focus or out of frame, or set "
                "\"accepted_risk\": true with a note saying why.")

        # --- registry agreement ---------------------------------------------
        for l in locks:
            kind, name = lock_kind(l)
            if kind == "product" and known_products and name not in known_products:
                err(sid, "E5", f"locked product {name!r} is not in the campaign registry",
                    f"known: {sorted(known_products)}. Register it: campaign.py "
                    f"add-product --name {name} --refs <real photo>")
            if kind == "character" and known_chars and name not in known_chars:
                err(sid, "E5", f"locked character {name!r} is not in the registry",
                    f"known: {sorted(known_chars)}")
            if kind == "product" and name in known_products:
                rec = campaign["products"][name]
                if not any("stored" in r for r in rec.get("refs", [])):
                    err(sid, "E7", f"product {name!r} has no real photograph stored",
                        "the plate IS the product. Ask the user for photos before "
                        "generating anything that shows it.")

        # --- describing a locked product in words ---------------------------
        if BLANK_PRODUCT.search(prompt):
            err(sid, "E9", "prompt asks for an unbranded or text-free product",
                "the label is the product. A blank pack is the wrong product, not a "
                "safe default. consistency.md, Part 1.")

        for l in locks:
            kind, name = lock_kind(l)
            if kind != "product" or name not in known_products:
                continue
            rec = campaign["products"][name]
            described = _describes(prompt, rec)
            if described:
                warn(sid, "W9",
                     f"prompt re-describes the locked product ({', '.join(described)})",
                     "point at the plate instead — \"the flacon from @Image1\". A "
                     "described object is a second version of it.")

        # --- duration --------------------------------------------------------
        secs = s.get("seconds")
        if isinstance(secs, (int, float)):
            if locks and secs > 5:
                warn(sid, "W1", f"{secs}s clip with locked things",
                     "keep locked clips 3-5s — drift accumulates with duration. "
                     "Two 4s clips end closer to the plate than one 8s clip.")
            if secs < 4 and "trim" not in note.lower():
                warn(sid, "W6", f"{secs}s is under the usual 4s model minimum",
                     "generate at the minimum and trim in the edit; say so in the note")

        # --- things that belong to the edit ---------------------------------
        if GRADE_WORDS.search(prompt):
            warn(sid, "W3", "grading described in the prompt",
                 "ask for neutral output and grade the assembly once in video-editor. "
                 "Colour consistency achieved by prompting is not consistency.")
        if LETTERING_WORDS.search(prompt):
            warn(sid, "W4", "on-screen text or logo asked for in the prompt",
                 "lettering and logos are composited in the edit, where they are "
                 "deterministic. A generated logo is a fresh lottery ticket per clip.")

        # --- reserved zone ----------------------------------------------------
        reserve = s.get("reserve") or plan.get("reserve")
        neg = str(s.get("negative") or "")
        if reserve and reserve != "none":
            body = prompt + " " + neg
            if not re.search(r"(stays? (dark|empty|clear)|no light creep|keep[- ]?out|"
                             r"nothing enters)", body, re.I):
                warn(sid, "W2", f"reserved {reserve} zone with no preservation clause",
                     "models fill space. Say it in the negative: \"the lower third "
                     "stays dark and empty throughout, no light creep\".")

    ok = not errors
    return {"ok": ok, "shots": len(shots), "errors": errors, "warnings": warnings,
            "locked_shots": sum(1 for s in shots if s.get("locks")),
            "campaign": campaign.get("name")}


def _describes(prompt: str, product: dict) -> list[str]:
    """Attributes of a locked product that the prompt spells out in words.

    Naming the product is fine and often necessary ("the flacon from @Image1").
    Re-stating its material, colour, label or shape is invention with a hint,
    and it is the mechanism behind "why is the bottle a different shape".
    """
    hits = []
    low = prompt.lower()
    for field, tag in (("material", "material"), ("colour", "colour")):
        val = str(product.get(field) or "")
        for token in re.split(r"[,;]", val):
            token = token.strip().lower()
            if len(token) > 3 and token in low and tag not in hits:
                hits.append(tag)
    for line in product.get("label_lines", []):
        if len(str(line)) > 2 and str(line).lower() in low and "label text" not in hits:
            hits.append("label text")
    return hits


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render(report: dict) -> str:
    lines = []
    head = "PASS" if report["ok"] else "BLOCKED"
    lines.append(f"planlint: {head} — {report['shots']} shots, "
                 f"{report.get('locked_shots', 0)} with locks, "
                 f"{len(report['errors'])} errors, {len(report['warnings'])} warnings")
    for group, items in (("ERROR", report["errors"]), ("warn", report["warnings"])):
        for it in items:
            lines.append(f"  [{group} {it['code']}] {it['shot']}: {it['problem']}")
            lines.append(f"        fix: {it['fix']}")
    if report["ok"] and not report["warnings"]:
        lines.append("  every locked shot names a plate and takes an image route.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate plan.json against the "
                                             "production-order laws.")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--campaign", help="campaign name (default: the active one)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="warnings become errors")
    args = ap.parse_args(argv)

    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": f"cannot read plan: {e}"}, indent=2),
              file=sys.stderr)
        return 2

    report = lint(plan, load_campaign(args.campaign))
    if args.strict and report["warnings"]:
        report["errors"] = report["errors"] + report["warnings"]
        report["ok"] = False

    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json
          else render(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
