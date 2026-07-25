#!/usr/bin/env python3
"""
generate.py — call a generation API for shots that were routed to an API platform.

SAFETY CONTRACT — this script exists to be safe, not clever:

  * It NEVER runs without an explicit --confirm flag. A dry run is the default.
  * It refuses platforms marked `api-paid` unless --allow-paid is also given.
  * It prints an itemised plan and an estimated credit draw before doing anything.
  * It logs every completed generation to the fleet spend ledger.

The agent must have run the Routing Gate (SKILL.md §3) and received the user's
explicit choice before this script is invoked with --confirm.

Usage:
    generate.py --plan plan.json                       # dry run: show plan, cost
    generate.py --plan plan.json --confirm              # generate (free/included only)
    generate.py --plan plan.json --confirm --allow-paid # include paid platforms
    generate.py --shot s1 --plan plan.json --confirm    # single shot
    generate.py --check                                 # what's callable right now

Only stdlib is used. HTTP via urllib.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

POLL_INTERVAL = 5
POLL_TIMEOUT = 900  # 15 minutes


# ---------------------------------------------------------------------------
# Fleet integration
# ---------------------------------------------------------------------------

def fleet_json(*args: str) -> dict:
    script = HERE / "fleet.py"
    if not script.is_file():
        return {}
    try:
        r = subprocess.run([sys.executable, str(script), *args],
                           capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return {}


def log_spend(platform: str, account: int, amount: float) -> None:
    script = HERE / "fleet.py"
    if not script.is_file():
        return
    try:
        subprocess.run(
            [sys.executable, str(script), "spend", "--platform", platform,
             "--account", str(account), "--amount", str(amount)],
            capture_output=True, text=True, timeout=20,
        )
    except (subprocess.SubprocessError, OSError):
        pass


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def http(url: str, *, method: str = "GET", headers: dict | None = None,
         body: dict | None = None, timeout: int = 120) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return 0, f"network error: {e}"


def download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ad-film-director/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
            while chunk := r.read(1 << 16):
                f.write(chunk)
        return dest.is_file() and dest.stat().st_size > 0
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _dig(obj: Any, keys: tuple[str, ...]) -> Any:
    """Find the first matching key anywhere in a nested structure."""
    if isinstance(obj, dict):
        for k in keys:
            if k in obj:
                return obj[k]
        for v in obj.values():
            got = _dig(v, keys)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = _dig(v, keys)
            if got is not None:
                return got
    return None


def find_video_url(payload: Any) -> str | None:
    v = _dig(payload, ("video", "video_url", "videoUrl", "output_url", "url", "output"))
    if isinstance(v, str) and v.startswith("http"):
        return v
    if isinstance(v, dict):
        u = _dig(v, ("url", "video_url"))
        if isinstance(u, str) and u.startswith("http"):
            return u
    if isinstance(v, list) and v:
        return find_video_url(v[0])
    return None


def find_status(payload: Any) -> str:
    s = _dig(payload, ("status", "state"))
    return str(s).lower() if s else ""


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

class Backend:
    """Generic async generation backend: submit → poll → download."""

    def __init__(self, plat: dict, account: int):
        self.plat = plat
        self.id = plat.get("id", "?")
        self.label = plat.get("label", self.id)
        self.account = account
        self.endpoint = (plat.get("endpoint") or "").rstrip("/")

    def auth_headers(self) -> dict:
        raise NotImplementedError

    def submit(self, shot: dict) -> tuple[bool, Any]:
        raise NotImplementedError

    def poll(self, handle: Any) -> tuple[str, Any]:
        raise NotImplementedError


class MagicaBackend(Backend):
    """
    magica.ai — Bearer auth, node/model execution with run polling.

    Endpoint shapes vary by account and change over time, so this probes a few
    plausible paths rather than hard-coding one. If none respond, it reports the
    failure honestly instead of pretending.
    """

    SUBMIT_PATHS = ("/nodes/run", "/runs", "/models/run", "/generate")
    POLL_PATHS = ("/runs/{id}", "/nodes/runs/{id}", "/generate/{id}")

    def auth_headers(self) -> dict:
        key = self.key()
        return {"Authorization": f"Bearer {key}"} if key else {}

    def key(self) -> str | None:
        pat = self.plat.get("auth_env_pattern") or ""
        if pat:
            v = os.environ.get(pat.replace("{n}", str(self.account)))
            if v:
                return v
        single = self.plat.get("auth_env") or "MAGICA_API_KEY"
        return os.environ.get(single)

    def submit(self, shot: dict) -> tuple[bool, Any]:
        body = {
            "prompt": shot.get("prompt", ""),
            "duration": shot.get("seconds", 5),
            "aspect_ratio": shot.get("aspect", "9:16"),
        }
        if shot.get("model"):
            body["model"] = shot["model"]
        if shot.get("negative"):
            body["negative_prompt"] = shot["negative"]
        if shot.get("reference"):
            body["image_url"] = shot["reference"]
        if shot.get("seed") is not None:
            body["seed"] = shot["seed"]

        last = None
        for path in self.SUBMIT_PATHS:
            code, payload = http(self.endpoint + path, method="POST",
                                 headers=self.auth_headers(), body=body)
            if code in (200, 201, 202):
                rid = _dig(payload, ("request_id", "id", "run_id", "requestId"))
                return True, {"id": rid, "path": path, "payload": payload}
            if code in (401, 403):
                return False, f"auth rejected ({code}) — check the API key for account {self.account}"
            last = f"{path} -> {code}: {str(payload)[:200]}"
        return False, f"no submit endpoint responded. Last: {last}"

    def poll(self, handle: Any) -> tuple[str, Any]:
        rid = handle.get("id")
        if not rid:
            # Some APIs return the result inline on submit.
            url = find_video_url(handle.get("payload"))
            return ("done", url) if url else ("error", "no request id and no inline result")
        for path in self.POLL_PATHS:
            code, payload = http(self.endpoint + path.format(id=rid),
                                 headers=self.auth_headers())
            if code == 200:
                status = find_status(payload)
                url = find_video_url(payload)
                if url:
                    return "done", url
                if status in ("failed", "error", "cancelled", "canceled"):
                    return "error", str(_dig(payload, ("error", "message")) or payload)[:300]
                return "pending", status or "processing"
        return "error", f"no poll endpoint responded for id={rid}"


class FalBackend(Backend):
    """fal.ai aggregator — Key auth, queue submit/poll. Usage-billed."""

    def auth_headers(self) -> dict:
        key = os.environ.get(self.plat.get("auth_env") or "FAL_KEY")
        return {"Authorization": f"Key {key}"} if key else {}

    def submit(self, shot: dict) -> tuple[bool, Any]:
        model = shot.get("model")
        if not model:
            return False, ("fal.ai needs an explicit model slug in the shot "
                           "(e.g. \"model\": \"fal-ai/<model>\"). Verify current slugs.")
        body = {"prompt": shot.get("prompt", "")}
        if shot.get("seconds"):
            body["duration"] = f"{shot['seconds']}s"
        if shot.get("aspect"):
            body["aspect_ratio"] = shot["aspect"]
        if shot.get("reference"):
            body["image_url"] = shot["reference"]
        if shot.get("audio") not in (None, "none", False, ""):
            body["generate_audio"] = True
        code, payload = http(f"https://fal.run/{model}", method="POST",
                             headers=self.auth_headers(), body=body)
        if code in (200, 201, 202):
            url = find_video_url(payload)
            if url:
                return True, {"inline": url}
            rid = _dig(payload, ("request_id", "requestId", "id"))
            return (True, {"id": rid, "model": model}) if rid else (False, "no request id returned")
        if code in (401, 403):
            return False, f"auth rejected ({code}) — check FAL_KEY"
        return False, f"{code}: {str(payload)[:200]}"

    def poll(self, handle: Any) -> tuple[str, Any]:
        if handle.get("inline"):
            return "done", handle["inline"]
        code, payload = http(
            f"https://queue.fal.run/{handle['model']}/requests/{handle['id']}",
            headers=self.auth_headers())
        if code != 200:
            return "error", f"{code}: {str(payload)[:200]}"
        url = find_video_url(payload)
        if url:
            return "done", url
        status = find_status(payload)
        if status in ("failed", "error"):
            return "error", str(payload)[:300]
        return "pending", status or "in_queue"


class HeyGenBackend(Backend):
    """HeyGen — X-Api-Key auth. PAY-AS-YOU-GO: always gated behind --allow-paid."""

    def auth_headers(self) -> dict:
        key = os.environ.get(self.plat.get("auth_env")
                             or (self.plat.get("api") or {}).get("auth_env")
                             or "HEYGEN_API_KEY")
        return {"X-Api-Key": key} if key else {}

    def submit(self, shot: dict) -> tuple[bool, Any]:
        avatar = shot.get("avatar_id")
        if not avatar:
            return False, "HeyGen needs \"avatar_id\" in the shot. List avatars in the UI first."
        body = {
            "video_inputs": [{
                "character": {"type": "avatar", "avatar_id": avatar,
                              "avatar_style": shot.get("avatar_style", "normal")},
                "voice": {"type": "text", "input_text": shot.get("script")
                          or shot.get("prompt", ""),
                          "voice_id": shot.get("voice_id", "")},
            }],
            "dimension": {"width": 1080, "height": 1920},
        }
        code, payload = http(f"{self.endpoint or 'https://api.heygen.com'}/v2/video/generate",
                             method="POST", headers=self.auth_headers(), body=body)
        if code in (200, 201, 202):
            vid = _dig(payload, ("video_id", "videoId", "id"))
            return (True, {"id": vid}) if vid else (False, f"no video id: {str(payload)[:200]}")
        if code in (401, 403):
            return False, f"auth rejected ({code}) — check HEYGEN_API_KEY and that API credits exist"
        return False, f"{code}: {str(payload)[:200]}"

    def poll(self, handle: Any) -> tuple[str, Any]:
        base = self.endpoint or "https://api.heygen.com"
        code, payload = http(f"{base}/v1/video_status.get?video_id={handle['id']}",
                             headers=self.auth_headers())
        if code != 200:
            return "error", f"{code}: {str(payload)[:200]}"
        status = find_status(payload)
        if status in ("completed", "success", "done"):
            url = find_video_url(payload)
            return ("done", url) if url else ("error", "completed but no URL")
        if status in ("failed", "error"):
            return "error", str(_dig(payload, ("error", "message")) or payload)[:300]
        return "pending", status or "processing"


BACKENDS = {"magica": MagicaBackend, "fal": FalBackend, "heygen": HeyGenBackend}


def make_backend(plat: dict, account: int) -> Backend | None:
    cls = BACKENDS.get(plat.get("id", ""))
    return cls(plat, account) if cls else None


# ---------------------------------------------------------------------------
# Planning and execution
# ---------------------------------------------------------------------------

def build_jobs(plan: dict, detect: dict, only: str | None) -> tuple[list[dict], list[dict]]:
    """Split shots into runnable jobs and skipped ones with reasons."""
    pinfo = {p["id"]: p for p in detect.get("platforms", [])}
    jobs, skipped = [], []

    for i, shot in enumerate(plan.get("shots") or [], 1):
        if not isinstance(shot, dict):
            continue
        sid = str(shot.get("id") or f"s{i}")
        if only and sid != only:
            continue
        pid = shot.get("platform")
        if not pid:
            skipped.append({"shot": sid, "reason": "no platform assigned — "
                            "run the Routing Gate first"})
            continue
        p = pinfo.get(pid)
        if not p:
            skipped.append({"shot": sid, "reason": f"platform {pid!r} not in fleet config"})
            continue
        access = p.get("effective_access")
        if access == "ui":
            skipped.append({"shot": sid, "platform": pid,
                            "reason": f"{p.get('label', pid)} is UI-only — "
                                      "use packet.py and generate manually"})
            continue
        if pid not in BACKENDS:
            skipped.append({"shot": sid, "platform": pid,
                            "reason": f"no API backend implemented for {pid!r} — "
                                      "generate manually via packet.py"})
            continue
        jobs.append({
            "shot": shot, "id": sid, "platform": p, "pid": pid,
            "paid": access == "api-paid",
            "account": shot.get("account") or 1,
            "cost_note": p.get("cost_warning", ""),
        })
    return jobs, skipped


def run_job(job: dict, outdir: Path, timeout: int) -> dict:
    sid, pid = job["id"], job["pid"]
    be = make_backend(job["platform"], int(job["account"]))
    if be is None:
        return {"shot": sid, "ok": False, "error": "no backend"}

    if not be.auth_headers():
        return {"shot": sid, "ok": False,
                "error": f"no API key in environment for {pid}"}

    ok, handle = be.submit(job["shot"])
    if not ok:
        return {"shot": sid, "platform": pid, "ok": False, "error": str(handle)}

    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        state, info = be.poll(handle)
        if state == "done":
            dest = outdir / f"{sid}.mp4"
            if download(str(info), dest):
                cost = job["shot"].get("est_credits")
                if cost:
                    log_spend(pid, int(job["account"]), float(cost))
                return {"shot": sid, "platform": pid, "ok": True,
                        "file": str(dest), "bytes": dest.stat().st_size,
                        "logged_credits": cost}
            return {"shot": sid, "platform": pid, "ok": False,
                    "error": f"download failed from {info}"}
        if state == "error":
            return {"shot": sid, "platform": pid, "ok": False, "error": str(info)}
        last = str(info)
        time.sleep(POLL_INTERVAL)

    return {"shot": sid, "platform": pid, "ok": False,
            "error": f"timed out after {timeout}s (last status: {last})"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="generate.py",
        description="Generate routed shots via API. Dry run unless --confirm.",
    )
    ap.add_argument("--plan", help="path to plan.json")
    ap.add_argument("--shot", help="generate only this shot id")
    ap.add_argument("--out", default="generated", help="output directory")
    ap.add_argument("--confirm", action="store_true",
                    help="actually generate (required; costs credits)")
    ap.add_argument("--allow-paid", action="store_true",
                    help="also allow platforms that need purchased credits")
    ap.add_argument("--timeout", type=int, default=POLL_TIMEOUT)
    ap.add_argument("--check", action="store_true",
                    help="report which platforms are API-callable right now")
    args = ap.parse_args(argv)

    detect = fleet_json("detect")
    if not detect:
        print(json.dumps({"error": "could not read fleet config via fleet.py"}, indent=2))
        return 1

    if args.check:
        rows = []
        for p in detect.get("platforms", []):
            rows.append({
                "id": p["id"], "label": p["label"],
                "access": p.get("effective_access"), "marker": p.get("marker"),
                "backend_implemented": p["id"] in BACKENDS,
                "callable_now": p.get("effective_access") == "api" and p["id"] in BACKENDS,
                "cost_warning": p.get("cost_warning", ""),
            })
        print(json.dumps({"mode": detect.get("mode"), "platforms": rows}, indent=2))
        return 0

    if not args.plan:
        print(json.dumps({"error": "--plan is required (or use --check)"}, indent=2))
        return 1

    src = Path(args.plan)
    if not src.is_file():
        print(json.dumps({"error": f"plan not found: {src}"}, indent=2))
        return 1
    try:
        plan = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON: {e}"}, indent=2))
        return 1

    jobs, skipped = build_jobs(plan, detect, args.shot)
    paid_jobs = [j for j in jobs if j["paid"]]

    # ---- dry run (default) ----
    if not args.confirm:
        print(json.dumps({
            "dry_run": True,
            "mode": detect.get("mode"),
            "would_generate": [
                {"shot": j["id"], "platform": j["pid"], "account": j["account"],
                 "paid": j["paid"], "cost_note": j["cost_note"]} for j in jobs
            ],
            "skipped": skipped,
            "paid_shots": len(paid_jobs),
            "next_step": (
                "Nothing was generated. Present the Routing Gate to the user, get an "
                "explicit choice, then re-run with --confirm"
                + (" --allow-paid" if paid_jobs else "") + "."
            ),
            "warning": (
                "Some shots would use platforms requiring purchased credits. "
                "Quote the estimate and get approval before using --allow-paid."
            ) if paid_jobs else None,
        }, indent=2, ensure_ascii=False))
        return 0

    # ---- paid gate ----
    if paid_jobs and not args.allow_paid:
        print(json.dumps({
            "blocked": True,
            "reason": "shots routed to platforms needing purchased credits",
            "shots": [{"shot": j["id"], "platform": j["pid"],
                       "cost_note": j["cost_note"]} for j in paid_jobs],
            "required": "re-run with --allow-paid, but only after the user has "
                        "explicitly approved the spend",
        }, indent=2, ensure_ascii=False))
        return 2

    if not jobs:
        print(json.dumps({
            "generated": [], "skipped": skipped,
            "note": "Nothing to generate via API. Use packet.py for manual platforms.",
        }, indent=2, ensure_ascii=False))
        return 0

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    results = []
    for j in jobs:
        print(f"[generate] {j['id']} via {j['pid']} (account {j['account']})…",
              file=sys.stderr)
        results.append(run_job(j, outdir, args.timeout))

    ok = [r for r in results if r.get("ok")]
    print(json.dumps({
        "generated": ok,
        "failed": [r for r in results if not r.get("ok")],
        "skipped": skipped,
        "outdir": str(outdir),
        "next_step": "Review each clip against the checklist in consistency.md, "
                     "then assemble via the video-editor skill (see delegation.md).",
    }, indent=2, ensure_ascii=False))
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
