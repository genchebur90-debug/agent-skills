#!/usr/bin/env python3
"""
campaign.py — campaign registry: variant tracking, character consistency assets,
and per-account assignment across several social accounts.

Solves two failure modes that only appear when you run more than one account:

  1. The same cut posted to two accounts. Overlapping audiences read duplicates
     as spam, and it wastes a variant slot.
  2. A recurring character drifting across a campaign, because someone generated
     video 8 from a frame of video 7 instead of from the canonical references.

Usage:
    campaign.py init --name shampoo-summer [--brand "Acme"]
    campaign.py add-character --name mascot --refs a.png b.png c.png
    campaign.py character --name mascot                  # show refs + prompt lock
    campaign.py add-product --name shampoo-500 --refs bottle.jpg --profile pack \\
                         --identity "amber 500ml pump bottle, three-line black lockup" \\
                         --label-lines "ACME" "REPAIR" "500 ml" --closure "black pump cap on"
    campaign.py product --name shampoo-500                # plate, lock card, gaps
    campaign.py lockcard --text                           # paste into every prompt
    campaign.py verify --product shampoo-500 --shot s3    # per-clip check fields
    campaign.py profiles                                  # identity by product family
    campaign.py register --variant v1 --account ig_main --platform reels \\
                         [--hook "..."] [--register ugc] [--file deliver/reels.mp4]
    campaign.py check --account ig_main                   # what has this account had?
    campaign.py next --account ig_main                    # unused variants for it
    campaign.py status                                    # whole campaign
    campaign.py variants                                  # all variants and placements

State lives in .campaign/<name>.json next to where you run it.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_DIR = Path(".campaign")
ACTIVE = STATE_DIR / "active.json"


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def active_name() -> str | None:
    if ACTIVE.is_file():
        try:
            return json.loads(ACTIVE.read_text(encoding="utf-8")).get("name")
        except (json.JSONDecodeError, OSError):
            return None
    return None


def campaign_path(name: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)
    return STATE_DIR / f"{safe}.json"


def load(name: str | None = None) -> tuple[dict, Path] | tuple[None, None]:
    name = name or active_name()
    if not name:
        return None, None
    p = campaign_path(name)
    if not p.is_file():
        return None, None
    try:
        return json.loads(p.read_text(encoding="utf-8")), p
    except (json.JSONDecodeError, OSError):
        return None, None


def save(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated"] = now()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def need_campaign(name: str | None) -> tuple[dict, Path]:
    data, path = load(name)
    if data is None:
        print(json.dumps({
            "error": "no active campaign",
            "hint": "campaign.py init --name <campaign-name>",
        }, indent=2))
        sys.exit(1)
    return data, path  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Asset copying — canonical references must be stable, not scratch files
# ---------------------------------------------------------------------------

def store_refs(campaign: str, kind: str, name: str, refs: list[str]) -> list[dict]:
    """Copy reference images into the campaign asset store so they survive."""
    dest_dir = STATE_DIR / "assets" / campaign / kind / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for r in refs:
        src = Path(r)
        entry: dict[str, Any] = {"source": str(src)}
        if src.is_file():
            dest = dest_dir / src.name
            try:
                if src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
                entry["stored"] = str(dest)
            except (OSError, shutil.Error) as e:
                entry["error"] = f"could not copy: {e}"
        else:
            entry["error"] = "file not found — stored as a path reference only"
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args) -> dict:
    p = campaign_path(args.name)
    if p.is_file() and not args.force:
        data, _ = load(args.name)
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVE.write_text(json.dumps({"name": args.name}), encoding="utf-8")
        return {"campaign": args.name, "existing": True, "activated": True,
                "variants": len(data.get("variants", {})) if data else 0,
                "note": "Campaign already existed; made it active. Use --force to reset."}

    data = {
        "name": args.name,
        "brand": args.brand or "",
        "created": now(),
        "characters": {},
        "products": {},
        "variants": {},
        "placements": [],
    }
    save(data, p)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE.write_text(json.dumps({"name": args.name}), encoding="utf-8")
    return {"campaign": args.name, "created": True, "state": str(p)}


def cmd_add_character(args) -> dict:
    data, path = need_campaign(args.campaign)
    refs = store_refs(data["name"], "characters", args.name, args.refs)
    data["characters"][args.name] = {
        "name": args.name,
        "refs": refs,
        "wardrobe": args.wardrobe or "",
        "lighting": args.lighting or "",
        "prompt_lock": args.prompt_lock or "",
        "seed": args.seed,
        "platform": args.platform or "",
        "model": args.model or "",
        "added": now(),
    }
    save(data, path)
    stored = [r["stored"] for r in refs if "stored" in r]
    return {
        "character": args.name,
        "stored_refs": stored,
        "missing": [r["source"] for r in refs if "error" in r],
        "rule": (
            "ALWAYS generate this character from these stored references. Never "
            "generate from a frame of a previous video — that compounds drift and "
            "the character becomes someone else within about ten videos."
        ),
    }


def cmd_character(args) -> dict:
    data, _ = need_campaign(args.campaign)
    c = data["characters"].get(args.name)
    if not c:
        return {"error": f"no character named {args.name!r}",
                "known": list(data["characters"])}
    lock_bits = [b for b in (c.get("wardrobe"), c.get("lighting"),
                             c.get("prompt_lock")) if b]
    return {
        "character": c["name"],
        "use_these_refs": [r.get("stored") or r["source"] for r in c["refs"]],
        "repeat_verbatim_in_every_prompt": ", ".join(lock_bits) or None,
        "seed": c.get("seed"),
        "platform": c.get("platform") or None,
        "model": c.get("model") or None,
        "reminder": "Keep clips 3-5s. Verify against these refs, not against the last clip.",
    }


# ---------------------------------------------------------------------------
# Product identity — the half of consistency that used to be prose only
# ---------------------------------------------------------------------------
#
# Characters were instrumented from the start: prompt_lock, seed, wardrobe,
# lighting, all stored and repeated verbatim. Products were not — they got a
# folder of photographs and a sentence of advice. That asymmetry is exactly
# what a real campaign fails on: the model stays itself because its lock is
# text that gets pasted into every prompt, while the bottle drifts because
# nothing carried its identity into the prompt at all.
#
# So a product now stores an IDENTITY SPEC: the few facts a buyer uses to
# recognise this object and no other. `lockcard` prints them as a block that
# goes into every shot prompt, every packet page and every review.

# What "identity" means per family of product. The keys are advisory: they tell
# the agent which questions to answer, and planlint warns when they are empty.
PROFILES: dict[str, dict] = {
    "pack": {
        "label": "bottle, jar, tube, box, can, fragrance, cosmetics, drinks",
        "identity": ["exact label wording and line order", "logo lockup",
                     "closure/cap present", "silhouette of the vessel",
                     "material and tint", "fill level and liquid colour"],
    },
    "food": {
        "label": "burger, pizza, coffee, ice cream, plated dishes",
        "identity": ["build and layer order", "portion size and proportions",
                     "doneness and colour", "garnish and sauce",
                     "vessel or wrapper it is served in"],
    },
    "vehicle": {
        "label": "cars, motorcycles, bikes, boats, machinery",
        "identity": ["model and body shape", "grille and light signature",
                     "wheel design", "body colour and finish", "badges",
                     "trim details that differ between versions"],
    },
    "space": {
        "label": "apartments, houses, hotels, restaurants, gyms, clinics",
        "identity": ["layout and sightlines", "window shape and view",
                     "floor and wall finishes", "fixed furniture",
                     "light direction and time of day"],
    },
    "apparel": {
        "label": "clothing, shoes, bags, jewellery, watches",
        "identity": ["cut and silhouette", "colourway", "material and weave",
                     "hardware and fastenings", "logo placement",
                     "dial/face details for watches"],
    },
    "device": {
        "label": "phones, laptops, appliances, hardware, tools",
        "identity": ["form factor and proportions", "port and button layout",
                     "finish and colour", "branding placement",
                     "screen content if the screen is visible"],
    },
    "screen": {
        "label": "apps, SaaS, dashboards, games",
        "identity": ["real UI, captured not invented", "brand colours and type",
                     "the exact screen states shown", "cursor/gesture behaviour"],
    },
    "service": {
        "label": "salons, courses, travel, logistics, insurance",
        "identity": ["the proof object the buyer sees", "staff look and uniform",
                     "environment and signage", "documents or interfaces shown"],
    },
    "person": {
        "label": "a founder, a creator, a named spokesperson",
        "identity": ["face and build", "wardrobe", "hair", "voice and accent",
                     "setting they always appear in"],
    },
}


def cmd_profiles(args) -> dict:
    return {"profiles": {k: {"covers": v["label"], "identity_is": v["identity"]}
                         for k, v in PROFILES.items()},
            "use": "campaign.py add-product --name X --profile pack --refs photo.jpg ...",
            "note": "The profile only decides which questions to answer. Any product "
                    "not on the list: pick the nearest and add --must items by hand."}


def cmd_add_product(args) -> dict:
    data, path = need_campaign(args.campaign)
    refs = store_refs(data["name"], "products", args.name, args.refs)
    profile = (args.profile or "").strip().lower()
    if profile and profile not in PROFILES:
        return {"error": f"unknown profile {profile!r}", "known": sorted(PROFILES)}

    prev = data["products"].get(args.name, {})
    rec = {
        "name": args.name,
        "refs": refs,
        "profile": profile or prev.get("profile", ""),
        "category": args.category or prev.get("category", ""),
        "identity": args.identity or prev.get("identity", ""),
        "label_lines": args.label_lines or prev.get("label_lines", []),
        "closure": args.closure or prev.get("closure", ""),
        "colour": args.colour or prev.get("colour", ""),
        "material": args.material or prev.get("material", ""),
        "must": args.must or prev.get("must", []),
        "forbid": args.forbid or prev.get("forbid", []),
        "lighting": args.lighting or prev.get("lighting", ""),
        "prompt_lock": args.prompt_lock or prev.get("prompt_lock", ""),
        "seed": args.seed if args.seed is not None else prev.get("seed"),
        "platform": args.platform or prev.get("platform", ""),
        "model": args.model or prev.get("model", ""),
        "added": prev.get("added") or now(),
        "updated": now(),
    }
    data["products"][args.name] = rec
    save(data, path)

    real = [r for r in refs if "stored" in r]
    gaps = _product_gaps(rec)
    return {
        "product": args.name,
        "stored_refs": [r["stored"] for r in real],
        "missing": [r["source"] for r in refs if "error" in r],
        "identity_gaps": gaps or None,
        "warning": None if real else (
            "No real product photo stored. Without one the model will invent a "
            "product that is not the user's — the label will be wrong. Ask for photos."
        ),
        "next": "python3 scripts/campaign.py lockcard --product " + args.name,
        "rule": "Generate product shots from these refs (image-to-video or "
                "reference-to-video), never text-to-video, and paste the lock card "
                "into every shot prompt.",
    }


def _product_gaps(rec: dict) -> list[str]:
    """Which identity questions this product has not answered yet."""
    gaps = []
    if not any("stored" in r for r in rec.get("refs", [])):
        gaps.append("no real photograph stored — the plate is the product, "
                    "everything else is invention")
    if not rec.get("identity") and not rec.get("must"):
        gaps.append("no identity sentence and no --must features: nothing tells a "
                    "later prompt what makes this object recognisable")
    prof = PROFILES.get(rec.get("profile", ""))
    if not rec.get("profile"):
        gaps.append("no --profile: pick one from `campaign.py profiles` so the right "
                    "identity questions get asked")
    elif prof:
        if prof is PROFILES.get("pack") and not rec.get("label_lines"):
            gaps.append("packaging with no --label-lines: the type IS the product, and "
                        "an unspecified label is the most common way the wrong product "
                        "ships")
        if prof is PROFILES.get("pack") and not rec.get("closure"):
            gaps.append("no --closure note: a pack shot with the cap missing reads as "
                        "in-use, not as presented")
    return gaps


def _lock_lines(rec: dict) -> list[str]:
    """The block that must be repeated verbatim wherever this product appears."""
    plate = [r.get("stored") or r["source"] for r in rec.get("refs", [])]
    out = [f"PRODUCT LOCK — {rec['name']}"]
    if rec.get("identity"):
        out.append(f"  identity      : {rec['identity']}")
    if rec.get("profile"):
        out.append(f"  profile       : {rec['profile']}")
    if plate:
        out.append(f"  plate         : {', '.join(plate)}")
        out.append("                  ^ this image IS the product. It enters the prompt "
                   "as an image, never as a description.")
    if rec.get("label_lines"):
        out.append("  label         : " + " / ".join(rec["label_lines"])
                   + "  (flat, level, legible, spelled exactly)")
    if rec.get("closure"):
        out.append(f"  closure       : {rec['closure']}")
    if rec.get("material"):
        out.append(f"  material      : {rec['material']}")
    if rec.get("colour"):
        out.append(f"  colour        : {rec['colour']}")
    if rec.get("must"):
        out.append("  must appear   : " + "; ".join(rec["must"]))
    if rec.get("forbid"):
        out.append("  never         : " + "; ".join(rec["forbid"]))
    if rec.get("lighting"):
        out.append(f"  lighting      : {rec['lighting']}")
    if rec.get("prompt_lock"):
        out.append(f"  verbatim      : {rec['prompt_lock']}")
    if rec.get("seed") is not None:
        out.append(f"  seed          : {rec['seed']}")
    return out


def _character_lock_lines(rec: dict) -> list[str]:
    plate = [r.get("stored") or r["source"] for r in rec.get("refs", [])]
    out = [f"CHARACTER LOCK — {rec['name']}"]
    if plate:
        out.append(f"  plates        : {', '.join(plate)}")
    for key, label in (("wardrobe", "wardrobe      "), ("lighting", "lighting      "),
                       ("prompt_lock", "verbatim      ")):
        if rec.get(key):
            out.append(f"  {label}: {rec[key]}")
    if rec.get("seed") is not None:
        out.append(f"  seed          : {rec['seed']}")
    out.append("  generate from the plates, never from a frame of the last video")
    return out


def cmd_product(args) -> dict:
    data, _ = need_campaign(args.campaign)
    pr = data["products"].get(args.name)
    if not pr:
        return {"error": f"no product named {args.name!r}",
                "known": list(data["products"])}
    return {
        "product": pr["name"],
        "use_these_refs": [r.get("stored") or r["source"] for r in pr["refs"]],
        "lock_card": "\n".join(_lock_lines(pr)),
        "identity_gaps": _product_gaps(pr) or None,
        "seed": pr.get("seed"),
        "reminder": "Keep clips 3-5s. Verify each clip against the plate, not against "
                    "the previous clip.",
    }


def cmd_lockcard(args) -> dict:
    """Print the block that goes into every shot prompt and every packet page."""
    data, _ = need_campaign(args.campaign)
    blocks: list[str] = []
    unknown: list[str] = []

    prods = args.product or ([] if args.character else list(data["products"]))
    chars = args.character or ([] if args.product else list(data["characters"]))

    for name in prods:
        rec = data["products"].get(name)
        if rec:
            blocks.append("\n".join(_lock_lines(rec)))
        else:
            unknown.append(name)
    for name in chars:
        rec = data["characters"].get(name)
        if rec:
            blocks.append("\n".join(_character_lock_lines(rec)))
        else:
            unknown.append(name)

    card = "\n\n".join(blocks)
    if args.text:
        print(card)
        return {}
    return {
        "campaign": data["name"],
        "lock_card": card or None,
        "unknown": unknown or None,
        "paste_into": ["every shot prompt that contains this thing",
                       "every page of the generation packet",
                       "the review of every clip"],
        "law": "Each thing is described in words exactly once. A product never — it "
               "comes from its plate. This card exists so the plate is not forgotten, "
               "not so the object can be re-described.",
    }


VERIFY_FIELDS = [
    ("plate_used", "was this frame generated FROM the plate, not from words or from "
                   "the previous clip?"),
    ("silhouette", "same shape and proportions as the plate?"),
    ("label", "wording, line order and spelling identical to the plate?"),
    ("logo", "present, undistorted, correct position?"),
    ("closure", "cap/lid/closure as specified, unless the shot note says in-use?"),
    ("colour", "product's own colour and finish, not shifted by the grade?"),
    ("must_appear", "every locked feature visible or deliberately out of frame?"),
    ("forbidden", "nothing from the never-list present?"),
    ("reserved_zone", "the caption area stayed dark and empty?"),
    ("continuity", "light direction and time of day match the adjacent shots?"),
]


def cmd_verify(args) -> dict:
    """Emit the per-clip product check as fields that must be filled in.

    A question with no field gets skipped; a field with no verdict is visible.
    That is the whole point: 'is the product still the product' was never
    answered because nothing recorded that it had been asked.
    """
    data, _ = need_campaign(args.campaign)
    pr = data["products"].get(args.product) if args.product else None
    if args.product and not pr:
        return {"error": f"no product named {args.product!r}",
                "known": list(data["products"])}

    checks = []
    for key, question in VERIFY_FIELDS:
        item = {"field": key, "question": question, "verdict": "UNCHECKED"}
        if pr:
            if key == "label" and pr.get("label_lines"):
                item["expected"] = " / ".join(pr["label_lines"])
            if key == "closure" and pr.get("closure"):
                item["expected"] = pr["closure"]
            if key == "colour" and pr.get("colour"):
                item["expected"] = pr["colour"]
            if key == "must_appear" and pr.get("must"):
                item["expected"] = pr["must"]
            if key == "forbidden" and pr.get("forbid"):
                item["expected"] = pr["forbid"]
        checks.append(item)

    return {
        "shot": args.shot or None,
        "product": args.product or None,
        "checks": checks,
        "rule": "Any FAIL means regenerate, not ship. Flag the credit cost of the "
                "retry before running it.",
        "note": "Colour statistics cannot see any of this. Look at the frame, "
                "side by side with the plate — scripts/identity.py sheet builds that "
                "comparison image for you.",
    }


def cmd_register(args) -> dict:
    data, path = need_campaign(args.campaign)
    vid = args.variant

    v = data["variants"].setdefault(vid, {
        "id": vid, "created": now(), "hook": "", "register": "",
        "length": None, "claim": "", "files": [],
    })
    for field, val in (("hook", args.hook), ("register", args.register),
                       ("claim", args.claim)):
        if val:
            v[field] = val
    if args.length:
        v["length"] = args.length
    if args.file and args.file not in v["files"]:
        v["files"].append(args.file)

    # Duplicate guard
    dupes = [p for p in data["placements"]
             if p["variant"] == vid and p["account"] == args.account]
    if dupes and not args.force:
        return {
            "blocked": True,
            "reason": f"variant {vid!r} is already registered on account "
                      f"{args.account!r} ({dupes[0]['registered']})",
            "advice": "Use a different variant, or --force if this is a deliberate repost.",
        }

    other = [p["account"] for p in data["placements"] if p["variant"] == vid]
    data["placements"].append({
        "variant": vid, "account": args.account,
        "platform": args.platform or "", "file": args.file or "",
        "registered": now(), "scheduled": args.scheduled or "",
    })
    save(data, path)

    out: dict[str, Any] = {
        "registered": {"variant": vid, "account": args.account,
                       "platform": args.platform or None},
        "variant_also_on": other,
    }
    if other:
        out["caution"] = (
            f"Variant {vid!r} is now on {len(other) + 1} accounts "
            f"({', '.join(other + [args.account])}). If those audiences overlap, "
            "it reads as spam. Prefer a distinct hook per account."
        )
    return out


def cmd_check(args) -> dict:
    data, _ = need_campaign(args.campaign)
    mine = [p for p in data["placements"] if p["account"] == args.account]
    used = {p["variant"] for p in mine}
    all_v = set(data["variants"])
    detail = []
    for p in sorted(mine, key=lambda x: x["registered"], reverse=True):
        v = data["variants"].get(p["variant"], {})
        detail.append({
            "variant": p["variant"], "platform": p.get("platform") or None,
            "registered": p["registered"],
            "hook": v.get("hook") or None, "register": v.get("register") or None,
        })
    return {
        "account": args.account,
        "count": len(mine),
        "history": detail,
        "unused_variants": sorted(all_v - used),
        "registers_used": sorted({d["register"] for d in detail if d["register"]}),
    }


def cmd_next(args) -> dict:
    data, _ = need_campaign(args.campaign)
    used = {p["variant"] for p in data["placements"] if p["account"] == args.account}
    candidates = []
    for vid, v in data["variants"].items():
        if vid in used:
            continue
        elsewhere = sum(1 for p in data["placements"] if p["variant"] == vid)
        candidates.append({
            "variant": vid, "hook": v.get("hook") or None,
            "register": v.get("register") or None,
            "used_on_other_accounts": elsewhere,
            "files": v.get("files", []),
        })
    candidates.sort(key=lambda c: c["used_on_other_accounts"])
    return {
        "account": args.account,
        "recommended": candidates[0] if candidates else None,
        "options": candidates,
        "note": None if candidates else
        "Every variant has been used on this account. Produce a new variant — "
        "changing the hook is the highest-leverage change.",
    }


def cmd_variants(args) -> dict:
    data, _ = need_campaign(args.campaign)
    out = []
    for vid, v in data["variants"].items():
        places = [{"account": p["account"], "platform": p.get("platform") or None}
                  for p in data["placements"] if p["variant"] == vid]
        out.append({
            "id": vid, "hook": v.get("hook") or None,
            "register": v.get("register") or None, "length": v.get("length"),
            "claim": v.get("claim") or None,
            "files": v.get("files", []), "placements": places,
        })
    return {"campaign": data["name"], "variants": out}


def cmd_status(args) -> dict:
    data, _ = need_campaign(args.campaign)
    accounts: dict[str, int] = {}
    for p in data["placements"]:
        accounts[p["account"]] = accounts.get(p["account"], 0) + 1
    chars = []
    for name, c in data["characters"].items():
        ok = sum(1 for r in c["refs"] if "stored" in r)
        chars.append({"name": name, "stored_refs": ok,
                      "missing_refs": len(c["refs"]) - ok})
    prods = []
    for name, pr in data["products"].items():
        ok = sum(1 for r in pr["refs"] if "stored" in r)
        prods.append({"name": name, "category": pr.get("category") or None,
                      "stored_refs": ok,
                      "warning": None if ok else "no real photo — product will be invented"})
    return {
        "campaign": data["name"],
        "brand": data.get("brand") or None,
        "created": data.get("created"),
        "characters": chars,
        "products": prods,
        "variant_count": len(data["variants"]),
        "placements_by_account": accounts,
        "total_placements": len(data["placements"]),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="campaign.py",
        description="Campaign registry: variants, consistency assets, per-account "
                    "assignment.",
    )
    ap.add_argument("--campaign", help="campaign name (defaults to the active one)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create or activate a campaign")
    s.add_argument("--name", required=True)
    s.add_argument("--brand", default="")
    s.add_argument("--force", action="store_true", help="reset if it exists")

    s = sub.add_parser("add-character", help="store canonical character references")
    s.add_argument("--name", required=True)
    s.add_argument("--refs", nargs="+", required=True)
    s.add_argument("--wardrobe", default="", help="exact wardrobe wording to reuse")
    s.add_argument("--lighting", default="", help="exact lighting wording to reuse")
    s.add_argument("--prompt-lock", default="", help="any other wording to repeat verbatim")
    s.add_argument("--seed", type=int)
    s.add_argument("--platform", default="")
    s.add_argument("--model", default="")

    s = sub.add_parser("character", help="show a character's refs and prompt lock")
    s.add_argument("--name", required=True)

    s = sub.add_parser("add-product",
                       help="store the product plate AND its identity lock")
    s.add_argument("--name", required=True)
    s.add_argument("--refs", nargs="+", required=True,
                   help="real photographs of the product. These are the product.")
    s.add_argument("--profile", default="",
                   help="pack | food | vehicle | space | apparel | device | screen | "
                        "service | person. See `campaign.py profiles`.")
    s.add_argument("--category", default="", help="art-direction category, e.g. "
                                                  "glossy-packaging, food")
    s.add_argument("--identity", default="",
                   help="one sentence: what makes a buyer recognise THIS object")
    s.add_argument("--label-lines", nargs="+", default=[], dest="label_lines",
                   help="exact type on the pack, in order, top line first")
    s.add_argument("--closure", default="",
                   help="cap/lid state, e.g. 'silver cap on unless the shot is in-use'")
    s.add_argument("--colour", default="", help="the product's own colour and finish")
    s.add_argument("--material", default="", help="glass, matte plastic, brushed steel…")
    s.add_argument("--must", nargs="+", default=[],
                   help="features that must be visible in a product shot")
    s.add_argument("--forbid", nargs="+", default=[],
                   help="things that must never appear: wrong variant, extra bottles…")
    s.add_argument("--lighting", default="")
    s.add_argument("--prompt-lock", default="", dest="prompt_lock",
                   help="wording to repeat verbatim in every prompt")
    s.add_argument("--seed", type=int)
    s.add_argument("--platform", default="")
    s.add_argument("--model", default="")

    s = sub.add_parser("product", help="show a product's plate, lock card and gaps")
    s.add_argument("--name", required=True)

    sub.add_parser("profiles", help="product families and what identity means for each")

    s = sub.add_parser("lockcard",
                       help="the block to paste into every prompt and packet page")
    s.add_argument("--product", nargs="+", help="default: every product")
    s.add_argument("--character", nargs="+", help="default: every character")
    s.add_argument("--text", action="store_true", help="plain text instead of JSON")

    s = sub.add_parser("verify", help="per-clip product check, as fields to fill in")
    s.add_argument("--product")
    s.add_argument("--shot", help="shot id this check belongs to")

    s = sub.add_parser("register", help="record a variant going to an account")
    s.add_argument("--variant", required=True)
    s.add_argument("--account", required=True)
    s.add_argument("--platform", default="")
    s.add_argument("--file", default="")
    s.add_argument("--hook", default="")
    s.add_argument("--register", default="", help="free text; ugc | humour | commercial | "
                                                  "arthouse | process | mockumentary | "
                                                  "retro | sensory | graphic | absurdist")
    s.add_argument("--claim", default="")
    s.add_argument("--length", type=float)
    s.add_argument("--scheduled", default="")
    s.add_argument("--force", action="store_true", help="allow a deliberate repost")

    s = sub.add_parser("check", help="what has an account already had?")
    s.add_argument("--account", required=True)

    s = sub.add_parser("next", help="unused variants for an account")
    s.add_argument("--account", required=True)

    sub.add_parser("variants", help="all variants and their placements")
    sub.add_parser("status", help="campaign overview")

    args = ap.parse_args(argv)

    handlers = {
        "init": cmd_init, "add-character": cmd_add_character, "character": cmd_character,
        "add-product": cmd_add_product, "product": cmd_product,
        "profiles": cmd_profiles, "lockcard": cmd_lockcard, "verify": cmd_verify,
        "register": cmd_register, "check": cmd_check,
        "next": cmd_next, "variants": cmd_variants, "status": cmd_status,
    }
    result = handlers[args.cmd](args)
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if isinstance(result, dict) and ("error" in result or "blocked" in result) else 0


if __name__ == "__main__":
    sys.exit(main())
