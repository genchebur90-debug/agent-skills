#!/usr/bin/env python3
"""
packet.py — build a copy-paste generation packet for manual production.

This is the workhorse of HYBRID mode, which is the common case: most consumer AI
subscriptions have no API, so the agent does the creative work and the human
clicks Generate. The packet must therefore be genuinely paste-ready — platform,
account, exact prompt, exact settings, exact output filename.

Usage:
    packet.py --plan plan.json --out packet.md
    packet.py --plan plan.json --out packet.md --routing routing.json
    packet.py --plan plan.json --stdout          # for TEXT mode / chat delivery

plan.json schema. `id` and `prompt` are required; `locks` and `parents` are
required as soon as the shot contains something that must stay identical, and
planlint.py enforces that before this script will build anything:
{
  "project":  "shampoo-summer",
  "register": "ugc",
  "master":   {"aspect": "9:16", "fps": 30},
  "shots": [
    {
      "id": "s1",
      "note": "hero bottle, highlight travels across label",
      "need": "image-to-video",
      "prompt": "Amber glass shampoo bottle, three-quarter angle, ...",
      "negative": "no extra bottles, no text overlay",
      "seconds": 5,
      "aspect": "9:16",
      "locks":   ["product:shampoo-500"],
      "parents": ["plates/s1_first_frame.png", "assets/bottle_real.jpg"],
      "platform": "google-flow",
      "account": 3,
      "audio": "none"
    }
  ]
}

Older spellings of parents (`reference`, `references`, `reference_images`) still
load: every script reads the plan through planlint.normalize_plan, so a plate
attached in one script can no longer be dropped by the next.

If a shot has no platform, packet.py asks fleet.py for the recommendation and
marks it as unconfirmed — a reminder that the Routing Gate still owes an answer.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import planlint  # noqa: E402  — same directory, stdlib only

try:
    import campaign as campaign_mod  # noqa: E402  — for lock cards
except Exception:                     # pragma: no cover - campaign is optional
    campaign_mod = None


def lock_cards(shot: dict, camp: dict) -> list[str]:
    """The identity block for everything this shot has locked.

    A packet page used to carry the prompt and nothing about what the object
    actually is, so the human generating it had no way to tell a correct
    flacon from a plausible one. The card travels with the shot now.
    """
    if not (camp and campaign_mod):
        return []
    out = []
    for lock in planlint.normalize_shot(shot).get("locks", []):
        kind, name = planlint.lock_kind(lock)
        rec = None
        if kind in ("product", "thing"):
            rec = (camp.get("products") or {}).get(name)
            if rec:
                out.append("\n".join(campaign_mod._lock_lines(rec)))
                continue
        if kind in ("character", "person", "thing"):
            rec = (camp.get("characters") or {}).get(name)
            if rec:
                out.append("\n".join(campaign_mod._character_lock_lines(rec)))
    return out


# ---------------------------------------------------------------------------
# Fleet lookup (optional — packet works standalone)
# ---------------------------------------------------------------------------

def fleet_json(*args: str) -> dict:
    """Call fleet.py and return parsed JSON, or {} if unavailable."""
    script = HERE / "fleet.py"
    if not script.is_file():
        return {}
    try:
        r = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0 and not r.stdout.strip():
            return {}
        return json.loads(r.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return {}


def platform_info(fleet_detect: dict) -> dict[str, dict]:
    return {p["id"]: p for p in fleet_detect.get("platforms", [])}


# ---------------------------------------------------------------------------
# Packet rendering
# ---------------------------------------------------------------------------

def _fmt_settings(shot: dict, master: dict) -> list[tuple[str, str]]:
    rows = []
    aspect = shot.get("aspect") or master.get("aspect") or "9:16"
    rows.append(("Aspect ratio", str(aspect)))
    if shot.get("seconds"):
        rows.append(("Duration", f"{shot['seconds']}s"))
    if shot.get("resolution") or master.get("resolution"):
        rows.append(("Resolution", str(shot.get("resolution") or master["resolution"])))
    audio = shot.get("audio")
    if audio is not None:
        rows.append(("Audio", "none — silent clip" if audio in ("none", False, "")
                     else str(audio)))
    if shot.get("reference"):
        rows.append(("Reference image", str(shot["reference"])))
        rows.append(("Mode", "image-to-video (attach the reference as first frame)"))
    if shot.get("last_frame"):
        rows.append(("Last frame", str(shot["last_frame"])))
    if shot.get("model"):
        rows.append(("Model", str(shot["model"])))
    if shot.get("seed") is not None:
        rows.append(("Seed", str(shot["seed"])))
    return rows


def render(plan: dict, pinfo: dict[str, dict], detect: dict,
           camp: dict | None = None) -> str:
    project = plan.get("project") or "untitled"
    register = plan.get("register") or ""
    master = plan.get("master") or {}
    shots = plan.get("shots") or []
    camp = camp or {}

    L: list[str] = []
    add = L.append

    add(f"# Generation packet — {project}")
    add("")
    add(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        + (f" · register: **{register}**" if register else ""))
    add("")
    add("Generate each shot below in the platform named, then save the file with the "
        "**exact filename given**. The director picks them up from `inbox/` by that "
        "name, so renaming breaks assembly.")
    add("")

    # ---- how to use ----
    add("## How to use this")
    add("")
    add("1. Create an `inbox/` folder next to your project if it doesn't exist.")
    add("2. Work through the shots in order — earlier shots are often references for later ones.")
    add("3. For each: open the platform, select the account named, paste the prompt, "
        "set the listed options, generate, download.")
    add("4. Save as `inbox/<filename>` exactly as specified.")
    add("5. Tell the director when done. It will match files, assemble, review and export.")
    add("")
    add("If a generation comes out wrong, regenerate it before moving on — a bad shot "
        "costs more to work around later than to redo now.")
    add("")

    # ---- account plan ----
    by_platform: dict[str, list[dict]] = {}
    for s in shots:
        by_platform.setdefault(str(s.get("platform") or "unassigned"), []).append(s)

    add("## Where each shot goes")
    add("")
    add("| Shot | Platform | Account | Duration | What it is |")
    add("|---|---|---|---|---|")
    for s in shots:
        pid = str(s.get("platform") or "—")
        label = pinfo.get(pid, {}).get("label", pid)
        acct = s.get("account")
        acct_s = f"#{acct}" if acct else "any"
        secs = f"{s['seconds']}s" if s.get("seconds") else "—"
        note = str(s.get("note") or "")[:48]
        flag = "" if s.get("platform") else " ⚠️"
        add(f"| `{s.get('id','?')}` | {label}{flag} | {acct_s} | {secs} | {note} |")
    add("")
    if any(not s.get("platform") for s in shots):
        add("⚠️ Shots without a platform still need a routing decision — see the "
            "Routing Gate before generating them.")
        add("")

    # ---- credit note ----
    paid = [pid for pid in by_platform
            if pinfo.get(pid, {}).get("marker") == "TOP-UP NEEDED"]
    if paid:
        add("### Cost note")
        add("")
        for pid in paid:
            p = pinfo[pid]
            add(f"- **{p['label']}** — {p.get('cost_warning', 'requires separate purchase')}")
        add("")
        add("Nothing here is charged automatically. These are the platforms where "
            "generating means spending new money.")
        add("")

    # ---- the shots ----
    add("---")
    add("")
    add("## Shots")
    add("")

    for i, s in enumerate(shots, 1):
        sid = str(s.get("id") or f"s{i}")
        pid = str(s.get("platform") or "unassigned")
        p = pinfo.get(pid, {})
        label = p.get("label", pid)
        acct = s.get("account")
        filename = s.get("filename") or f"{sid}.mp4"

        add(f"### {i}. `{sid}` — {s.get('note') or 'shot'}")
        add("")
        head = f"**Platform:** {label}"
        if acct:
            head += f" · **Account:** #{acct}"
        if p.get("marker"):
            head += f" · _{p['marker']}_"
        add(head)
        if p.get("url"):
            add(f"**Open:** {p['url']}")
        add("")

        add("**Prompt** — copy everything in the block:")
        add("")
        add("```text")
        add(str(s.get("prompt", "")).strip())
        add("```")
        add("")

        if s.get("negative"):
            add("**Negative / avoid:**")
            add("")
            add("```text")
            add(str(s["negative"]).strip())
            add("```")
            add("")

        rows = _fmt_settings(s, master)
        if rows:
            add("**Settings:**")
            add("")
            for k, v in rows:
                add(f"- {k}: `{v}`")
            add("")

        parents = planlint.normalize_shot(s).get("parents", [])
        if parents:
            add("**Attach these, in order** — they are what keeps the product and the "
                "cast identical across shots. A prompt without them is a different "
                "object that merely sounds the same:")
            add("")
            for i, ref in enumerate(parents, 1):
                add(f"- `@Image{i}` → `{ref}`")
            add("")
        elif s.get("locks") or s.get("locked"):
            add("> **STOP.** This shot has locked things and no plate attached. Do not "
                "generate it — send it back to the director to build the plate first.")
            add("")

        for card in lock_cards(s, camp):
            add("<details><summary>What this thing must look like (lock card)</summary>")
            add("")
            add("```text")
            add(card)
            add("```")
            add("")
            add("</details>")
            add("")

        add(f"**Save as:** `inbox/{filename}`")
        add("")

        if p.get("manual_steps"):
            add("<details><summary>Step-by-step for this platform</summary>")
            add("")
            for step in p["manual_steps"]:
                add(f"1. {step}")
            add("")
            add("</details>")
            add("")

        add("---")
        add("")

    # ---- checklist ----
    add("## Before you hand it back")
    add("")
    add("Quick check on each clip — catching these now saves a regeneration later:")
    add("")
    add("- [ ] The product looks like **your** product — open the plate and the clip "
        "side by side, compare label, logo, closure, colour, proportions")
    add("- [ ] No warped text or garbled logo")
    add("- [ ] Hands and faces survive a close look (count fingers)")
    add("- [ ] Physics behave — liquid falls, fabric drapes, nothing floats")
    add("- [ ] Any area you reserved for captions stayed clear")
    add("- [ ] Filenames match exactly what's specified above")
    add("")
    add(f"All files in `inbox/`: {', '.join(sorted(str(s.get('filename') or str(s.get('id','?'))+'.mp4') for s in shots))}")
    add("")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="packet.py",
        description="Build a copy-paste generation packet for manual production.",
    )
    ap.add_argument("--plan", required=True, help="path to plan.json")
    ap.add_argument("--out", help="write packet markdown here")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    ap.add_argument("--inbox", default="inbox", help="expected drop folder (default: inbox)")
    ap.add_argument("--campaign", help="campaign name for lock cards (default: active)")
    ap.add_argument("--force", action="store_true",
                    help="build the packet even though planlint found errors. "
                         "Every use of this is a decision to ship known drift.")
    ap.add_argument("--skip-lint", action="store_true",
                    help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    src = Path(args.plan)
    if not src.is_file():
        print(json.dumps({"error": f"plan not found: {src}"}, indent=2))
        return 1
    try:
        plan = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON: {e}"}, indent=2))
        return 1
    if not isinstance(plan, dict) or not plan.get("shots"):
        print(json.dumps({"error": "plan must be an object with a non-empty 'shots' list"},
                         indent=2))
        return 1

    # ---- the gate -------------------------------------------------------
    # A packet is the moment a mistake becomes someone's afternoon: the human
    # generates twelve clips from it before anyone looks. Lint first.
    camp = planlint.load_campaign(args.campaign)
    if not args.skip_lint:
        report = planlint.lint(plan, camp)
        if not report["ok"]:
            print(planlint.render(report), file=sys.stderr)
            if not args.force:
                print(json.dumps({
                    "blocked": "plan has errors that guarantee drift",
                    "errors": len(report["errors"]),
                    "fix_then_rerun": "python3 scripts/planlint.py --plan "
                                      f"{args.plan}",
                    "override": "add --force only if you accept the listed failures",
                }, indent=2))
                return 1
            print("proceeding under --force despite the errors above\n", file=sys.stderr)
        elif report["warnings"]:
            print(planlint.render(report), file=sys.stderr)

    detect = fleet_json("detect")
    pinfo = platform_info(detect)

    # Fill missing platforms from fleet recommendations, flagged as unconfirmed.
    unassigned = [s for s in plan["shots"] if isinstance(s, dict) and not s.get("platform")]
    suggestions: list[dict] = []
    if unassigned:
        needs = {"shots": [
            {"id": s.get("id"), "need": s.get("need", "video"),
             "best_for": s.get("best_for", []), "seconds": s.get("seconds")}
            for s in unassigned
        ]}
        tmp = Path(".packet-needs.tmp.json")
        try:
            tmp.write_text(json.dumps(needs), encoding="utf-8")
            routed = fleet_json("plan", "--needs", str(tmp))
        finally:
            tmp.unlink(missing_ok=True)
        rec = {r["shot"]: r for r in routed.get("shots", [])}
        for s in unassigned:
            r = rec.get(s.get("id"))
            if r:
                suggestions.append({
                    "shot": s.get("id"),
                    "suggested_platform": r.get("recommended"),
                    "options": [o["platform"] for o in r.get("options", [])],
                })

    md = render(plan, pinfo, detect, camp)

    inbox = Path(args.inbox)
    created_inbox = False
    if not args.stdout and not inbox.exists():
        try:
            inbox.mkdir(parents=True, exist_ok=True)
            created_inbox = True
        except OSError:
            pass

    if args.stdout or not args.out:
        print(md)
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")

    result: dict[str, Any] = {
        "packet": str(out),
        "shots": len(plan["shots"]),
        "inbox": str(inbox),
        "inbox_created": created_inbox,
        "mode": detect.get("mode"),
        "expected_files": [
            f"{inbox}/{s.get('filename') or str(s.get('id','shot'))+'.mp4'}"
            for s in plan["shots"] if isinstance(s, dict)
        ],
    }
    if suggestions:
        result["unrouted_shots"] = suggestions
        result["gate_reminder"] = (
            "These shots had no platform assigned. Present the options to the user "
            "and get an explicit choice before they generate."
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
