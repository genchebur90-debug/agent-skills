# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is [semantic](https://semver.org/spec/v2.0.0.html).

## 1.5.0 — 2026-08-04

Consistency stops being advice and becomes a mechanism, and delegation stops depending on
shell variables that no host keeps alive.

The reported failure was specific: across a fragrance campaign the recurring model held and
the product did not — wrong flacon, missing logo, forgotten cap. The cause was an asymmetry
in the toolchain rather than a gap in the writing. A character stored `prompt_lock`, `seed`,
`wardrobe` and `lighting`, and that text was pasted into every prompt; a product stored a
folder of photographs and a sentence of advice, so by shot eight the bottle was being
described from memory — the one thing `production-order.md` forbids and nothing checked.

### Added

- **`references/identity-spec.md`** — what "the same product" means per family: pack, food,
  vehicle, space, apparel, device, screen, service, person. Four questions in Phase 1, three
  to six features, and the failure mode each family actually has. A burger has no label and a
  car has no cap; "is the product still the product?" was unanswerable as written.
- **Product identity in the registry.** `campaign.py add-product` now takes `--profile`,
  `--identity`, `--label-lines`, `--closure`, `--colour`, `--material`, `--must`, `--forbid`,
  `--prompt-lock`, `--seed`. New commands: `product` (record plus the gaps it still has),
  `profiles`, `lockcard`, `verify`.
- **`campaign.py lockcard`** — the identity block that travels with the shot. `packet.py`
  embeds it on every page, so the person generating can tell a correct flacon from a
  plausible one. It sits *beside* the prompt: putting its words in the prompt body would be
  the second description of the object, which is the drift itself.
- **`campaign.py verify`** — the per-clip check as fields that start `UNCHECKED`. A question
  with no field gets skipped, and that is why the wrong bottle ships.
- **`scripts/planlint.py`** — the production-order laws, enforced. Errors on: a locked thing
  with no parent plate, text-to-video for a locked shot, a parent that is another shot's
  output, two locked things in one frame, a product missing from the registry or missing its
  photograph, a prompt asking for an unbranded pack. Warns on over-long locked clips,
  grading or lettering in the prompt, a reserved zone with no preservation clause, and a
  prompt that re-describes a locked product. `packet.py` and `generate.py` run it and refuse;
  `--force` exists and every use is a decision to ship known drift.
- **`scripts/identity.py`** — `sheet` builds the plate-beside-candidate comparison image,
  `check` reports advisory numbers (interior luminance, proportions, detail density) that
  catch a milky fill, a normalised silhouette and a vanished label. Neither is a verdict; the
  point is to make the honest comparison cheap enough that it happens.
- **`scripts/siblings.py`** — resolves and runs `watch`, `video-editor` and `film-director`
  on any host, caching to `.campaign/siblings.json` and wiring the child environment
  (including `VE_DIR`, which `montage.py` needs for beat detection).
- **`references/fleet.md`** — the fleet detail extracted out of `SKILL.md`.
- **`SKILL.md` §0b, the production contract** — seven lines that hold the whole discipline,
  meant to survive a long context, plus §0c: the three commands that start work on any host.

### Changed

- **One spelling of the plan schema.** `parents` and `locks` are canonical; `reference`,
  `references`, `reference_images` and friends still load. Every script reads the plan
  through `planlint.normalize_plan`, so a reference can no longer be attached by one script
  and dropped by the next — which it silently was, between `packet.py` and `generate.py`.
- **`references/delegation.md`** rewritten around `siblings.py`. The old detection block
  exported `VE_DIR` and `WATCH_BIN` and asked the agent to remember them; on hosts where each
  tool call is a fresh process — which is most of them — every later command ran against an
  empty path. Also corrected the claim that every `video-editor` script prints JSON:
  `doctor.py` prints text.
- **Host-neutral language.** Frames are opened with "whatever image input your host provides"
  rather than a named tool, and a host that cannot show images is told to say so instead of
  claiming to have reviewed the footage.
- `SKILL.md` frontmatter description brought under the 1024-character limit that some hosts
  enforce, where it had been silently rejecting the skill on install.
- `compatibility` corrected: the scripts use 3.10+ syntax; the old "Python 3.8+" was wrong.

## 2026-07-31

Seedance 2.0's real input contract, verified instead of assumed. Written down because guessing
at a model's limits produces invented restrictions, and invented restrictions quietly delete the
technique the user came for. Two of them had already been stated out loud in a live session
before being checked.

### Added

- `references/platforms.md` — **"Seedance 2.0 — verified input contract"**. Mixed-modality input
  in a single call, addressed by `@` handles from inside the prompt: up to **9 images**
  (`@Image1`…), **3 video clips** (`@Video1`…, 2–15s combined), **3 audio clips** (`@Audio1`…,
  ≤15s, mp3/wav). Two entry modes, first/last frame and universal reference. Output 4–15s, six
  aspect ratios, native ceiling **2K** with 4K promised later — so an aggregator offering `4k`
  risks top rate for an upscale.
- The same section records **what ByteDance itself names as still weak**, which is more useful
  than any strength list: multi-subject *consistency* (interaction is a strength, holding two
  identities is not), **text rendering accuracy**, and complex editing effects.
- Delivery difference by route, which had already caused a wrong conclusion: consumer UIs take
  local files by drag and drop, the aggregator API accepts **public HTTPS URLs only**. A plate
  behind an authenticated URL never arrives, and the symptom reads as "the model won't accept
  images."
- `references/platforms.md` capability map gains three rows: beat-landing changes → audio
  reference input; an exact movement → video reference input; several looks on one subject →
  many image slots in one call.

### Changed

- `references/production-order.md` — the Seedance paragraph replaced with the three-reference
  table, and one instruction reversed. It previously said to leave audio off and score in the
  edit. That is right for *generated* audio and wrong as a whole: **passing the real track as
  `@Audio1` moves beat-sync into the generation**, which for an outfit-change or any 卡點-style ad
  is the entire trick. Post-hoc `--beat-sync` is now documented as the fallback, not the method.
  Likewise a movement passed as `@Video1` carries real physics, where described motion is
  reinvented on every run.
- `references/platforms.md` — the Seedance landscape note rewritten from "technically strong but
  restricted" to the current picture, keeping the licensing and regional caution, since a
  vendor's own commercial-use claim is not a legal clearance.

### What produced this

Two capability claims were asserted in a live session without being checked, and both were
wrong in a way that cost the user options:

- "Seedance can't be trusted with UI elements, composite them in post." The caution turned out
  to be defensible, but for a different reason — ByteDance's own evaluation names text rendering
  as weak. A cursor is not text, and the honest answer is one cheap test, not a prohibition.
- "A boy and a girl in one frame won't work." Multi-subject interaction is a headline strength.
  The real risk is identity drift, which is a design tradeoff, not a wall.

The audio-reference input was missed entirely, and it was the single most valuable field for the
job at hand. **A capability claim about a model belongs in this file only after the schema or the
vendor's documentation has been read.**

### Note on versioning

The frontmatter still reads `1.4.0`. Two dated entries — 2026-07-30 and this one — have landed
since, following the dated convention the previous entry established. Both are unreleased with
respect to semver; the next bump should cover them together.

## 2026-07-30

Measurement discipline, learned across a full still-approval cycle on a live campaign. Every
rule below carries the measurements that produced it, because a rule without its evidence gets
argued with.

### Added

- `references/measurement.md` — five rules. The look window is **derived from the approved
  frames**, never asserted in a style note. Colour is corrected **with numbers**, because prompt
  revision cannot hold one channel while moving another. **No global statistic catches a lit
  backdrop**, so the script and the eye own different failure classes and neither substitutes for
  the other. Measurement happens **inside an object mask**, never inside a crop box placed by
  eye. A reserved caption zone is **measured, not judged**. Plus a symptom index from what the
  client says to what to measure first, and the order of operations.
- `scripts/lockcheck.py` — derives a brightness / temperature / saturation / blackness window
  from the approved frames and gates a candidate against it. Reports key direction without
  enforcing it, since direction is coverage and temperature is not. Warns when the approved set
  mixes subject classes and the window has stopped discriminating: a pack shot once passed a
  ceiling raised 15 points by a single frame of a yellow lemon. `--reserve top|bottom` measures
  the caption zone alongside the colour gate. Prints, on every run, that a PASS is a colour
  result and not an approval.

### Changed

- `references/consistency.md` — the blank-product rule restored and expanded. The label is the
  product; a garbled logo is fixable, an absent one means you photographed the wrong product.
  A complete product includes its closure — a missing cap reads as a product in use, not
  presented. And transparent liquid transmits rather than glows: asking for a backlit luminous
  fill produces frosted plastic, with the interior-luminance figures that separate the two
  (reference 112, correct 118, the two failed "luminous" attempts 176 and 191).
- `SKILL.md` — Phase 6 gains the per-frame gate with its command; Phase 7 gains the
  correct-with-numbers rule and the arithmetic behind it; the scripts table and the reference
  index gain the new files.
- `SKILL.md` §9 gains four failure modes: trusting your own style notes over the approved
  frames, fixing colour by rewording the prompt, reporting a passing gate as an approval, and
  diagnosing from a crop box placed by eye.

### The evidence, briefly

- A style lock said "cold colour temperature". All five approved frames measured warm, +38 to
  +58. Obeying the lock produced a frame at +6.5 with half the set's saturation, rejected on
  sight. The document had been wrong from the start and was steering work with authority.
- Two emphatic prompt passes aimed at a colour fault moved it 2 points of the 18 needed and
  pushed the frame's temperature to +69.3, eight points past the ceiling. A post correction hit
  three targets in two passes.
- A forbidden warm backdrop appeared behind a subject. Four metrics were tried: share of frame
  below luma 8, mean of the darkest quarter, border luma, darkest background block. All four
  passed it, because black corners coexist with a lit mid-band.
- A crop box placed "roughly over the bottle" reported the liquid as dark and olive. Measured
  inside a proper mask it was brighter than the reference, 117.7 against 112.0 — the box had
  been sitting on the model's chest, and the real fault was elsewhere.

## [1.4.0]

Production order. The skill knew what had to stay identical but not in what order
things get made — which is what actually decides whether they do. Video is always
made from references; this release writes that down as a sequence.

### Added

- `references/production-order.md` — the shot ledger (in/out/length/what is locked
  in frame/parent plates/camera/route) as the bridge between analysing a reference
  and generating anything; deriving the lock list from the ledger instead of
  guessing; the four tiers (locks → composites → one approved shot plate per shot →
  video from that plate → edit); and model routing keyed to how many locked things
  a shot has in frame.
- **The one law:** every generation names its parents, and each thing is described
  in words exactly once — a character in its portrait, a location in its plate, a
  product never, because a product comes from a photograph. A second shot in the
  same room inherits the first room frame rather than a second description of it.
- `SKILL.md` Phase 6 now opens with order before prompts, and the reference table
  points at the new file.
- Verified model routing against the live magica catalogue (July 2026) with real
  ids and price tiers: `seedance-2.0-reference-to-video` and its fast variant for
  anything with a locked character or product, `kling-v3-pro-image-to-video` for a
  single approved plate with a strong camera move, `kling-v3-pro-text-to-video`
  only where nothing is locked, `kling-v3-pro-motion-control` for transferring a
  movement onto a locked character.
- Two failure modes: prompts written before the ledger exists, and describing a
  recurring thing a second time.

### Notes

- Minimum clip length is a model constraint, not a target: a 1.8-second shot is
  generated at the model's 4-second floor and trimmed in the edit.
- Stills are where composition gets decided, because a still costs a fraction of a
  video second and the agent host renders them for free.
- Text-to-video cannot hold a character. That is a capability boundary, not a
  prompt-quality problem.

## [1.3.0]

Learning layer. The skill can now be taught by example: the user shows an ad they
like, the skill measures it instead of admiring it, and a technique that proves
itself is written into the file that owns it. Purely additive — no existing
behaviour changes.

### Added

- `references/reference-ledger.md` — intake protocol for reference ads; a lookup
  table translating what the user says ("dynamic", "looks expensive", "great with
  the music") into what to actually measure and which file owns the answer; the
  applicability test; the promotion threshold; the observation-card format; a
  promotion index; an antipattern section.
- `SKILL.md` §7 "Learning from the ads you're shown" — the short protocol plus the
  three rules that stop the ledger from corrupting the skill. Former §7 and §8
  renumbered to §8 and §9.
- Phase 1 routes a handed-over reference ad into the intake instead of an eyeball
  pass. Phase 7 gains a sixth check: measure your own cut with `montage.py` and
  compare it against the reference's numbers.
- `references/consistency.md` — explicit precedence when a style lock and a learned
  pattern disagree: lock, then the user's word, then a promoted pattern, then
  defaults.
- Three failure modes: admiring a reference instead of measuring it, promoting a
  lesson from a single ad, letting a learned pattern override a project lock.

### Notes

- Promoted rules live in the file that owns them (`script-craft.md`,
  `product-artdirection.md`, `creative-registers.md`, `consistency.md`), tagged
  `[REF-nnnn]` so a bad lesson can be traced and removed. The ledger holds
  observations and the audit trail, not doctrine.
- Promotion needs two independent references or the user's explicit word. One ad is
  an anecdote.

## [1.2.0]

Infrastructure. The fleet layer stops knowing platform names and starts reading
data, so any user's set of tools fits without touching code. Purely additive:
every existing `fleet.yaml` keeps working unchanged.

### Fleet

- `access: host` — a route where the agent's own environment renders the shot.
  No API key, no browser step, none of the user's platform credits. Marker `HOST`.
- `protocol:` on a platform declares the SHAPE of its API (`magica-like`,
  `fal-like`, `heygen-like`, `host`) instead of the backend being keyed by
  platform id. A new service that speaks a known shape is a config block and
  zero code. Platform ids remain as aliases.
- `subscription:` block per platform — `plan`, `seats`, `cost_per_month_usd`,
  `credits_per_month`, `resets`, `renews_on`, `verified_on`, `balance_source`.
  All fields optional.
- `models:` per platform, which makes host-overlap detection possible.
- `fleet.py inventory` — one answer to "what AI tooling do I own?": plans, seats,
  pools, percentages, reset dates, access class. Three warning classes:
  credits about to expire unused, a hand-typed balance that has gone stale, and
  a paid model the host already renders for free.
- `preferences.balance_stale_after_days` and `preferences.expiry_warn_days`.
- `mode()` reports AUTONOMOUS when a host renderer exists, not only on an API key.
- Setup interview asks about credit resets and balances, and documents that
  adding a platform later never requires code.

### Generation

- `HostBackend` — emits a render order (`tool`, `args`, `save_as`) rather than
  making HTTP calls, because host tools live in the agent's runtime. Writes to the
  same `inbox/<shot>.<ext>` contract `packet.py` uses, so assembly cannot tell how
  a clip arrived. Threads `firstFrameImage`, `referenceImages`, `voice`, `avatarId`.
- Backend resolution goes through `resolve_backend_class()`: protocol first, id as
  a legacy alias, `None` → routed to the manual path instead of failing.

### Fixed

- The built-in YAML fallback parser (used when PyYAML is absent) silently
  truncated flow lists that wrapped across lines — `[a, b,\n c, d]` parsed as
  `['[a', 'b']`, losing entries with no error. Wrapped lists are now folded
  before parsing.

### Documentation

- `SKILL.md`: run `inventory` first; how to read each warning class; a routing
  table ranking host / api / ui / api-paid; render orders explained. Rule 1 still
  applies to free host shots.
- `references/platforms.md`: the overlap trap and the three ceilings that justify
  paying anyway (resolution, clip length, a model the host lacks); credit-expiry
  and displayed-price-vs-actual-bill warnings.
- `references/delegation.md`: measuring a reference with `montage.py` instead of
  describing it; caption presets per register; sibling detection now finds skills
  sitting next to this one.

## [1.1.0]

Concept slates. Phase 2 becomes 2a claim → 2b slate → 2c lock.

- Ten creative registers, up from four: added process/craft documentary,
  mockumentary, retro pastiche, sensory/ASMR, hyper-stylised graphic,
  absurdist/surreal
- The conventionality dial, for spreading a slate deliberately
- Where concepts come from: five axes of product interrogation
- Category clichés to avoid
- Slate rules: 3-5 concepts, one register each, deliberate variance spread, one
  solid obvious idea, one genuinely non-obvious, no rigged slates
- `script-craft.md`: Making Sequence and Format Borrow structures
- `campaign.py --register` accepts all ten registers

## [1.0.0]

First release. Seven phases, the Routing Gate, fleet layer with account rotation,
campaign registry, delegation to `video-editor` and `watch`.
