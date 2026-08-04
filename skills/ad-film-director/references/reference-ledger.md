# Reference Ledger

Load when the user hands you an ad — one they like, or one they hate — and in Phase 7 when
checking your own cut against a measured target.

An ad the user liked is the cheapest and most precise direction they will ever give you, and
the easiest to waste. Watched casually it yields "nice, punchy edit" and changes nothing next
time. Measured, it yields "four cuts inside the first 2.8s, 71% of cuts on the beat, grade
cools until the payoff then warms" — a target you can hit tomorrow on a completely different
product.

**This file is raw material and audit trail, not doctrine.** A pattern that has proven itself
gets written into the file that owns it — `script-craft.md`, `product-artdirection.md`,
`creative-registers.md`, `consistency.md` — carrying a `[REF-nnnn]` tag so anyone can trace
where it came from and undo it later. What stays here: the observation cards, the numbers, and
the index of what was promoted where.

`delegation.md` is the canonical command reference for watching and measuring, and it already
covers why numbers beat impressions on a single reference. What this file adds is everything
that has to survive the session: a lookup from what the user says to what to measure, a bar a
technique must clear before it counts, a threshold before it becomes a rule, and a record of
which rule came from which ad.

---

## The intake protocol

**1. Get the file.** A local `.mp4` uploaded to chat is the reliable path. A URL needs
`yt-dlp`, which is missing in some sandboxes and blocked by login walls on Instagram and
TikTok regardless. Don't fight it — ask for the file.

**2. Get one sentence of intent.** What did they like? Don't interrogate: one line is enough,
and "just look at it" is an acceptable answer — then you name what you think they responded
to and let them correct you.

**3. Watch it, then measure it.** Both. Frames tell you what is on screen; only the numbers
tell you how it was built.

```bash
# the whole ad — keyframes land on cuts, which is what you want on a reference
python3 "$WATCH_BIN/watch.py" ref.mp4 --detail efficient --no-whisper

# the hook alone, at the 2 fps ceiling — this is where the ad is won or lost
python3 "$WATCH_BIN/watch.py" ref.mp4 --start 0 --end 3 --fps 2

# how it was built. VE_DIR is not optional: without it beat detection
# reports measurable:false, and beat alignment is half of what you came for
VE_DIR="$VE_DIR" python3 "$WATCH_BIN/montage.py" --video ref.mp4 --beats-from-audio
```

Then `Read` every frame path printed. On a 15–30s ad the focused hook pass costs almost nothing
and carries most of the signal. If the shot count looks lower than the frames plainly show, the
cuts are luma-similar — lower `--threshold` (0.20, then 0.12) before believing the pacing
figures.

**4. Get the words if the ad speaks.** With no Whisper key configured, skip the API and let
the host transcribe:

```bash
ffmpeg -i ref.mp4 -vn -c:a libmp3lame -q:a 5 ref.mp3
```

Hand `ref.mp3` to the host's own transcription. A 30-second ad is well under any upload cap.

**5. Convert the impression into a measurement.** See the table below. This is the whole job.

**6. Apply the applicability test.** Anything that fails it does not enter the ledger.

**7. Write the card.** Status `observed`. If the technique matches an existing card, do not
open a new one — increment its confirmation count.

**8. Promote only when the threshold is met.** Then patch the owning file and log it in the
promotion index.

---

## Turning an impression into a measurement

The user speaks in effects. The skill needs causes. This table is the bridge — left column is
roughly what people say, right columns are what to actually look at.

| They say | Measure this | Source | Lands in |
|---|---|---|---|
| "dynamic", "punchy", "no dead air" | cuts per 10s, mean/median shot length, length histogram | `shots` | `script-craft.md` — structure and length |
| "grabs you instantly" | cuts in first 3s, opening shot duration, what is in frame one | `hook` + focused frames | `script-craft.md` — hook rules |
| "great with the music" | share of cuts on beat, mean offset in ms, BPM | `rhythm` | `video-editor` params, beat-sync decision |
| "beautiful image", "rich colour" | warmth, grade drift across the film, contrast spread | `grade` + frames | `product-artdirection.md` — category lighting |
| "looks expensive" | camera moves vs subject moves, move speed, lens compression, highlight control | frames | `product-artdirection.md` |
| "product looks great" | when product first enters (% of runtime), how long it holds, how many angles | `shots` + frames | `script-craft.md` proof-shot placement, `consistency.md` |
| "funny", "weird", "unlike the category" | structure and register, not numbers | transcript + frames | `creative-registers.md` |
| "captions are good" | style, position, timing relative to image, safe-zone margin | frames | `script-craft.md` on-screen text, caption preset |
| "sounds good" | integrated LUFS, true peak, music-vs-SFX balance | `audio` | `video-editor` loudness target |
| "the pacing builds" | first-third vs last-third shot length, accelerating/steady/decelerating | `pacing` | `script-craft.md` structures |

**When the words map to nothing, say so.** Sometimes what they liked was the product, the
celebrity, the location or the joke — none of which is a transferable craft rule. Filing it as
one pollutes the skill and produces confident nonsense three ads later. "You liked this, but
what you liked isn't something I can reuse" is a real and useful answer.

---

## The applicability test

A candidate technique is admitted only if it changes at least one of these:

1. **A prompt block** — light, lens, camera behaviour, grade wording, a preservation clause.
2. **A structural target** — shot length, shot count, where the product enters, total runtime.
3. **An edit parameter** — a `video-editor` flag: beat-sync, look, caption preset, LUFS target.
4. **A line of copy** — a hook mechanism, a claim shape, a CTA pattern.

If it changes none of them, it is a diary entry. Say what you noticed in chat and let it go.

---

## Promotion — when an observation becomes a rule

One ad is an anecdote. Ads are made by talented people making one-off choices, and half of
what works in a given ad works because of that specific product, budget and cast.

**A card is promoted when either:**

- **two or more independent references** show the same technique (confirmation count ≥ 2), or
- **the user says it outright** — "always do this", "this is the rule now". Their word is
  worth more than any count, and it promotes immediately at count 1.

**How to promote.** Write the rule into the file that owns it, in that file's own voice and
inside the section that already covers the topic — not as an appended block at the bottom.
Tag it `[REF-0003]` (or several ids) so it can be traced and reverted. Then add a line to the
promotion index below and set the card's status to `promoted`.

A promoted rule that later proves wrong is deleted from the owning file, and its card status
becomes `rejected` with the reason. This is why the tags exist.

---

## Precedence — what wins when rules collide

Strict order, highest first:

1. **The project's style lock** (`.campaign/STYLE-LOCK.txt`, the `prompt_lock` on a registered
   product or character). A learned pattern never overrides a lock. If a reference is warm and
   sunlit and the project is locked to pure black, the lock wins and the pattern is noted as
   out of scope for this project.
2. **The user's explicit instruction in the current conversation.**
3. **A promoted pattern from this ledger.**
4. **The skill's general defaults.**

When a learned pattern and a lock disagree, say so in one line rather than silently picking.
That sentence is often where the user discovers their own lock needs revising.

---

## What never enters the ledger

- **A shot list.** Copy the technique, never the frames. "Cuts on every second beat, product
  enters 40% in, grade cools then warms" transfers to any product. A reproduced sequence of
  shots is plagiarism and reads as plagiarism — and for spec work published under the user's
  own name it is the one failure that cannot be defended.
- **Brand-specific assets.** Their font, their exact palette, their music, their tagline.
- **Taste without a mechanism.** "Beautiful" with nothing measured under it.
- **Anything from an ad the user hasn't actually commented on.** Their reaction is the signal;
  without it you are just measuring strangers' work.

---

## Card format

Keep to roughly 15 lines. Density beats completeness — the fields that were not measurable are
omitted, not filled with "n/a".

```
### REF-0001 — short handle
- Source: <file or url> · analysed: YYYY-MM-DD · brand/product: <what it sells>
- Category: <gloss / food / fabric / interiors / … per product-artdirection.md>
- Format: <duration, aspect, platform it was cut for>
- User's words: "<verbatim, their language>"
- Shots: N · mean Xs · median Ys · cuts/10s Z · histogram <shape>
- Hook: <cuts in first 3s> · opening shot <X>s · frame one: <what it is>
- Pacing: accelerating | steady | decelerating
- Rhythm: <BPM> · <share>% on beat · mean offset <N>ms
- Grade: <warm/cool> · drift <yes/no> · contrast <spread>
- Audio: <LUFS> integrated · true peak <dB>
- Copy: hook line, claim count, CTA shape
- Candidate techniques:
  1. <technique> → <owning file / phase>
  2. <technique> → <owning file / phase>
- Status: observed | promoted → <file> | rejected (<reason>)
- Confirmations: 1
```

---

## Promotion index

Every rule this ledger has pushed into the skill, so the trail runs both ways.

| Rule | Written into | Based on |
|---|---|---|
| _(none yet)_ | | |

---

## Observation cards

_No references analysed yet._ The first intake fills this section; the card format above is a
starting shape and is expected to change once real reports have been read.

---

## Antipatterns

Ads the user disliked, and the mechanism behind the dislike. Cheaper to collect than positives
and just as directive — a named antipattern is a check you can run in Phase 7.

_None recorded yet._

---

## Housekeeping

- **Cap: ~20 observation cards.** Past that, collapse the oldest promoted or rejected cards to
  a single line each (`REF-0004 — handle — promoted → script-craft.md`). The measurements have
  already done their work; the trail is what needs keeping.
- **Never delete a card that a promoted rule cites.** Collapse it instead, or the tag in the
  owning file points at nothing.
- **Re-measuring is cheap; re-remembering is not.** If a number looks wrong, re-run
  `montage.py` with a lower `--threshold` before theorising — luma-similar cuts go undetected
  and a low shot count is the usual symptom.
