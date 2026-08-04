# Production Order — assets before video

Load in Phase 6, before writing a single shot prompt. `consistency.md` says what must stay
identical; this file says **in what order things get made**, which is what actually decides
whether they stay identical.

## The one law

**Every generation names its parents.** A generation with no parent is only allowed when it is a
lock being created from a real photograph, or the one deliberate canonical image of a character
or set. Everything else inherits.

Its practical form, and the rule to repeat out loud when a shot list is being written:

> **Each thing is described in words exactly once.** A character once, in its canonical portrait.
> A location once, in its establishing plate. A product **never** — it comes from a photograph.
> After that first time, that thing only ever enters a prompt as an *image*.

The second shot in the same kitchen does not get a fresh description of the kitchen. It gets the
first generated image of that kitchen as an input. A described location drifts; a referenced
location cannot.

---

## Step 1 — Break the reference into scenes

Measure first, with `watch` and `montage.py` (commands in `delegation.md`). Then write the shot
ledger — this table is the bridge between analysis and generation, and nothing gets generated
until it is filled:

| # | In | Out | Len | Locked in frame | Parent plates | Camera | Route |
|---|---|---|---|---|---|---|---|
| 1 | 0.00 | 1.83 | 1.8s | chef, kitchen | `chef-in-kitchen` | floor-level wide, static | ref-to-video |
| 2 | 1.83 | 6.00 | 4.2s | chef, patty | `chef-sheet`, `patty-plate` | low, slow push | ref-to-video |
| 3 | 6.00 | 7.80 | 1.8s | product only | `bun-plate` | tabletop macro, static | image-to-video |

**Locked in frame** is the column that decides cost and route. Count the things that must be
recognisably the same as elsewhere in the film:

- **0 locked things** → text-to-video is fine, and it is the cheapest route available.
- **1 locked thing** → reference-to-video or image-to-video, from that thing's plate.
- **2 or more locked things in one frame** → no current model holds this reliably. Split the
  shot, or accept that one of them is out of focus or out of frame. Deciding this here costs
  nothing; discovering it after six failed generations costs real money.

**Length note:** models have a minimum clip length (Seedance starts at 4s). A 1.8-second shot is
generated at the minimum and **trimmed in the edit**. Never try to prompt a shorter clip.

---

## Step 2 — Derive the lock list from the ledger

Read down the *Locked in frame* column and you have exactly the plates you need. Not more.

- A human or mascot appears in more than one shot → **character sheet required**.
- A human appears in exactly one shot → no sheet; the shot plate is enough.
- The same room appears in more than one shot → **location plate required**.
- The product appears at all → **product plate required, from a real photograph**.
- A prop recurs and reads clearly → plate it too.

Building locks nobody needs is the second most common way to waste a budget. The first is not
building the ones you do.

### The ledger becomes plan.json, and the plan is checked

The ledger above is what a human reads; `plan.json` is the same table in the form the scripts
read. Two fields carry the law:

```json
{
  "project": "perfume-noir",
  "shots": [
    {
      "id": "s3",
      "note": "hero, slow push",
      "need": "reference-to-video",
      "seconds": 4,
      "locks":   ["product:noir-50"],
      "parents": ["plates/s3_first_frame.png", "plates/noir50_34.png"],
      "prompt":  "slow 85mm push in on the flacon from @Image1, black surround…",
      "negative": "the lower third stays dark and empty throughout, no light creep",
      "reserve": "bottom"
    }
  ]
}
```

- **`locks`** — what must be recognisably the same as elsewhere. Prefix with the kind:
  `product:`, `character:`, `location:`. This is the *Locked in frame* column.
- **`parents`** — the plates this generation inherits, in the order they get attached
  (`@Image1`, `@Image2`…). This is the *Parent plates* column, and it is what makes "every
  generation names its parents" checkable instead of aspirational.

Older spellings (`reference`, `references`, `reference_images`) still load — `planlint.py`
normalises them and every script now reads the plan through it, so a reference can no longer
be attached in one script and dropped in the next.

Then run the check before anything is built or bought:

```bash
python3 scripts/planlint.py --plan plan.json
```

It blocks, rather than warns, on the failures that make footage unusable: a locked thing with
no parent plate, a text-to-video route for a locked shot, a parent that is another shot's
output, two locked things in one frame, a product missing from the registry or missing its
real photograph, and a prompt asking for an unbranded pack. `packet.py` and `generate.py`
run it themselves and refuse to proceed — `--force` exists, and using it is a decision to
ship known drift.

---

## Step 3 — Tier 0: the locks

Made once, stored in the registry as campaign assets, never as scratch files:

```bash
python3 campaign.py add-character --name chef --refs chef_canonical.png chef_34.png chef_profile.png \
  --prompt-lock "heavyset man, black cap worn forward, black jacket with small red chest logo, white apron"
python3 campaign.py add-product --name burger --refs burger_real_photo.jpg
```

- **Character**: one canonical portrait first — neutral expression, even light, clear features,
  head and shoulders. Then derive front / three-quarter / profile / full-body **from that
  portrait**, never independently. Four independently generated portraits are four people.
- **Product**: a real photograph, or a generation pass that **edits** a real photograph into the
  campaign's light. Attaching a photo and *also* describing the object in words is still
  invention, just with a hint.
- **Location**: one establishing frame of the set, lit per the category (`product-artdirection.md`).

Stills are cheap and the agent host renders them for free — build every Tier 0 plate there
before spending a credit on video.

---

## Step 4 — Tier 1: composites

A composite proves two locks can coexist before any video is paid for:

- `chef-in-kitchen` = character sheet **+** location plate → one still.
- `burger-on-counter` = product plate **+** location plate → one still.

Generate a composite from its two Tier 0 parents. **Never from a previous composite plus words** —
that is where drift enters through the side door.

If a composite refuses to come out right after a few tries, that is the model telling you the
shot is too crowded. Believe it now, at the price of an image, rather than later at the price of
a video.

---

## Step 5 — Tier 2: shot plates — one still per shot

For every row of the ledger, generate the **first frame of that shot** from its parent plates.
This is where angle, lens, framing and light get decided.

**This step is the whole economy of AI ad work.** A still costs a fraction of a video second, so
every argument about composition should be settled in images. Arriving at video generation with
an approved first frame per shot turns generation from exploration into execution.

It matters twice over for single-image models: Kling's image-to-video takes **one** input frame,
so the shot plate must already contain the character *and* the location *and* the product
together. Tier 2 is what makes a one-image model usable at all.

---

## Step 6 — Tier 3: video, one clip per shot

Each clip is generated **from its own shot plate**, with the Tier 0 plates passed as additional
references wherever the model accepts several.

Three prohibitions:

- **No text-to-video for any shot containing a locked thing.** Not once, not for a draft.
  `planlint` treats this as an error, not a warning.
- **No chaining generations.** Never feed the last frame of clip N as the first frame of clip
  N+1 to "continue" — drift compounds and by the tenth clip the character is someone else.
  Return to the plate every time.
- **No grading per clip.** Ask for neutral-ish output and grade the assembly once
  (`video-editor`). Colour consistency achieved by prompting is not consistency.

Keep clips at 3–5 seconds. Drift grows with duration: two 4-second clips end closer to the
reference than one 8-second clip does.

---

## Step 7 — Tier 4: the edit

`video-editor` owns it: trim each clip to the ledger's length, assemble to the beat map, one
grade pass, one music bed for the whole film, captions inside the safe zone, logo **composited**
rather than generated, loudness to the platform target.

Anything the model renders unreliably — small label copy, a logo, legible on-screen text —
belongs here rather than in a prompt. A logo that depends on generation is a lottery ticket
bought fresh in every clip.

---

## Model routing by requirement

Verified against the user's magica catalogue, July 2026. Tiered prices vary by resolution;
confirm the exact figure with `POST /nodes/estimate-credits` on the real inputs before committing —
estimates return nothing useful for placeholder URLs.

| The shot needs | Model | Price |
|---|---|---|
| A locked character or product, several reference images | `seedance-2.0-reference-to-video` | 0.0807–1.555 USD tiered |
| The same, for drafts and blocking | `seedance-2.0-fast-reference-to-video` | 0.0645–0.2419 USD tiered |
| Animation of one approved shot plate | `seedance-2.0-image-to-video` / `-fast-` | 0.1345–1.555 / 0.1076–0.2419 |
| One plate, strong camera move | `kling-v3-pro-image-to-video` | 0.112–0.168 USD tiered |
| Nothing locked — atmosphere, abstract, B-roll | `kling-v3-pro-text-to-video` | 0.112–0.168 USD tiered |
| A movement transferred onto a locked character | `kling-v3-pro-motion-control` | 0.168 USD/s |
| A finished clip needs altering | `kling-o3-pro-video-edit` | 0.2801 USD/s |

`seedance-2.0-reference-to-video` takes **three kinds of reference, not one**, and the third
changes how a beat-cut ad gets built. Verified against the live schema 2026-07-31:

| Field | Cited in the prompt as | Limits |
|---|---|---|
| `reference_image_urls` | `@Image1`, `@Image2`… | up to 9 images |
| `reference_video_urls` | `@Video1`… | up to 3 clips, 2–15s combined |
| `reference_audio_urls` | `@Audio1`… | up to 3 clips, ≤15s combined, mp3/wav |

Plus `duration` 4–15s, `aspect_ratio` including `9:16`, `resolution` offering `4k` on the
aggregator — though ByteDance documents **2K as the current native ceiling**, so `1080p` is the
honest maximum and `4k` risks paying top rate for an upscale.

**Supplying audio is how cuts land on the beat.** `generate_audio: true` invents a bed, a different
one per clip, so it stays off for multi-clip work. But passing the real track as `@Audio1` and
instructing the changes to fall on its beats moves beat-sync *into the generation* rather than
leaving it to the edit. For an outfit-change or any 卡点-style ad that is the entire trick, and
reaching for `--beat-sync` in post is the fallback, not the method.

**Supplying a motion clip beats describing motion.** A spin, a jump or a turn passed as `@Video1`
carries real physics into the shot; the same movement written in words is reinvented from nothing
on every generation.

Nine images in one call means a full set fits at once — character plates plus every product plate,
with no splitting.

**Text-to-video models cannot hold a character.** That is a capability boundary, not a matter of
prompt quality: Veo is excellent at motion and useless for this job, because the chef will be a
different man in every shot. Reserve it for what it is good at.

---

## Failure modes of ordering

- **Writing shot prompts before the ledger exists.** The route and the plate list are derived
  from the ledger; without it, every prompt is a guess about what it inherits.
- **Describing a recurring thing twice.** The second description is a second version of the
  thing. This is the single largest source of "why is the bottle a different shape".
- **Skipping Tier 2 to save time.** Composition then gets decided at video prices, and each
  revision costs a full generation instead of an image.
- **Building a character sheet for a character who appears once.** Cost with no return.
- **Two locked things in one frame because the reference had them there.** The reference was shot
  with a camera, or by a team with a compositor. Split it.
- **Grading, captioning or lettering in the prompt.** All three belong to the edit, where they
  are deterministic.
