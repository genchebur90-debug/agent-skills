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
    campaign.py add-product --name shampoo-500 --refs bottle.jpg
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


def cmd_add_product(args) -> dict:
    data, path = need_campaign(args.campaign)
    refs = store_refs(data["name"], "products", args.name, args.refs)
    data["products"][args.name] = {
        "name": args.name,
        "refs": refs,
        "category": args.category or "",
        "lighting": args.lighting or "",
        "added": now(),
    }
    save(data, path)
    real = [r for r in refs if "stored" in r]
    return {
        "product": args.name,
        "stored_refs": [r["stored"] for r in real],
        "missing": [r["source"] for r in refs if "error" in r],
        "warning": None if real else (
            "No real product photo stored. Without one the model will invent a "
            "product that is not the user's — the label will be wrong. Ask for photos."
        ),
        "rule": "Generate product shots image-to-video from these refs, not text-to-video.",
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

    s = sub.add_parser("add-product", help="store canonical product references")
    s.add_argument("--name", required=True)
    s.add_argument("--refs", nargs="+", required=True)
    s.add_argument("--category", default="", help="e.g. glossy-packaging, food")
    s.add_argument("--lighting", default="")

    s = sub.add_parser("register", help="record a variant going to an account")
    s.add_argument("--variant", required=True)
    s.add_argument("--account", required=True)
    s.add_argument("--platform", default="")
    s.add_argument("--file", default="")
    s.add_argument("--hook", default="")
    s.add_argument("--register", default="", help="ugc | humour | commercial | arthouse")
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
        "add-product": cmd_add_product, "register": cmd_register, "check": cmd_check,
        "next": cmd_next, "variants": cmd_variants, "status": cmd_status,
    }
    result = handlers[args.cmd](args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if isinstance(result, dict) and ("error" in result or "blocked" in result) else 0


if __name__ == "__main__":
    sys.exit(main())
