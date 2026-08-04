#!/usr/bin/env python3
"""
siblings.py — find and run the sibling skills, from any host, without env vars.

Why this exists
---------------
The previous contract was a bash snippet that exported VE_DIR and WATCH_BIN and
told the agent to "remember the result". Almost no agent host keeps a shell
alive between tool calls: each command runs in a fresh process, the exports die
with it, and every later command silently becomes `python3 /playbook.py`. The
delegation looked configured and was in fact broken on every second run.

So resolution moved into a script. It probes the known install layouts, caches
what it found in .campaign/siblings.json, and can exec the target itself with
the child environment already wired. One command works the same in Claude Code,
Codex, Gumloop, a plain terminal or a CI box.

Usage
-----
    siblings.py doctor                  # what is available, as JSON
    siblings.py path video-editor       # absolute dir, or exit 3
    siblings.py bin  watch              # dir that actually holds the scripts
    siblings.py run video-editor playbook.py -- ad --clips a.mp4 --out o.mp4
    siblings.py run watch watch.py -- master.mp4 --detail balanced --no-whisper
    siblings.py refresh                 # forget the cache and probe again

Exit codes
----------
    0  fine
    3  sibling not installed  (callers: fall back, do not crash)
    4  sibling found but its entry script is missing
    other  whatever the child process returned

Override anything with environment variables when a host puts skills somewhere
unusual:  ADFD_VIDEO_EDITOR_DIR, ADFD_WATCH_DIR, ADFD_FILM_DIRECTOR_DIR,
ADFD_SKILLS_DIR (a directory that contains several skills).

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
STATE = Path(".campaign") / "siblings.json"

# name -> (marker file that proves it is really that skill, env override)
SIBLINGS: dict[str, dict] = {
    "video-editor": {
        "marker": "playbook.py",
        "env": "ADFD_VIDEO_EDITOR_DIR",
        "owns": "post-production: cutting, grade, captions, loudness, export, QC",
    },
    "watch": {
        "marker": "watch.py",
        "env": "ADFD_WATCH_DIR",
        "owns": "seeing and measuring video: frames, transcript, montage metrics",
    },
    "film-director": {
        "marker": "SKILL.md",
        "env": "ADFD_FILM_DIRECTOR_DIR",
        "owns": "narrative film and animation over 60s",
    },
}

# Directories that hosts are known to keep skills in. Cheap to probe, and a
# miss costs one stat() call.
HOST_ROOTS = (
    "/home/user/skills",                 # Gumloop sandbox
    "~/.claude/skills",
    "~/.agents/skills",
    "~/.codex/skills",
    "~/.config/agents/skills",
    "~/.config/agent-skills",
    "~/skills",
    "/mnt/skills/public",
    "/opt/skills",
)


def _norm(p: Path) -> Path:
    return Path(os.path.expanduser(str(p)))


def _entry_dir(base: Path, marker: str) -> Path | None:
    """A skill installs either flat or with its code under scripts/."""
    base = _norm(base)
    if (base / marker).is_file():
        return base.resolve()
    if (base / "scripts" / marker).is_file():
        return (base / "scripts").resolve()
    return None


def _candidates(name: str) -> list[Path]:
    """Every place worth looking, cheapest and most likely first."""
    out: list[Path] = []

    env_dir = os.environ.get(SIBLINGS[name]["env"])
    if env_dir:
        out.append(Path(env_dir))

    shared = os.environ.get("ADFD_SKILLS_DIR")
    if shared:
        out.append(Path(shared) / name)

    # Next to this skill — the normal case in every layout that has one.
    out += [
        SKILL_ROOT.parent / name,             # skills/ad-film-director -> skills/<name>
        SKILL_ROOT.parent.parent / name,      # repo/skills/... -> repo/<name>
        SKILL_ROOT.parent.parent / "skills" / name,
        SKILL_ROOT / name,                    # vendored inside this skill
    ]

    # Wherever the agent happens to be working.
    cwd = Path.cwd()
    out += [cwd / name, cwd / "skills" / name, cwd.parent / name]

    for root in HOST_ROOTS:
        out.append(Path(root) / name)

    # Repo-style installs: <root>/<name>-skill/<name> and <root>/<name>-skill
    for root in HOST_ROOTS:
        out.append(Path(root) / f"{name}-skill" / name)
        out.append(Path(root) / f"{name}-skill")

    # Claude Code plugin cache, e.g. ~/.claude/plugins/cache/<plugin>/<name>/*/skills/<name>
    plug = _norm(Path("~/.claude/plugins/cache"))
    if plug.is_dir():
        try:
            out += sorted(plug.glob(f"*/**/skills/{name}"))[:20]
        except OSError:
            pass

    root_env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root_env:
        out.append(Path(root_env) / "skills" / name)

    return out


def _load_cache() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except OSError:
        pass          # a read-only workspace is not a reason to fail


def resolve(name: str, use_cache: bool = True) -> dict:
    """Locate one sibling. Returns {'found': bool, 'dir', 'bin', 'how'}."""
    if name not in SIBLINGS:
        return {"found": False, "error": f"unknown sibling '{name}'",
                "known": sorted(SIBLINGS)}
    marker = SIBLINGS[name]["marker"]

    if use_cache:
        hit = _load_cache().get(name)
        if hit and hit.get("bin") and Path(hit["bin"], marker).is_file():
            return {**hit, "found": True, "how": "cache"}

    for cand in _candidates(name):
        try:
            bin_dir = _entry_dir(cand, marker)
        except OSError:
            continue
        if bin_dir:
            rec = {"name": name, "dir": str(bin_dir.parent if bin_dir.name == "scripts"
                                            else bin_dir),
                   "bin": str(bin_dir), "how": "probe"}
            cache = _load_cache()
            cache[name] = {k: rec[k] for k in ("name", "dir", "bin")}
            _save_cache(cache)
            return {**rec, "found": True}

    return {"found": False, "name": name,
            "owns": SIBLINGS[name]["owns"],
            "hint": f"set {SIBLINGS[name]['env']}=/path/to/{name} if it is installed "
                    f"somewhere unusual"}


def child_env(extra: dict | None = None) -> dict:
    """Environment for a delegated call, with every sibling path already set.

    montage.py inside `watch` looks for rhythm.py through VE_DIR, so exporting
    it here is what makes beat analysis work at all.
    """
    env = dict(os.environ)
    for name in SIBLINGS:
        r = resolve(name)
        if not r.get("found"):
            continue
        if name == "video-editor":
            env["VE_DIR"] = r["bin"]
        elif name == "watch":
            env["WATCH_DIR"] = r["dir"]
            env["WATCH_BIN"] = r["bin"]
        elif name == "film-director":
            env["FD_DIR"] = r["dir"]
    env["ADFD_DIR"] = str(SKILL_ROOT)
    if extra:
        env.update(extra)
    return env


def host_report() -> dict:
    """What this host can actually do — the first thing any agent should ask."""
    ff = shutil.which("ffmpeg")
    probe = shutil.which("ffprobe")
    return {
        "python": ".".join(str(v) for v in sys.version_info[:3]),
        "ffmpeg": ff or None,
        "ffprobe": probe or None,
        "shell": True,
        "cwd": str(Path.cwd()),
        "skill_root": str(SKILL_ROOT),
        "campaign_state": str(Path(".campaign").resolve()) if Path(".campaign").is_dir() else None,
    }


def cmd_doctor(args) -> int:
    out = {"host": host_report(), "siblings": {}}
    for name in SIBLINGS:
        r = resolve(name, use_cache=not args.refresh)
        entry = {"found": bool(r.get("found")), "owns": SIBLINGS[name]["owns"]}
        if r.get("found"):
            entry["bin"] = r["bin"]
            entry["run"] = f"python3 scripts/siblings.py run {name} " \
                           f"{SIBLINGS[name]['marker']} -- <args>"
        else:
            entry["fallback"] = FALLBACKS[name]
        out["siblings"][name] = entry

    ve = out["siblings"]["video-editor"]
    if ve["found"] and args.deep:
        # video-editor's doctor.py prints human text, not JSON — read the verdict.
        try:
            p = subprocess.run([sys.executable, str(Path(ve["bin"], "doctor.py"))],
                               capture_output=True, text=True, timeout=120,
                               env=child_env())
            ve["doctor_ready"] = "READY" in p.stdout
            if not ve["doctor_ready"]:
                ve["doctor_tail"] = p.stdout.strip().splitlines()[-4:]
        except (OSError, subprocess.SubprocessError) as e:
            ve["doctor_ready"] = False
            ve["doctor_error"] = str(e)

    out["degraded"] = [n for n, v in out["siblings"].items() if not v["found"]]
    print(json.dumps(out, indent=2))
    return 0


FALLBACKS = {
    "video-editor": "ffmpeg concat + loudnorm. Draft quality: no subject-tracking "
                    "reframe, no dialogue chain, no captions, no QC. Say so.",
    "watch": "ffmpeg -vf fps=1 into a temp dir, then open the frames with the host's "
             "own image reading. Local files only, no transcript, no scene detection.",
    "film-director": "Direct it here as a long ad, or tell the user which skill owns it.",
}


def cmd_path(args) -> int:
    r = resolve(args.name)
    if not r.get("found"):
        print(json.dumps(r, indent=2), file=sys.stderr)
        return 3
    print(r["dir"] if args.which == "dir" else r["bin"])
    return 0


def cmd_run(args) -> int:
    r = resolve(args.name)
    if not r.get("found"):
        print(json.dumps({**r, "fallback": FALLBACKS.get(args.name)}, indent=2),
              file=sys.stderr)
        return 3
    script = Path(r["bin"], args.script)
    if not script.is_file():
        print(json.dumps({"error": "entry script missing", "expected": str(script),
                          "available": sorted(p.name for p in Path(r["bin"]).glob("*.py"))},
                         indent=2), file=sys.stderr)
        return 4
    cmd = [sys.executable, str(script), *args.rest]
    if args.dry_run:
        print(json.dumps({"would_run": cmd, "cwd": str(Path.cwd())}, indent=2))
        return 0
    try:
        return subprocess.run(cmd, env=child_env()).returncode
    except KeyboardInterrupt:
        return 130


def cmd_refresh(args) -> int:
    try:
        STATE.unlink(missing_ok=True)
    except OSError:
        pass
    return cmd_doctor(argparse.Namespace(refresh=True, deep=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("doctor", help="what is installed and what this host can do")
    s.add_argument("--refresh", action="store_true", help="ignore the cache")
    s.add_argument("--deep", action="store_true",
                   help="also run video-editor's own doctor (slower)")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("path", help="absolute directory of a sibling")
    s.add_argument("name")
    s.set_defaults(fn=cmd_path, which="dir")

    s = sub.add_parser("bin", help="directory that holds the sibling's scripts")
    s.add_argument("name")
    s.set_defaults(fn=cmd_path, which="bin")

    s = sub.add_parser("run", help="resolve and execute a sibling script")
    s.add_argument("name")
    s.add_argument("script")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("rest", nargs=argparse.REMAINDER,
                   help="arguments for the child, after --")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("refresh", help="forget cached locations and probe again")
    s.set_defaults(fn=cmd_refresh)

    args = ap.parse_args(argv)
    rest = list(getattr(args, "rest", []) or [])
    # argparse.REMAINDER swallows our own flags once they follow the script
    # name, so pull them back out instead of forwarding them to the child.
    if "--dry-run" in rest:
        rest = [a for a in rest if a != "--dry-run"]
        args.dry_run = True
    if rest and rest[0] == "--":
        rest = rest[1:]
    if hasattr(args, "rest"):
        args.rest = rest
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
