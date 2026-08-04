# Measurement Discipline

Load when frames are being approved one by one, when a frame "looks off" and you
cannot say why, or before you try to fix a colour problem.

Everything here was learned the expensive way on a real campaign, in front of a
client, and each rule below is followed by the evidence that produced it. The
numbers are not illustrative — they are the actual measurements.

---

## Rule 1 — The window comes from the approved frames, not from your document

A style lock is written from intention, before the work exists. The approved
frames are evidence, produced after. When they disagree, **the frames win and
the document gets corrected.**

**What happened.** A campaign's style lock said, in writing: *"cold colour
temperature, rimming edges in bright silver."* Five frames had been approved.
Measured, every one of them was warm:

| approved frame | temperature (R−B) | saturation |
|---|---|---|
| 01 portrait | +58.2 | 54% |
| 02 lemon | +73.0 | 49% |
| 03 bottle | +46.5 | 43% |
| 04 mist | +38.5 | 34% |
| 05 jasmine | +46.1 | 46% |

Not one was cold. The document was wrong and had been wrong from the start.
Obeying it produced a frame at **+6.5 with 19% saturation** — 41 points of
temperature and 26 points of saturation outside the family. The client saw it
instantly: *"a different shadow."* He was right, and he was reading a fault the
written lock had instructed.

**Therefore:**

1. Derive the window numerically from the approved set. Do not assert it in
   prose. `scripts/lockcheck.py --approved <frames>` prints it.
2. Write the measured window into the lock, with the date and the number of
   frames it came from, and re-derive it whenever a frame is approved.
3. When a lock and the approvals disagree, fix the lock in the same turn you
   notice. A stale lock does not sit harmlessly — it actively steers work wrong,
   and it steers with authority.

**Direction is free, temperature is not.** Across those five frames the key came
from the left, the right, the top and the bottom. That is coverage, and it is
correct. Colour temperature is the opposite: human vision adapts to absolute
warmth within about a second, so a shot 20 points off looks fine alone and looks
lifted from another film the instant it is cut in. Enforce temperature. Never
enforce key direction.

---

## Rule 2 — Colour is fixed with numbers, not with prompt wording

`consistency.md` says grade the assembly, not the generations. This is the
operational form of that rule, and the arithmetic for why.

**What happened.** A finished frame had two colour faults: a magenta cast in the
rim light (+23.4 where the reference measured +11.9) and a colour balance that
needed roughly 18 points of movement. Two full prompt revisions were spent on
it, each with explicit, emphatic, numerically-named instructions.

| | rim magenta | frame temperature | verdict |
|---|---|---|---|
| start | +23.4 | +55.7 | wrong |
| after two prompt passes | +10.9 | **+69.3** | gate rejected it |
| after post correction | **+9.5** | **+54.5** | passed |

The prompt fixed the magenta but dragged the whole frame to +69.3 — eight points
past the window ceiling — so the net result was a worse frame. Prompt revision
cannot hold one channel while moving another; the model re-renders everything at
once.

The post correction hit three targets in two passes: rim magenta 23.3 → 9.5,
temperature +69 → +54.5, and the product's own colour back onto the reference
(+13.8 → +5.8 greenness against a reference +6.7).

**Therefore: the prompt decides WHAT is in the frame. Numbers decide its
colour.** Once a frame's content is right, stop prompting and correct.

**How to correct, practically.**

- Solve the coefficients on a **downscaled copy**, then apply once at full
  resolution. A grid search over float32 arrays at 3072×5504 will be killed for
  memory. Downscale to 400px, search, save the two or three numbers, apply.
- Apply channel gains with PIL's per-channel `point()` on split channels rather
  than building a full-size float array. Same result, a fraction of the memory.
- Global correction moves everything, including things you did not intend. After
  a global channel change, re-measure the object you care about: cutting red to
  cool a frame also pushed a green liquid 7 points greener than its reference,
  which then needed a masked correction back.
- Sequence: fix the global fault first, re-measure, then correct locally inside
  the object's mask.

---

## Rule 3 — A statistic cannot catch a lit backdrop. Only the eye can.

**What happened.** A frame grew a warm brown lit gradient behind the subject —
a fault the style lock forbids by name, in a line that exists because that exact
background had already been dropped once. Four metrics were tried against it:

| metric | approved range | the bad frame | caught it? |
|---|---|---|---|
| share of frame below luma 8 | 7–52% | 27% | no |
| mean of the darkest quarter | 0.2–11.9 | 0.9 | no |
| luma around the frame border | 15.8–63.0 | 33.1 | no |
| darkest background block | 0–6 | 0 | no |
| side strips, mid-height, median | 0–9 | **35** | yes — but false-positives when the subject fills the sides |

All four global metrics passed it, because black corners coexist perfectly well
with a lit mid-band. The one metric that caught it fires falsely on any frame
where a shoulder or an arm reaches the frame edge — which, in a portrait
campaign, is most of them.

**Therefore: the script and the eye cover different failure classes, and neither
substitutes for the other.**

| the script owns | the eye owns |
|---|---|
| temperature drift | a backdrop appearing |
| saturation loss | a prop entering frame |
| exposure mismatch | a limb in the reserved zone |
| a product's colour against its reference | scale and composition |
| whether a reserved zone is measurably clean | whether the gesture reads |

Say "the gate passed" and "I looked at it" as two separate statements, because
they are two separate checks. **A passing gate is not an approval.** Presenting
a gate result as an approval is how a forbidden backdrop reaches a client.

---

## Rule 4 — Measure inside the object's mask, never inside a guessed box

**What happened.** A crop box was placed by eye over "where the bottle is" and
used to measure the perfume's colour. It reported the liquid as dark and olive.
Acting on that, the next generation was asked for a lighter, fresher liquid.

Measured properly — inside a mask built from the liquid itself — the liquid was
already **brighter than the reference**: 117.7 against 112.0. The crop box had
been sitting mostly on the model's chest. The real fault was somewhere else
entirely: the rim magenta at +23.4 against +11.9.

So a wrong measurement produced a confident wrong diagnosis, which produced a
wasted generation aimed in the wrong direction. **A diagnosis from a bad
measurement is worse than no diagnosis** — no diagnosis leaves you looking, a
wrong one sends you away with false certainty.

**How to build a mask.** Find a property that separates the object from its
surroundings, then clean it up:

```python
# A pale green liquid against brown skin. Greenness separates them cleanly:
#   inside the liquid  G - (R+B)/2  ≈  +7
#   on skin            G - (R+B)/2  ≈  -19
green = G - (R + B) / 2
raw = ((green > 1.5) & (lum > 25))
# then: dilate to close gaps, blur for a soft edge, threshold, and CHECK the
# coverage is plausible before trusting a single number that comes out of it
```

Other separators that work: hue for a coloured product against neutral
surroundings, luminance for a backlit object against black, saturation for a
brand colour against skin. If nothing separates the object numerically, say so
and judge it by eye — do not invent a box.

**Always report the coverage.** A mask covering 0.1% or 60% of the frame is
broken, and a number derived from a broken mask is worse than no number.

---

## Rule 5 — Measure the reserved zone, do not eyeball it

Titles, logos and captions need genuinely black space, and "looks dark enough"
is not a judgement the eye makes well against a bright type overlay.

The check is one line: the share of the reserved band brighter than luma 32, and
its peak. Real results from one campaign's final frames:

| frame | reserved top third | verdict |
|---|---|---|
| bare product on black | 0.00% dirty, peak 5 | type will sit perfectly |
| model, pulled back | 4.3% dirty, peak 118 | usable, type shifts off centre |
| model, framed close | 22.3% dirty, peak 185 | **type will not read** |

`lockcheck.py --reserve top` reports it alongside the colour gate. Run it before
promising a client that a title fits, not after the frame is approved.

And state the reservation in the prompt in the negative, as `consistency.md`
Part 4 requires — models fill space, and an unreserved zone will acquire
something bright precisely where the type was going.

---

## Rule 6 — Measure what the fix COSTS, not only what it removes

This is the most expensive lesson in this file, and the one most easily skipped,
because a correction that improves its target feels like a success.

**What happened.** Faint horizontal banding was detected in generated clips. Over
several hours the filter went through four versions, three metrics and a per-tile
spectral analysis. Each version drove the banding number down and each was reported
as progress. Then the client said the clips "don't look like 1080p".

One measurement settled it:

| | sharpness |
|---|---|
| raw clip from the model | **4.76** |
| after the banding filter | **2.59** |
| container re-encode only, no pixel processing | **4.73** |

**The filter was destroying 46% of the image detail to remove an artifact the client
had called "barely noticeable".** He was not seeing the banding. He was seeing the
cure. The entire effort was net negative and nobody knew, because only one side of
the trade was ever measured.

**Therefore: every correction reports two numbers — how much of the fault it removed,
and how much of something else it destroyed.** A filter that improves its target and
is silent about its collateral is not verified, it is unexamined.

Standard collateral metrics, cheap to compute, worth running on every pass:

- **sharpness** — mean absolute neighbour difference over the frame. Any spatial
  filter will move this. If it drops more than a few percent, stop.
- **modelling** — standard deviation of heavily blurred luminance over the subject.
  This is form and light. Smoothing that flattens it has killed the subject.
- **colour** — temperature and saturation before and after. Channel operations leak.

### Know when to accept the fault

The corollary, and the harder discipline: **some artifacts should be accepted, not
fixed.** Post-processing is not free, and an artifact that costs less than its cure
should be left alone.

Before building any correction, ask what the fault actually costs at delivery size,
on the delivery device. Faint banding at 4K that is invisible on a phone is not worth
a single percent of sharpness. The instinct to fix everything detectable is the same
instinct that optimises a metric into a worse film.

---

## Rule 7 — When the client's eye and your metric disagree, the metric is wrong

The client said the stripes were still visible. Five different detectors were built
and each reported the clip clean. Each time the detector was believed.

That was backwards every time. **The client is looking at the actual delivered file
on the actual device. A metric is a hypothesis about what is visible.** When they
disagree, the default assumption is that the hypothesis is incomplete — not that the
client is mistaken.

Each of those five detectors was in fact wrong in a specific way, and each failure
was the same shape: the sample did not match the viewing condition.

| what was measured | what the client saw |
|---|---|
| frame 1 of the clip | the fault was worst at frame 97 |
| the average over the frame | the fault was in the worst local patch |
| a crop box placed by eye | the box was sitting on the wrong object |
| full 4K resolution | the client was watching downscaled on a phone |
| a ratio of peak to noise floor | on near-black areas that ratio inflates meaninglessly |

**Therefore: verify in the delivery condition.** The resolution it will be watched at,
the worst frame of the whole clip, the actual region in question — and say out loud
which sample was used, so the gap is visible when it exists.

And when the client insists after a clean measurement, the next move is never to
re-run the same measurement. It is to ask where they see it, or to change the sample.

---

## Symptom index

| The client says | Measure this first |
|---|---|
| "still visible" after you measured it clean | nothing — change the sample. Rule 7. |
| "doesn't look like 1080p", "looks soft" | sharpness before and after your own processing. Rule 6. |
| "different shadow", "another light", "looks like another film" | temperature against the approved window |
| "washed out", "lifeless", "grey" | saturation against the approved window |
| "the background is strange" | nothing — look at it. Rule 3. |
| "the product's colour is wrong" | the product inside a mask, against the real product photograph |
| "the title doesn't fit / can't be read" | the reserved zone, `--reserve` |
| "it looks cheap" | nothing — this is composition and restraint, not a statistic |

---

## The order of operations

1. **Content first, by eye and by prompt.** Is the right object in the frame,
   doing the right thing, with the label present and legible?
2. **Then the gate.** `lockcheck.py` against the approved set of the same
   subject class.
3. **Then look at it again**, for everything the gate cannot see.
4. **Then correct colour with numbers**, if the gate found drift.
5. **Then re-measure the object**, because a global correction moved it too.
6. **Measure the collateral** — sharpness and modelling before and after every
   correction. A fix that costs more than the fault is a regression. Rule 6.
7. Only then show it — and say which checks you actually ran, and on which sample.

If the client disagrees after all of that, the measurement was wrong, not the client.
Change the sample before changing the frame.

Reversing steps 1 and 4 is the common failure: fixing colour by prompt while the
content is still wrong burns generations and moves the colour two points at a
time.
