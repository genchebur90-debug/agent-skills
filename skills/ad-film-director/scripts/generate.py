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
sys.path.insert(0, str(HERE))

import planlint  # noqa: E402  — one spelling of the plan schema, one gate

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
    magica.ai — Bearer auth (gx_ keys), direct model execution via Nodes.

    Verified against the live API 2026-08-01:
        POST /api/v1/nodes/{nodeType}/run  body: {subModelId?, input:{...}}
        GET  /api/v1/nodes/runs/{runId}
        GET  /api/v1/credits/balance
        POST /api/v1/uploads              body: {base64|url|data_uri, filename, contentType}
        GET  /api/v1/models               -> [{nodeType, name, category}]      <- PATH ids
        GET  /api/v1/models/search        -> {modelCatalog: {category: [{modelId}]}}
        GET  /api/v1/models/{modelId}/pricing   and   /schema

    TWO ID NAMESPACES, and mixing them is the most common failure:
      * the PATH takes a **nodeType** — underscores, e.g. `seedance_2_0_fast`,
        `kling_v3_pro`. Get these from GET /models.
      * `subModelId` in the body takes the **catalog modelId** — dashes, e.g.
        `seedance-2.0-fast-image-to-video`. Get these from GET /models/search.
      Putting the dashed catalog id in the path returns
      404 {"error":"Unknown node type: ..."} for every shot.

    Image inputs must be on a host the provider can fetch. Thread-internal URLs are
    not reachable — POST the bytes to /uploads as base64 and use the CDN url it
    returns.

    POST /nodes/estimate-credits IS BROKEN: it answers 200 with {"microcredits": 0}
    for paid models. Zero does not mean free. Price from
    GET /models/{modelId}/pricing -> pricingDetails.tiers, multiplied by seconds.

    Model parameters go inside a nested `input` object, not at the body root.
    """

    def auth_headers(self) -> dict:
        key = self.key()
        return {"Authorization": f"Bearer {key}"} if key else {}

    def key(self) -> str | None:
        """Resolve this account's key. Numbered pattern wins over the single var."""
        pat = self.plat.get("auth_env_pattern") or ""
        if pat:
            v = os.environ.get(pat.replace("{n}", str(self.account)))
            if v:
                return v
        single = self.plat.get("auth_env") or "MAGICA_API_KEY"
        return os.environ.get(single)

    # -- cost and balance, used by the Routing Gate --------------------------

    def balance(self) -> dict | None:
        """
        Live credit balance for this account. None if unreachable.

        Reports WHY on failure. "Did not respond" sends someone hunting a network
        fault when the real answer is usually a rejected key — and those need
        opposite fixes.
        """
        code, payload = http(f"{self.endpoint}/credits/balance",
                             headers=self.auth_headers(), timeout=30)
        if code == 200 and isinstance(payload, dict):
            return {
                "available": payload.get("availableBalance"),
                "formatted": payload.get("formatted"),
                "subscription": payload.get("hasActiveSubscription"),
            }
        if code in (401, 403):
            return {
                "available": None,
                "auth_failed": True,
                "http_status": code,
                "why": (f"{self.label} rejected the key for account {self.account} "
                        f"(HTTP {code}). Check it is current and pasted whole."),
            }
        if code == 429:
            return {"available": None, "http_status": 429,
                    "why": "Rate limited — wait and retry."}
        return {
            "available": None,
            "http_status": code,
            "why": f"Balance call returned HTTP {code}.",
        }

    def estimate(self, shots: list[dict]) -> dict | None:
        """
        Exact pre-run cost in microcredits. Per magica's docs this mirrors
        run-time charging exactly and has no side effects.
        """
        nodes = []
        for s in shots:
            model = s.get("model")
            if not model:
                continue
            node: dict = {"type": model, "data": self._input_for(s)}
            if s.get("sub_model"):
                node["subModelId"] = s["sub_model"]
            nodes.append(node)
        if not nodes:
            return None
        code, payload = http(f"{self.endpoint}/nodes/estimate-credits",
                             method="POST", headers=self.auth_headers(),
                             body={"nodes": nodes[:100]}, timeout=60)
        if code == 200 and isinstance(payload, dict):
            return payload
        return None

    # -- generation ---------------------------------------------------------

    @staticmethod
    def _input_for(shot: dict) -> dict:
        """Build the nested `input` object magica expects."""
        inp: dict = {"prompt": shot.get("prompt", "")}
        if shot.get("seconds"):
            inp["duration"] = shot["seconds"]
        if shot.get("aspect"):
            inp["aspect_ratio"] = shot["aspect"]
        if shot.get("negative"):
            inp["negative_prompt"] = shot["negative"]
        if shot.get("reference"):
            inp["image_url"] = shot["reference"]
        if shot.get("seed") is not None:
            inp["seed"] = shot["seed"]
        if shot.get("resolution"):
            inp["resolution"] = shot["resolution"]
        # Pass through anything the caller set explicitly for this model.
        extra = shot.get("input")
        if isinstance(extra, dict):
            inp.update(extra)
        return inp

    def submit(self, shot: dict) -> tuple[bool, Any]:
        model = shot.get("model")
        if not model:
            return False, (
                "magica needs a nodeType in the shot, e.g. \"model\": \"kling_v3_pro\" "
                "(underscores). List them with GET /api/v1/models. The dashed catalog id "
                "such as kling-v3-pro-image-to-video goes in \"sub_model\", not here."
            )
        body: dict = {"input": self._input_for(shot)}
        if shot.get("sub_model"):
            body["subModelId"] = shot["sub_model"]

        code, payload = http(f"{self.endpoint}/nodes/{model}/run",
                             method="POST", headers=self.auth_headers(), body=body)
        if code in (200, 201, 202):
            rid = _dig(payload, ("runId", "run_id", "id"))
            if rid:
                return True, {"id": rid}
            url = find_video_url(payload)
            return (True, {"inline": url}) if url else (
                False, f"no runId in response: {str(payload)[:200]}")
        if code in (401, 403):
            return False, (f"auth rejected ({code}) for account {self.account} — "
                           "key missing, revoked or expired")
        if code == 429:
            return False, "rate limited (429) — wait and retry, or use another account"
        if code == 404:
            return False, (f"nodeType {model!r} not found. The PATH needs an underscored "
                           "nodeType from GET /v1/models (e.g. kling_v3_pro). A dashed "
                           "catalog id from /models/search belongs in sub_model instead.")
        return False, f"{code}: {str(payload)[:250]}"

    def poll(self, handle: Any) -> tuple[str, Any]:
        if handle.get("inline"):
            return "done", handle["inline"]
        rid = handle.get("id")
        if not rid:
            return "error", "no runId to poll"
        code, payload = http(f"{self.endpoint}/nodes/runs/{rid}",
                             headers=self.auth_headers())
        if code != 200:
            return "error", f"{code}: {str(payload)[:200]}"
        url = find_video_url(payload)
        if url:
            return "done", url
        status = find_status(payload)
        if status in ("failed", "error", "cancelled", "canceled"):
            return "error", str(_dig(payload, ("error", "message")) or payload)[:300]
        return "pending", status or "processing"


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


class HostBackend(Backend):
    """
    The agent's own host renders the shot — no HTTP, no key, no browser step.

    Everything else here talks to a remote service. This one cannot: the host's
    generation tools live in the agent's runtime, not behind a URL this script
    can reach. So it does the one useful thing a script can do in that position
    — it turns each shot into an unambiguous, ready-to-execute render order and
    hands it back. The agent executes the orders with its own tools and writes
    the results to the filenames named here.

    The filename contract is the same one packet.py uses (`inbox/<shot>.mp4`),
    so assembly downstream cannot tell how a clip arrived. That is the point:
    swapping a shot between host, API and manual generation changes nothing
    after this step.

    Config is data, like every other platform:

        - id: host
          access: host
          protocol: host
          tools:
            video:  GenerateVideo
            image:  GenerateImage
            audio:  GenerateAudio
            avatar: GenerateAvatarVideo
    """

    # Which shot needs map to which kind of tool, in priority order.
    NEED_KINDS = (
        ("avatar", ("avatar", "lipsync", "talking-head", "presenter")),
        ("audio", ("audio", "tts", "voice", "voiceover", "music")),
        ("image", ("image", "still", "keyframe", "frame", "poster")),
        ("video", ("video", "clip", "shot", "image-to-video", "motion")),
    )

    def _kind(self, shot: dict) -> str:
        want = " ".join(
            str(shot.get(k) or "") for k in ("kind", "need", "type", "output")
        ).lower()
        for kind, words in self.NEED_KINDS:
            if any(w in want for w in words):
                return kind
        # No explicit need: an attached still implies image-to-video, otherwise
        # a plain video clip. Both are video work.
        return "video"

    def _tool_for(self, kind: str) -> str:
        tools = self.plat.get("tools")
        if isinstance(tools, dict) and tools.get(kind):
            return str(tools[kind])
        return {
            "video": "GenerateVideo",
            "image": "GenerateImage",
            "audio": "GenerateAudio",
            "avatar": "GenerateAvatarVideo",
        }[kind]

    def auth_headers(self) -> dict:
        return {}

    def submit(self, shot: dict) -> tuple[bool, Any]:
        kind = self._kind(shot)
        sid = str(shot.get("id") or "shot")
        ext = {"audio": "mp3", "image": "png"}.get(kind, "mp4")
        filename = str(shot.get("filename") or f"{sid}.{ext}")

        args: dict = {"prompt": shot.get("prompt", "")}
        if shot.get("seconds"):
            args["durationSeconds"] = shot["seconds"]
        if shot.get("aspect"):
            args["aspectRatio"] = shot["aspect"]
        if shot.get("resolution"):
            args["resolution"] = shot["resolution"]
        if shot.get("model"):
            args["model"] = shot["model"]
        # Consistency controls: a still locks composition, references hold the
        # character and style steady across a campaign. See consistency.md.
        # One spelling of "the plates this shot inherits". packet.py, planlint
        # and generate.py used to disagree about the field name, which is how a
        # reference silently stopped being attached between two scripts.
        parents = planlint.normalize_shot(shot).get("parents", [])
        if parents:
            args["firstFrameImage"] = parents[0]
            args["referenceImages"] = parents[:9]
        if shot.get("voice"):
            args["voice"] = shot["voice"]
        if shot.get("avatar_id"):
            args["avatarId"] = shot["avatar_id"]
        extra = shot.get("input")
        if isinstance(extra, dict):
            args.update(extra)
        args["title"] = str(shot.get("title") or shot.get("label") or sid)

        return True, {
            "render_order": True,
            "shot": sid,
            "kind": kind,
            "tool": self._tool_for(kind),
            "args": args,
            "save_as": f"inbox/{filename}",
        }

    def poll(self, handle: Any) -> tuple[str, Any]:
        # Nothing to wait for: the agent, not this script, does the rendering.
        return "host", handle


# Protocol -> backend. Keyed by the *shape of the conversation*, not by vendor,
# so a new service that speaks a shape already here is a config block and zero
# code. Platform ids stay as aliases so existing fleet.yaml files keep working.
PROTOCOLS = {
    "magica-like": MagicaBackend,
    "fal-like": FalBackend,
    "heygen-like": HeyGenBackend,
    "host": HostBackend,
}

# Legacy: id-keyed lookup from before protocols existed.
BACKENDS = {"magica": MagicaBackend, "fal": FalBackend, "heygen": HeyGenBackend,
            "host": HostBackend}


def resolve_backend_class(plat: dict):
    """
    Find the backend for a platform: declared protocol first, then its id as a
    legacy alias. Returns None when nothing can talk to it, which callers report
    as "generate this one manually" rather than failing the run.
    """
    proto = str(plat.get("protocol") or "").strip().lower()
    if proto in PROTOCOLS:
        return PROTOCOLS[proto]
    # Tolerate a bare protocol name ("magica" for "magica-like").
    if proto and f"{proto}-like" in PROTOCOLS:
        return PROTOCOLS[f"{proto}-like"]
    return BACKENDS.get(str(plat.get("id") or "").strip().lower())


def make_backend(plat: dict, account: int) -> Backend | None:
    cls = resolve_backend_class(plat)
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
        if resolve_backend_class(p) is None:
            proto = p.get("protocol") or pid
            skipped.append({"shot": sid, "platform": pid,
                            "reason": f"no backend speaks protocol {proto!r} for "
                                      f"{pid!r} — generate manually via packet.py"})
            continue
        jobs.append({
            "shot": shot, "id": sid, "platform": p, "pid": pid,
            "paid": access == "api-paid",
            "host": access == "host",
            "account": shot.get("account") or 1,
            "cost_note": p.get("cost_warning", ""),
        })
    return jobs, skipped


def live_cost_and_balance(jobs: list[dict]) -> dict:
    """
    Ask each API platform for its real balance and a real pre-run cost estimate.
    Returns {} when no platform supports it. Never raises — this is advisory.
    """
    out: dict = {}
    by_platform: dict[str, list[dict]] = {}
    for j in jobs:
        by_platform.setdefault(j["pid"], []).append(j)

    for pid, group in by_platform.items():
        be = make_backend(group[0]["platform"], int(group[0]["account"]))
        if be is None or not be.auth_headers():
            continue
        entry: dict = {}

        if hasattr(be, "balance"):
            try:
                bal = be.balance()  # type: ignore[attr-defined]
                if bal:
                    entry["balance"] = bal
            except Exception:
                pass

        if hasattr(be, "estimate"):
            try:
                est = be.estimate([g["shot"] for g in group])  # type: ignore[attr-defined]
                if est:
                    entry["estimate"] = est
                    total = _dig(est, ("totalMicrocredits", "total_microcredits"))
                    if isinstance(total, (int, float)):
                        entry["estimated_credits"] = total / 1_000_000
            except Exception:
                pass

        if entry:
            entry["shots"] = [g["id"] for g in group]
            out[pid] = entry

    return out


def all_account_balances(detect: dict, platform_id: str) -> list[dict]:
    """Balance for every configured account on one platform — for `--balances`."""
    plat = next((p for p in detect.get("platforms", [])
                 if p["id"] == platform_id), None)
    if not plat:
        return []
    rows = []
    for n in range(1, int(plat.get("accounts", 1)) + 1):
        be = make_backend(plat, n)
        row: dict = {"account": n}
        if be is None:
            row["error"] = "no backend implemented"
        elif not be.auth_headers():
            row["error"] = "no key in environment"
        elif hasattr(be, "balance"):
            try:
                bal = be.balance()  # type: ignore[attr-defined]
                if bal:
                    row.update(bal)
                    # A reachable endpoint that returned no number is still a
                    # failure for the caller — surface it as one.
                    if bal.get("available") is None and bal.get("why"):
                        row["error"] = bal["why"]
                else:
                    row["error"] = "balance endpoint did not respond"
            except Exception as e:
                row["error"] = f"{type(e).__name__}: {e}"
        else:
            row["error"] = "platform does not expose a balance endpoint"
        rows.append(row)
    return rows


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
    ap.add_argument("--balances", metavar="PLATFORM",
                    help="show live credit balance for every account on a platform")
    ap.add_argument("--campaign", help="campaign name for lock checks (default: active)")
    ap.add_argument("--force", action="store_true",
                    help="generate despite planlint errors. This spends money on "
                         "footage already known to drift.")
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
                "protocol": p.get("protocol") or p["id"],
                "backend_implemented": resolve_backend_class(p) is not None,
                "callable_now": (p.get("effective_access") in ("api", "host")
                                 and resolve_backend_class(p) is not None),
                "cost_warning": p.get("cost_warning", ""),
            })
        print(json.dumps({"mode": detect.get("mode"), "platforms": rows}, indent=2))
        return 0

    if args.balances:
        rows = all_account_balances(detect, args.balances)
        if not rows:
            print(json.dumps({
                "error": f"platform {args.balances!r} not found in fleet config",
            }, indent=2))
            return 1
        usable = [r for r in rows if "error" not in r]
        total = sum(r["available"] for r in usable
                    if isinstance(r.get("available"), (int, float)))
        print(json.dumps({
            "platform": args.balances,
            "accounts": rows,
            "usable_accounts": len(usable),
            "total_available": total or None,
            "hint": "The account with the most credits is used first when "
                    "prefer_fullest_account is on.",
        }, indent=2, ensure_ascii=False))
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

    # ---- the gate --------------------------------------------------------
    # Money is about to move. A shot that names no plate will come back wrong
    # and be regenerated at full price, so the cheapest possible moment to
    # catch it is here, before the first API call.
    lint_report = planlint.lint(plan, planlint.load_campaign(args.campaign))
    if not lint_report["ok"]:
        print(planlint.render(lint_report), file=sys.stderr)
        if not args.force:
            print(json.dumps({
                "blocked": "plan has errors that guarantee drift — not spending "
                           "credits on it",
                "errors": len(lint_report["errors"]),
                "fix_then_rerun": f"python3 scripts/planlint.py --plan {args.plan}",
                "override": "--force, only with the user's explicit approval",
            }, indent=2))
            return 1
        print("proceeding under --force despite the errors above\n", file=sys.stderr)
    elif lint_report["warnings"]:
        print(planlint.render(lint_report), file=sys.stderr)

    jobs, skipped = build_jobs(plan, detect, args.shot)
    paid_jobs = [j for j in jobs if j["paid"]]

    # ---- dry run (default) ----
    if not args.confirm:
        out: dict[str, Any] = {
            "dry_run": True,
            "mode": detect.get("mode"),
            "would_generate": [
                {"shot": j["id"], "platform": j["pid"], "account": j["account"],
                 "paid": j["paid"], "cost_note": j["cost_note"]} for j in jobs
            ],
            "skipped": skipped,
            "paid_shots": len(paid_jobs),
        }

        # Real numbers where the platform can give them, so the Routing Gate
        # quotes actual cost and actual balance rather than a guess.
        live = live_cost_and_balance(jobs)
        if live:
            out["live"] = live

        out["next_step"] = (
            "Nothing was generated. Present the Routing Gate to the user with the "
            "cost figures above, get an explicit choice, then re-run with --confirm"
            + (" --allow-paid" if paid_jobs else "") + "."
        )
        if paid_jobs:
            out["warning"] = (
                "Some shots would use platforms requiring purchased credits. "
                "Quote the estimate, say pricing must be verified, and get "
                "approval before using --allow-paid."
            )
        print(json.dumps(out, indent=2, ensure_ascii=False))
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
