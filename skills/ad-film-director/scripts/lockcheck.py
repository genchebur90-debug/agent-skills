#!/usr/bin/env python3
"""
lockcheck — measure whether a candidate frame belongs to the same film as the
approved ones.

Why this exists
---------------
Style consistency is normally judged by eye, and the eye is unreliable about
exactly the things that betray a mismatched shot. Colour temperature is the
worst case: human vision adapts to absolute warmth within a second, so a shot
that is 20 points warmer than its neighbours looks fine alone and looks lifted
from another film the moment it is cut in.

So: derive the tolerance window from the frames the user has already APPROVED,
then test the candidate against it. The approved set is the source of truth —
not the style document. Style documents drift out of date and are written from
intention; approvals are evidence. When the two disagree, the approvals win and
the document gets corrected.

What this tool does NOT do
--------------------------
It cannot see composition. A lit backdrop appearing behind the subject, a prop
entering frame, a limb crossing into the reserved caption zone — none of these
move the colour statistics reliably, and all of them ruin a frame. Four separate
metrics were tried against a frame that had grown a forbidden warm backdrop and
all four passed it, because black corners coexist happily with a lit mid-band.

A PASS here means "the colour belongs to this film". It does not mean the frame
is approved. Look at the frame. Every time.

Usage
-----
    lockcheck.py --approved a.png b.png c.png --candidate new.png
    lockcheck.py --approved 'shots/approved/*.png' --candidate new.png
    lockcheck.py --approved a.png b.png                  # just print the window

    --reserve top|bottom|none   also measure the reserved caption zone (default none)
    --tolerance 0.15            pad around the approved spread (default .15)
    --json                      machine-readable output

Metrics, and why each one
-------------------------
brightness   mean luma of the LIT pixels only. Measuring the black surround too
             would just report how much black is in frame, which is a
             composition choice, not an exposure one.
temperature  mean(R) - mean(B) over lit pixels. Positive is warm. The single
             metric that most often exposes a shot from another session.
saturation   mean (max-min)/max per lit pixel. Catches "I removed the colour
             cast and removed the life with it".
blackness    share of pixels at or below luma 16. Composition, so it is reported
             as a soft note rather than a hard failure.
key_x/key_y  where the light sits, from the luma balance left/right and
             top/bottom. Reported, never enforced: light direction legitimately
             changes shot to shot — that is coverage. Temperature does not.

Heterogeneous approved sets
---------------------------
If the approved set mixes subject classes — skin frames alongside a bright
product-on-black frame, say — the window inflates and stops discriminating. A
pack shot once passed a window whose ceiling had been raised 15 points by a
single frame of a yellow lemon. The tool warns when a gated metric's spread is
unusually wide; when it does, split the set and compare like to like.

Exit code 0 if the candidate is inside every hard gate, 1 if not, so this can
gate a pipeline step.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:  # pragma: no cover
    sys.exit("lockcheck needs pillow and numpy: pip install pillow numpy")

Image.MAX_IMAGE_PIXELS = None

# Pixels darker than this are the black surround, not subject.
LIT_FLOOR = 28
# Pixels at or below this count as true black for the blackness metric.
BLACK_CEIL = 16
# Long edge the image is reduced to before measuring. Colour statistics are
# scale-invariant and this keeps a 4K frame under a millisecond.
SAMPLE = 400
# In the reserved zone, a pixel brighter than this will show through type.
RESERVE_CEIL = 32

GATED = ("brightness", "temperature", "saturation", "blackness")
# Outside the window here is a note, not a failure: it reflects composition.
SOFT = ("blackness",)
# Spread beyond this on a gated metric suggests the approved set mixes subject
# classes, so the window is too loose to mean anything.
WIDE_SPREAD = {"brightness": 45.0, "temperature": 28.0, "saturation": 28.0}


def measure(path: str | Path, reserve: str = "none") -> dict:
    """Return the look metrics for one frame."""
    im = Image.open(path).convert("RGB")
    im.thumbnail((SAMPLE, SAMPLE))
    a = np.asarray(im).astype(float)

    lum = a.mean(2)
    lit = lum > LIT_FLOOR
    if not lit.any():                       # frame is essentially all black
        lit = lum > 0

    px = a[lit]
    r, b = px[:, 0], px[:, 2]
    mx, mn = px.max(1), px.min(1)

    h, w = lum.shape
    left, right = lum[:, : w // 2].mean(), lum[:, w // 2 :].mean()
    top, bottom = lum[: h // 2, :].mean(), lum[h // 2 :, :].mean()

    def side(a_: float, b_: float, lo: str, hi: str) -> str:
        if a_ > b_ * 1.15:
            return lo
        if b_ > a_ * 1.15:
            return hi
        return "even"

    out = {
        "frame": Path(path).name,
        "brightness": round(float(lum[lit].mean()), 1),
        "temperature": round(float(r.mean() - b.mean()), 1),
        "saturation": round(float(100 * ((mx - mn) / np.maximum(mx, 1)).mean()), 1),
        "blackness": round(float(100 * (lum <= BLACK_CEIL).mean()), 1),
        "key_x": side(left, right, "left", "right"),
        "key_y": side(top, bottom, "top", "bottom"),
    }

    if reserve in ("top", "bottom"):
        band = lum[: h // 3] if reserve == "top" else lum[-(h // 3) :]
        out["reserve_zone"] = reserve
        out["reserve_dirty_pct"] = round(float(100 * (band > RESERVE_CEIL).mean()), 2)
        out["reserve_max"] = int(band.max())
    return out


def window(measured: list[dict], tolerance: float = 0.15) -> dict:
    """Tolerance window derived from the approved frames.

    The pad is a share of the observed spread, so a set that is already tight
    stays tight and a varied set is not punished for its variety. A metric with
    zero spread still gets a small absolute pad, otherwise one approved frame
    would make the window impossible to satisfy.
    """
    out = {}
    for k in GATED:
        vals = [m[k] for m in measured]
        lo, hi = min(vals), max(vals)
        pad = max((hi - lo) * tolerance, abs(lo) * 0.05, 2.0)
        out[k] = {
            "observed": [round(lo, 1), round(hi, 1)],
            "allowed": [round(lo - pad, 1), round(hi + pad, 1)],
            "mean": round(sum(vals) / len(vals), 1),
            "spread": round(hi - lo, 1),
            "soft": k in SOFT,
            "wide": (hi - lo) > WIDE_SPREAD.get(k, 1e9),
        }
    return out


def verdict(cand: dict, win: dict) -> tuple[bool, list[str]]:
    """True if the candidate is inside every hard gate. Notes explain misses."""
    ok, notes = True, []
    for k, spec in win.items():
        lo, hi = spec["allowed"]
        v = cand[k]
        if lo <= v <= hi:
            continue
        direction = "below" if v < lo else "above"
        delta = v - (lo if v < lo else hi)
        line = (f"{k}: {v} is {direction} the window [{lo}, {hi}] "
                f"by {abs(delta):.1f} (approved mean {spec['mean']})")
        if spec["soft"]:
            notes.append("note  " + line)
        else:
            notes.append("FAIL  " + line)
            ok = False

    if "reserve_dirty_pct" in cand:
        d, mx = cand["reserve_dirty_pct"], cand["reserve_max"]
        if d > 1.0:
            notes.append(f"note  reserved {cand['reserve_zone']} zone is not clean: "
                         f"{d}% of it is brighter than {RESERVE_CEIL} (peak {mx}). "
                         f"Type placed there will not read.")
    return ok, notes


def expand(patterns: list[str]) -> list[str]:
    """Accept literal paths and globs alike, so shell-quoted globs still work."""
    out: list[str] = []
    for p in patterns:
        hits = sorted(glob.glob(p))
        out.extend(hits or [p])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Check a candidate frame against the look of the approved set.")
    ap.add_argument("--approved", nargs="+", required=True,
                    help="approved frames — paths or globs. The source of truth.")
    ap.add_argument("--candidate", help="frame to test. Omit to just print the window.")
    ap.add_argument("--reserve", choices=("top", "bottom", "none"), default="none",
                    help="also measure the reserved caption zone")
    ap.add_argument("--tolerance", type=float, default=0.15,
                    help="pad around the approved spread, as a share of it (default .15)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    approved_paths = expand(args.approved)
    missing = [p for p in approved_paths if not Path(p).is_file()]
    if missing:
        return _die(f"approved frame not found: {', '.join(missing)}")
    if args.candidate and not Path(args.candidate).is_file():
        return _die(f"candidate not found: {args.candidate}")

    measured = [measure(p) for p in approved_paths]
    win = window(measured, args.tolerance)
    cand = measure(args.candidate, args.reserve) if args.candidate else None

    if args.json:
        print(json.dumps({"approved": measured, "window": win, "candidate": cand,
                          "pass": verdict(cand, win)[0] if cand else None}, indent=2))
        return 0 if (cand is None or verdict(cand, win)[0]) else 1

    hdr = f"{'frame':<22}{'bright':>7}{'temp':>7}{'sat':>7}{'black':>7}   key"
    print(hdr)
    print("-" * len(hdr))
    for m in measured:
        print(f"{m['frame']:<22}{m['brightness']:>7}{m['temperature']:>7}"
              f"{m['saturation']:>6}%{m['blackness']:>6}%   {m['key_x']}/{m['key_y']}")

    print(f"\nwindow from {len(measured)} approved frame(s), tolerance {args.tolerance:g}")
    for k, spec in win.items():
        flag = ""
        if spec["soft"]:
            flag = "  (soft — composition, not look)"
        elif spec["wide"]:
            flag = "  (WIDE — mixed subject classes? split the set)"
        print(f"  {k:<12} observed {spec['observed'][0]:>7} … {spec['observed'][1]:<7}"
              f"  allowed {spec['allowed'][0]:>7} … {spec['allowed'][1]:<7}{flag}")

    if any(s["wide"] and not s["soft"] for s in win.values()):
        print("\n  A wide spread means the approved set is not one visual family.\n"
              "  Compare like with like: skin frames against skin frames, product\n"
              "  frames against product frames. A window widened by an unrelated\n"
              "  frame will pass work it should have caught.")

    if not cand:
        return 0

    print(f"\n{'CANDIDATE':<22}{cand['brightness']:>7}{cand['temperature']:>7}"
          f"{cand['saturation']:>6}%{cand['blackness']:>6}%   {cand['key_x']}/{cand['key_y']}")
    ok, notes = verdict(cand, win)
    print()
    for n in notes:
        print("  " + n)
    print(f"\n  {'PASS — colour belongs to this film' if ok else 'REJECT — reads as a different film'}")
    if not ok:
        print("  Fix the colour with numbers, not with prompt wording: solve the\n"
              "  correction on a downscaled copy, apply it once at full resolution.\n"
              "  Prompt revisions move colour a couple of points and drag other\n"
              "  metrics out of window while they do it.")
    print("\n  A PASS is not an approval. This tool cannot see a lit backdrop, a\n"
          "  stray prop, or a limb in the caption zone. Look at the frame.")
    return 0 if ok else 1


def _die(msg: str) -> int:
    print(f"lockcheck: {msg}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
