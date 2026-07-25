#!/usr/bin/env python3
"""
fleet.py — read the user's generation fleet, detect operating mode, and route
shots to platforms WITHOUT ever spending money silently.

Core promise: this script never generates anything. It only reports what is
possible, what it would cost, and what needs the user's approval first.

Usage:
    fleet.py detect                       operating mode + usable platforms
    fleet.py budget                       remaining credits per account
    fleet.py plan --needs plan.json       routing options per shot, grouped by cost
    fleet.py pick --need video --best-for physical-realism
    fleet.py spend --platform magica --account 1 --amount 1200
    fleet.py accounts --platform magica   next account in rotation

Config: fleet.yaml (or fleet.example.yaml as fallback) in the skill root.
State:  .fleet-state.json next to the config (spend log, rotation cursor).

No third-party dependencies. PyYAML is used when present; otherwise a small
built-in parser handles the subset of YAML this config needs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Access types, and what each means for spending
# ---------------------------------------------------------------------------

ACCESS_API = "api"            # agent can call it; credits already owned
ACCESS_UI = "ui"              # human generates in browser; credits already owned
ACCESS_API_PAID = "api-paid"  # agent could call it, but credits must be bought
ACCESS_OFF = "off"

# Marker vocabulary shared with SKILL.md §3 so the agent's output stays consistent.
MARKERS = {
    ACCESS_API: ("INCLUDED", "Runs on credits you already have. No new spend."),
    ACCESS_UI: ("MANUAL", "Your subscription covers it, but there's no API — "
                          "you generate in the browser and drop the file in inbox/."),
    ACCESS_API_PAID: ("TOP-UP NEEDED", "Requires buying credits separately. "
                                       "Verify current pricing before agreeing."),
}


# ---------------------------------------------------------------------------
# Minimal YAML subset parser (fallback when PyYAML is absent)
# ---------------------------------------------------------------------------

def _coerce(raw: str) -> Any:
    """Turn a scalar string into bool / int / float / None / str."""
    v = raw.strip()
    if not v:
        return ""
    # strip inline comment when not inside quotes
    if not (v.startswith(('"', "'"))):
        hash_pos = v.find(" #")
        if hash_pos != -1:
            v = v[:hash_pos].strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    low = v.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off") and low != "off":
        return False
    if low in ("null", "~", ""):
        return None
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_coerce(p) for p in _split_flow(inner)]
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d*\.\d+", v):
        return float(v)
    return v


def _split_flow(s: str) -> list[str]:
    """Split a flow-style list body on commas outside quotes."""
    parts, buf, quote = [], [], None
    for ch in s:
        if quote:
            if ch == quote:
                quote = None
            buf.append(ch)
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p for p in (p.strip() for p in parts) if p]


def _tiny_yaml(text: str) -> dict:
    """
    Parse the YAML subset used by fleet.yaml: nested maps, dash lists of maps,
    dash lists of scalars, flow lists, block scalars (> and |), comments.
    """
    root: dict = {}
    # stack of (indent, container). container is dict or list.
    stack: list[tuple[int, Any]] = [(-1, root)]
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()

        # close deeper scopes
        while stack and indent <= stack[-1][0] and len(stack) > 1:
            stack.pop()
        parent = stack[-1][1]

        # ---- list item ----
        if line.startswith("- "):
            item_body = line[2:].strip()
            if not isinstance(parent, list):
                continue
            if ":" in item_body and not item_body.startswith(("\"", "'")):
                # dash-started map: create dict, seed first key
                d: dict = {}
                parent.append(d)
                stack.append((indent, d))
                k, _, v = item_body.partition(":")
                k, v = k.strip(), v.strip()
                if v in (">", "|", ">-", "|-"):
                    block, i = _read_block(lines, i, indent + 2)
                    d[k] = block
                elif v == "":
                    stack.append((indent + 1, _new_child(d, k, lines, i)))
                else:
                    d[k] = _coerce(v)
            else:
                parent.append(_coerce(item_body))
            continue

        # ---- key: value ----
        if ":" in line:
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if not isinstance(parent, dict):
                continue
            if v in (">", "|", ">-", "|-"):
                block, i = _read_block(lines, i, indent + 2)
                parent[k] = block
            elif v == "":
                child = _new_child(parent, k, lines, i)
                stack.append((indent, child))
            else:
                parent[k] = _coerce(v)

    return root


def _new_child(parent: dict, key: str, lines: list[str], idx: int) -> Any:
    """Decide whether an empty-valued key opens a list or a map."""
    for j in range(idx, len(lines)):
        s = lines[j]
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        child: Any = [] if s.lstrip().startswith("- ") else {}
        parent[key] = child
        return child
    parent[key] = {}
    return parent[key]


def _read_block(lines: list[str], idx: int, min_indent: int) -> tuple[str, int]:
    """Consume an indented block scalar, returning joined text and new index."""
    out: list[str] = []
    while idx < len(lines):
        s = lines[idx]
        if s.strip() and (len(s) - len(s.lstrip())) < min_indent:
            break
        out.append(s.strip())
        idx += 1
    return " ".join(p for p in out if p).strip(), idx


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except ImportError:
        return _tiny_yaml(text)


# ---------------------------------------------------------------------------
# Config and state
# ---------------------------------------------------------------------------

def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_config() -> tuple[Path | None, bool]:
    """Return (path, is_example). Prefers a real fleet.yaml."""
    root = skill_root()
    for name in ("fleet.yaml", "fleet.yml"):
        for base in (Path.cwd(), root):
            p = base / name
            if p.is_file():
                return p, False
    ex = root / "fleet.example.yaml"
    return (ex, True) if ex.is_file() else (None, False)


def state_path() -> Path:
    cfg, _ = find_config()
    return (cfg.parent if cfg else skill_root()) / ".fleet-state.json"


def load_state() -> dict:
    p = state_path()
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"spend": {}, "rotation": {}}


def save_state(st: dict) -> None:
    state_path().write_text(json.dumps(st, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fleet model
# ---------------------------------------------------------------------------

class Platform:
    def __init__(self, raw: dict):
        self.raw = raw
        self.id = str(raw.get("id", "unknown"))
        self.label = str(raw.get("label", self.id))
        self.access = str(raw.get("access", ACCESS_OFF)).strip().lower()
        self.priority = int(raw.get("priority", 99) or 99)
        self.accounts = int(raw.get("accounts", 1) or 1)
        self.budget_per_account = raw.get("budget_per_account")
        self.unit = str(raw.get("unit", "credits"))
        self.can = _as_list(raw.get("can"))
        self.best_for = _as_list(raw.get("best_for"))
        self.weak_at = _as_list(raw.get("weak_at"))
        self.notes = str(raw.get("notes", "") or "")
        self.url = str(raw.get("url", "") or "")
        self.max_clip_seconds = raw.get("max_clip_seconds")

        api = raw.get("api") if isinstance(raw.get("api"), dict) else {}
        self.api = api
        self.auth_env = str(raw.get("auth_env") or api.get("auth_env") or "")
        self.auth_env_pattern = str(raw.get("auth_env_pattern") or "")
        self.endpoint = str(raw.get("endpoint") or api.get("endpoint") or "")
        self.separate_purchase = bool(
            raw.get("separate_purchase") or api.get("separate_purchase")
        )
        self.est_cost_note = str(
            raw.get("est_cost_note") or api.get("est_cost_note") or ""
        )
        mw = raw.get("manual_workflow")
        self.manual_steps = _as_list(mw.get("steps")) if isinstance(mw, dict) else []

    # -- credentials -------------------------------------------------------

    def keys_present(self) -> list[str]:
        """Which auth env vars are actually set."""
        found = []
        if self.auth_env and os.environ.get(self.auth_env):
            found.append(self.auth_env)
        if self.auth_env_pattern:
            for n in range(1, self.accounts + 1):
                name = self.auth_env_pattern.replace("{n}", str(n))
                if os.environ.get(name):
                    found.append(name)
        return found

    def effective_access(self) -> str:
        """
        Resolve declared access against reality.
        A platform declared `api` with no key present cannot be called.
        """
        if self.access == ACCESS_OFF:
            return ACCESS_OFF
        if self.access == ACCESS_API:
            return ACCESS_API if self.keys_present() else ACCESS_UI
        if self.access == ACCESS_API_PAID:
            # Key present means credits were probably bought; still flag as paid
            # so the agent warns, per Rule 2.
            return ACCESS_API_PAID
        return ACCESS_UI

    def marker(self) -> tuple[str, str]:
        return MARKERS.get(self.effective_access(), ("UNAVAILABLE", "Not usable."))

    # -- capability --------------------------------------------------------

    def supports(self, need: str) -> bool:
        if not need:
            return True
        need = need.strip().lower()
        return any(need == c.lower() or need in c.lower() for c in self.can)

    def strength_score(self, best_for: list[str]) -> int:
        if not best_for:
            return 0
        bf = [b.lower() for b in self.best_for]
        wk = [w.lower() for w in self.weak_at]
        score = 0
        for want in best_for:
            w = want.strip().lower()
            if any(w == b or w in b or b in w for b in bf):
                score += 2
            if any(w == x or w in x or x in w for x in wk):
                score -= 3
        return score

    # -- budget ------------------------------------------------------------

    def spent(self, st: dict, account: int | None = None) -> float:
        rec = st.get("spend", {}).get(self.id, {})
        if account is None:
            return float(sum(rec.values())) if rec else 0.0
        return float(rec.get(str(account), 0))

    def remaining(self, st: dict, account: int) -> float | None:
        if self.budget_per_account in (None, ""):
            return None
        return float(self.budget_per_account) - self.spent(st, account)

    def total_remaining(self, st: dict) -> float | None:
        if self.budget_per_account in (None, ""):
            return None
        return float(self.budget_per_account) * self.accounts - self.spent(st)


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        return [x.strip().strip("\"'") for x in s[1:-1].split(",") if x.strip()]
    return [p.strip() for p in s.split(",") if p.strip()]


class Fleet:
    def __init__(self):
        self.path, self.is_example = find_config()
        self.data: dict = load_yaml(self.path) if self.path else {}
        raw_platforms = self.data.get("platforms") or []
        self.platforms = [
            Platform(p) for p in raw_platforms if isinstance(p, dict)
        ]
        self.prefs = self.data.get("preferences") or {}
        self.destinations = self.data.get("destinations") or []
        self.brand = self.data.get("brand") or {}

    # -- preferences -------------------------------------------------------

    @property
    def require_approval(self) -> bool:
        return bool(self.prefs.get("require_approval_for_paid", True))

    @property
    def max_spend(self) -> float:
        try:
            return float(self.prefs.get("max_spend_per_run_usd", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    @property
    def rotate(self) -> bool:
        return bool(self.prefs.get("rotate_accounts", True))

    @property
    def low_warn_pct(self) -> float:
        try:
            return float(self.prefs.get("low_budget_warn_pct", 15) or 15)
        except (TypeError, ValueError):
            return 15.0

    def usable(self) -> list[Platform]:
        return [p for p in self.platforms if p.effective_access() != ACCESS_OFF]

    def mode(self) -> str:
        has_shell = bool(shutil.which("ffmpeg") or shutil.which("python3"))
        can_api = any(p.effective_access() == ACCESS_API for p in self.platforms)
        if not has_shell:
            return "TEXT"
        return "AUTONOMOUS" if can_api else "HYBRID"

    def next_account(self, p: Platform, st: dict) -> int:
        if p.accounts <= 1:
            return 1
        if not self.rotate:
            return 1
        cur = int(st.get("rotation", {}).get(p.id, 0))
        nxt = (cur % p.accounts) + 1
        st.setdefault("rotation", {})[p.id] = nxt
        return nxt


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_detect(fleet: Fleet, args) -> dict:
    st = load_state()
    mode = fleet.mode()

    plats = []
    for p in fleet.platforms:
        eff = p.effective_access()
        if eff == ACCESS_OFF:
            continue
        marker, meaning = p.marker()
        entry = {
            "id": p.id,
            "label": p.label,
            "declared_access": p.access,
            "effective_access": eff,
            "marker": marker,
            "meaning": meaning,
            "accounts": p.accounts,
            "can": p.can,
            "best_for": p.best_for,
            "priority": p.priority,
        }
        if p.access == ACCESS_API and eff == ACCESS_UI:
            entry["downgraded_because"] = (
                f"declared api but no key found in {p.auth_env or p.auth_env_pattern}"
            )
        if eff == ACCESS_API_PAID:
            entry["cost_warning"] = p.est_cost_note or "Requires separate purchase."
        rem = p.total_remaining(st)
        if rem is not None:
            entry["remaining_total"] = rem
            entry["unit"] = p.unit
        plats.append(entry)

    plats.sort(key=lambda e: e["priority"])

    warnings = []
    if fleet.is_example:
        warnings.append(
            "Using fleet.example.yaml. Copy it to fleet.yaml and edit it to "
            "describe the platforms you actually have."
        )
    if not plats:
        warnings.append("No usable platforms configured.")
    if mode == "HYBRID":
        warnings.append(
            "No API-callable platform with credentials. Generation will be manual: "
            "produce a packet with packet.py, user generates in the browser."
        )
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            warnings.append(f"{tool} not found on PATH — assembly will not work.")

    return {
        "mode": mode,
        "config": str(fleet.path) if fleet.path else None,
        "using_example_config": fleet.is_example,
        "require_approval_for_paid": fleet.require_approval,
        "max_spend_per_run_usd": fleet.max_spend,
        "platforms": plats,
        "destinations": [
            d.get("id") for d in fleet.destinations if isinstance(d, dict)
        ],
        "warnings": warnings,
        "reminder": (
            "Never generate before running the Routing Gate (SKILL.md §3) and "
            "getting an explicit choice from the user."
        ),
    }


def cmd_budget(fleet: Fleet, args) -> dict:
    st = load_state()
    out = []
    for p in fleet.platforms:
        if p.effective_access() == ACCESS_OFF:
            continue
        accounts = []
        for n in range(1, p.accounts + 1):
            rem = p.remaining(st, n)
            row: dict = {"account": n, "spent": p.spent(st, n)}
            if rem is not None:
                row["remaining"] = rem
                row["unit"] = p.unit
                if p.budget_per_account:
                    pct = 100.0 * rem / float(p.budget_per_account)
                    row["remaining_pct"] = round(pct, 1)
                    if pct <= fleet.low_warn_pct:
                        row["low"] = True
            accounts.append(row)
        out.append({
            "id": p.id,
            "label": p.label,
            "unit": p.unit,
            "resets": p.raw.get("resets"),
            "total_remaining": p.total_remaining(st),
            "accounts": accounts,
        })
    return {"budgets": out}


def _options_for(fleet: Fleet, need: str, best_for: list[str], st: dict) -> list[dict]:
    """Build cost-grouped routing options for one need."""
    cands = [p for p in fleet.usable() if p.supports(need)]
    opts = []
    for p in cands:
        eff = p.effective_access()
        marker, meaning = p.marker()
        acct = fleet.next_account(p, dict(st))  # don't persist during planning
        rem = p.remaining(st, acct)
        o = {
            "platform": p.id,
            "label": p.label,
            "marker": marker,
            "meaning": meaning,
            "access": eff,
            "score": p.strength_score(best_for),
            "priority": p.priority,
            "suggested_account": acct,
            "requires_approval": eff == ACCESS_API_PAID,
        }
        if rem is not None:
            o["remaining_on_account"] = rem
            o["unit"] = p.unit
            if rem <= 0:
                o["exhausted"] = True
        if eff == ACCESS_API_PAID:
            o["cost_warning"] = p.est_cost_note or "Requires separate purchase."
            o["must_say"] = (
                "This needs credits bought separately. Quote the estimate, "
                "say pricing must be verified, and ask before proceeding."
            )
        if eff == ACCESS_UI:
            o["manual_steps"] = p.manual_steps or [
                f"Open {p.url or p.label}", "Paste the prompt from the packet",
                "Generate and download", "Save to inbox/<shot-id>.mp4",
            ]
        if p.weak_at and p.strength_score(best_for) < 0:
            o["caution"] = f"Weak at: {', '.join(p.weak_at)}"
        if p.max_clip_seconds:
            o["max_clip_seconds"] = p.max_clip_seconds
        opts.append(o)

    # Best first: free-and-automatic, then strength, then priority.
    rank = {ACCESS_API: 0, ACCESS_UI: 1, ACCESS_API_PAID: 2}
    opts.sort(key=lambda o: (
        bool(o.get("exhausted")),
        rank.get(o["access"], 3) if fleet.prefs.get("prefer_included_credits", True) else 0,
        -o["score"],
        o["priority"],
    ))
    return opts


def cmd_plan(fleet: Fleet, args) -> dict:
    """
    Input plan.json:
      {"shots":[{"id":"s1","need":"image-to-video","best_for":["physical-realism"],
                 "seconds":5,"note":"hero bottle"}]}
    """
    src = Path(args.needs)
    if not src.is_file():
        return {"error": f"needs file not found: {src}"}
    try:
        plan = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"error": f"invalid JSON in {src}: {e}"}

    shots = plan.get("shots") if isinstance(plan, dict) else plan
    if not isinstance(shots, list):
        return {"error": "expected {'shots': [...]} or a list of shots"}

    st = load_state()
    routed, unroutable, needs_approval = [], [], False

    for i, sh in enumerate(shots, 1):
        if not isinstance(sh, dict):
            continue
        sid = str(sh.get("id") or f"s{i}")
        need = str(sh.get("need") or sh.get("needs") or "video")
        best_for = _as_list(sh.get("best_for"))
        opts = _options_for(fleet, need, best_for, st)
        if not opts:
            unroutable.append({
                "shot": sid, "need": need,
                "reason": "no configured platform supports this need",
                "suggestion": "Add a platform whose `can` includes this need, "
                              "or change the shot approach.",
            })
            continue
        if any(o.get("requires_approval") for o in opts[:1]):
            needs_approval = True
        if all(o.get("requires_approval") or o.get("exhausted") for o in opts):
            needs_approval = True
        routed.append({
            "shot": sid,
            "need": need,
            "seconds": sh.get("seconds"),
            "note": sh.get("note", ""),
            "best_for": best_for,
            "options": opts,
            "recommended": opts[0]["platform"],
        })

    return {
        "mode": fleet.mode(),
        "shots": routed,
        "unroutable": unroutable,
        "any_option_needs_payment": needs_approval,
        "gate": {
            "required": True,
            "instruction": (
                "Present these options to the user grouped by cost marker "
                "(INCLUDED / MANUAL / TOP-UP NEEDED), recommend the cheapest "
                "viable path first, never pre-select a paid option, and wait for "
                "an explicit choice before generating. Offer a mixed route."
            ),
            "max_spend_per_run_usd": fleet.max_spend,
        },
    }


def cmd_pick(fleet: Fleet, args) -> dict:
    st = load_state()
    opts = _options_for(fleet, args.need, _as_list(args.best_for), st)
    if not opts:
        return {"error": f"no platform supports need={args.need!r}"}
    return {
        "need": args.need,
        "best_for": _as_list(args.best_for),
        "options": opts,
        "recommended": opts[0],
        "gate_required": True,
    }


def cmd_spend(fleet: Fleet, args) -> dict:
    st = load_state()
    pid, acct = args.platform, str(args.account)
    st.setdefault("spend", {}).setdefault(pid, {})
    st["spend"][pid][acct] = float(st["spend"][pid].get(acct, 0)) + float(args.amount)
    save_state(st)
    p = next((x for x in fleet.platforms if x.id == pid), None)
    out = {"platform": pid, "account": args.account,
           "logged": float(args.amount), "total": st["spend"][pid][acct]}
    if p:
        rem = p.remaining(st, int(args.account))
        if rem is not None:
            out["remaining"] = rem
            out["unit"] = p.unit
            if p.budget_per_account:
                pct = 100.0 * rem / float(p.budget_per_account)
                out["remaining_pct"] = round(pct, 1)
                if pct <= fleet.low_warn_pct:
                    out["warning"] = (
                        f"Account {acct} of {p.label} is at {pct:.0f}% remaining."
                    )
    return out


def cmd_accounts(fleet: Fleet, args) -> dict:
    st = load_state()
    p = next((x for x in fleet.platforms if x.id == args.platform), None)
    if not p:
        return {"error": f"unknown platform: {args.platform}"}
    acct = fleet.next_account(p, st)
    save_state(st)
    rem = p.remaining(st, acct)
    out = {"platform": p.id, "account": acct, "of": p.accounts}
    if rem is not None:
        out["remaining"] = rem
        out["unit"] = p.unit
    if p.auth_env_pattern:
        out["auth_env"] = p.auth_env_pattern.replace("{n}", str(acct))
    elif p.auth_env:
        out["auth_env"] = p.auth_env
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="fleet.py",
        description="Read the generation fleet, detect mode, route shots. "
                    "Never generates and never spends.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("detect", help="operating mode and usable platforms")
    sub.add_parser("budget", help="remaining credits per account")

    sp = sub.add_parser("plan", help="routing options per shot")
    sp.add_argument("--needs", required=True, help="path to plan.json")

    sp = sub.add_parser("pick", help="options for a single need")
    sp.add_argument("--need", required=True,
                    help="video | image-to-video | avatar-video | lipsync | image | tts")
    sp.add_argument("--best-for", default="",
                    help="comma-separated strengths, e.g. physical-realism,native-audio")

    sp = sub.add_parser("spend", help="log credit usage")
    sp.add_argument("--platform", required=True)
    sp.add_argument("--account", required=True, type=int)
    sp.add_argument("--amount", required=True, type=float)

    sp = sub.add_parser("accounts", help="next account in rotation")
    sp.add_argument("--platform", required=True)

    args = ap.parse_args(argv)

    fleet = Fleet()
    if fleet.path is None:
        print(json.dumps({
            "error": "no fleet config found",
            "hint": "Copy fleet.example.yaml to fleet.yaml in the skill root.",
        }, indent=2))
        return 1

    handlers = {
        "detect": cmd_detect, "budget": cmd_budget, "plan": cmd_plan,
        "pick": cmd_pick, "spend": cmd_spend, "accounts": cmd_accounts,
    }
    result = handlers[args.cmd](fleet, args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if isinstance(result, dict) and "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
