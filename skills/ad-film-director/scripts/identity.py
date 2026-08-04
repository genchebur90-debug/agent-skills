#!/usr/bin/env python3
"""
identity.py — put the candidate next to the plate so the drift becomes visible.

Why this exists
---------------
lockcheck.py answers "does this frame's colour belong to this film". It says so
itself: it cannot see a wrong label, a missing cap or a bottle that has quietly
become a different shape. Those are the failures that make an ad unusable, and
they were left to the agent noticing them while reviewing frames one at a time
— which is exactly the condition under which nobody notices. A frame looks
right on its own. It only looks wrong beside the real product.

So this builds the comparison: one image, plate on the left, candidates to the
right, at matched height. The agent then reads that single image and answers
the fields from `campaign.py verify`. The numbers below are advisory support,
never a verdict.

There is no model here and no claim of automatic verification. The tool's whole
job is to make the honest check cheap enough that it actually happens.

Usage
-----
    identity.py sheet --plate plate.jpg --candidates f1.png f2.png --out sheet.png
    identity.py sheet --plate plate.jpg --candidates clip.mp4 --at 1.5 --out sheet.png
    identity.py check --plate plate.jpg --candidate f1.png
    identity.py check --plate plate.jpg --candidate f1.png --box 120,300,400,600

Exit codes: 0 done, 1 bad input, 2 missing dependency.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw
    import numpy as np
except ImportError:                                    # pragma: no cover
    sys.exit("identity.py needs pillow and numpy: pip install pillow numpy")

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".avi"}
PANEL_H = 720
PAD = 16
BG = (18, 18, 18)
INK = (235, 235, 235)
LIT_FLOOR = 28


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

def as_image(path: str, at: float = 0.0) -> Image.Image:
    """Open a still, or pull one frame out of a clip."""
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"not found: {path}")
    if p.suffix.lower() not in VIDEO_EXT:
        return Image.open(p).convert("RGB")
    if not shutil.which("ffmpeg"):
        raise SystemExit(f"{path} is a video and ffmpeg is not on PATH — "
                         "extract a frame yourself and pass the image")
    tmp = Path(tempfile.mkdtemp()) / "frame.png"
    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(p),
                    "-frames:v", "1", str(tmp)], check=True)
    return Image.open(tmp).convert("RGB")


def parse_box(spec: str | None, size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    if not spec:
        return None
    try:
        x, y, w, h = (int(v) for v in spec.split(","))
    except ValueError:
        raise SystemExit("--box wants x,y,w,h in pixels")
    return max(0, x), max(0, y), min(w, size[0]), min(h, size[1])


# ---------------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------------

def panel(im: Image.Image, caption: str) -> Image.Image:
    r = im.copy()
    r.thumbnail((PANEL_H * 2, PANEL_H))
    out = Image.new("RGB", (r.width, r.height + 28), BG)
    out.paste(r, (0, 0))
    ImageDraw.Draw(out).text((6, r.height + 8), caption[:70], fill=INK)
    return out


def cmd_sheet(args) -> int:
    plate = panel(as_image(args.plate), f"PLATE — {Path(args.plate).name}")
    panels = [plate]
    for c in args.candidates:
        panels.append(panel(as_image(c, args.at), f"candidate — {Path(c).name}"))

    w = sum(p.width for p in panels) + PAD * (len(panels) + 1)
    h = max(p.height for p in panels) + PAD * 2
    sheet = Image.new("RGB", (w, h), BG)
    x = PAD
    for i, p in enumerate(panels):
        sheet.paste(p, (x, PAD))
        x += p.width + PAD
        if i == 0:                       # a rule between plate and candidates
            ImageDraw.Draw(sheet).line([(x - PAD // 2, 0), (x - PAD // 2, h)],
                                       fill=(90, 90, 90), width=2)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)

    print(json.dumps({
        "sheet": str(out),
        "panels": len(panels),
        "next": "open this image and answer the fields from "
                "`campaign.py verify --product <name>`",
        "look_for": ["label wording and line order", "logo shape and position",
                     "closure present", "silhouette and proportions",
                     "colour and finish of the product itself",
                     "anything on the never-list"],
        "warning": "a candidate that merely looks plausible is the failure mode. "
                   "Compare, do not admire.",
    }, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Advisory numbers
# ---------------------------------------------------------------------------

def stats(im: Image.Image, box=None) -> dict:
    if box:
        x, y, w, h = box
        im = im.crop((x, y, x + w, y + h))
    im = im.copy()
    im.thumbnail((480, 480))
    a = np.asarray(im).astype(float)
    lum = a.mean(2)
    lit = lum > LIT_FLOOR
    if not lit.any():
        lit = lum > 0

    px = a[lit]
    mx, mn = px.max(1), px.min(1)
    ys, xs = np.nonzero(lit)
    bw = max(1, int(xs.max() - xs.min()))
    bh = max(1, int(ys.max() - ys.min()))

    # Vertical gradient magnitude of the subject: a rough stand-in for how much
    # structure (type, seams, facets) survives. A blank pack reads far lower
    # than a labelled one shot the same way.
    g = np.abs(np.diff(lum, axis=0)).mean()

    return {
        "interior_luminance": round(float(lum[lit].mean()), 1),
        "temperature": round(float(px[:, 0].mean() - px[:, 2].mean()), 1),
        "saturation": round(float(100 * ((mx - mn) / np.maximum(mx, 1)).mean()), 1),
        "subject_aspect": round(bw / bh, 3),
        "detail_density": round(float(g), 2),
        "lit_share_pct": round(float(100 * lit.mean()), 1),
    }


THRESHOLDS = {
    "interior_luminance": (25.0, "the fill has changed character — the classic case "
                                 "is a transparent liquid rendered milky, which "
                                 "measures 60-90 points brighter than the reference"),
    "subject_aspect": (0.18, "the object's proportions moved: the model has "
                             "normalised an unusual shape toward a familiar one"),
    "detail_density": (0.35, "structure lost or invented — most often the label or "
                             "the type has gone, which means the wrong product"),
    "temperature": (18.0, "the product's own colour drifted; fix in the grade, not "
                          "by rewording the prompt"),
}


def cmd_check(args) -> int:
    plate_im = as_image(args.plate)
    cand_im = as_image(args.candidate, args.at)
    p = stats(plate_im, parse_box(args.plate_box, plate_im.size))
    c = stats(cand_im, parse_box(args.box, cand_im.size))

    notes = []
    for key, (limit, why) in THRESHOLDS.items():
        delta = c[key] - p[key]
        rel = abs(delta) / max(abs(p[key]), 1e-6) if key in ("subject_aspect",
                                                             "detail_density") else abs(delta)
        if rel > limit:
            notes.append({"metric": key, "plate": p[key], "candidate": c[key],
                          "delta": round(delta, 3), "means": why})

    print(json.dumps({
        "plate": p,
        "candidate": c,
        "flags": notes,
        "verdict": "LOOK CLOSELY" if notes else "no numeric red flag",
        "hard_truth": "These numbers cannot read a label, count a cap or spot the "
                      "wrong variant. A clean result here is not approval. Build the "
                      "sheet and look: identity.py sheet --plate ... --candidates ...",
    }, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare a candidate frame with the "
                                             "product plate.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sheet", help="build the side-by-side comparison image")
    s.add_argument("--plate", required=True, help="canonical product/character plate")
    s.add_argument("--candidates", nargs="+", required=True,
                   help="frames or clips to compare against it")
    s.add_argument("--at", type=float, default=1.0,
                   help="seconds into a clip to sample (default 1.0)")
    s.add_argument("--out", default="identity_sheet.png")
    s.set_defaults(fn=cmd_sheet)

    s = sub.add_parser("check", help="advisory numbers for one candidate")
    s.add_argument("--plate", required=True)
    s.add_argument("--candidate", required=True)
    s.add_argument("--box", help="x,y,w,h of the product inside the candidate")
    s.add_argument("--plate-box", help="x,y,w,h of the product inside the plate")
    s.add_argument("--at", type=float, default=1.0)
    s.set_defaults(fn=cmd_check)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
