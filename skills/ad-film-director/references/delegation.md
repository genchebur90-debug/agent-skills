# Delegating to Sibling Skills

Load in Phase 6 and Phase 7.

This skill directs. Two other skills do specialist work better than reimplementing it here
would. **Always detect availability first and degrade gracefully — never fail because a
sibling is absent.**

| Skill | Repository | Owns |
|---|---|---|
| `video-editor` | `genchebur90-debug/video-editor-skill` | All post-production |
| `watch` | `bradautomates/claude-video` | Seeing and analysing video |

Neither is required. Both make the output substantially better.

---

## Detection — one command, any host

```bash
python3 scripts/siblings.py doctor
```

Returns JSON: what this host can do (python, ffmpeg, cwd), which siblings are installed,
their absolute paths, and a `degraded` list naming what is missing. Run it once at the start
of a production and again only if something moves.

**Never export paths into shell variables.** The previous version of this file did, and it
was wrong on almost every host: each tool call runs in a fresh process, `VE_DIR` dies with
it, and the next command silently becomes `python3 /playbook.py`. Resolution lives in
`siblings.py`, which probes the known layouts (next to this skill, `~/.claude/skills`,
`~/.agents/skills`, `~/.codex/skills`, `/home/user/skills`, plugin caches, the current
directory), caches the answer in `.campaign/siblings.json`, and can run the target itself:

```bash
python3 scripts/siblings.py run video-editor playbook.py -- ad --clips a.mp4 --out o.mp4
python3 scripts/siblings.py run watch watch.py -- master.mp4 --detail balanced --no-whisper
```

`run` also sets the child environment the siblings expect — including `VE_DIR`, which
`montage.py` needs to find `rhythm.py` for beat detection. That is why beat analysis used to
return nothing on a fresh shell.

If a skill sits somewhere unusual, point at it once and every later call finds it:
`ADFD_VIDEO_EDITOR_DIR=/path/to/video-editor`, `ADFD_WATCH_DIR=...`, or `ADFD_SKILLS_DIR=`
a directory holding several skills.

**Exit codes from `siblings.py`:** `3` means not installed — fall back, do not crash. `4`
means installed but the entry script is missing, which is a broken install worth reporting.
Anything else is the child's own exit code.

To check the environment more deeply (this runs `video-editor/doctor.py`, which prints human
text rather than JSON — `siblings.py` reads its verdict for you):

```bash
python3 scripts/siblings.py doctor --deep
```

## film-director — narrative film and animation over 60 seconds

A sibling, not a layer. This skill owns ads: a product, a buyer, a claim, 6-60 seconds. Narrative
film and animation from 30 seconds to 5 minutes belong to `film-director`, which has its own phase
structure, artifact-based locks for 50-150 shots, and a cross-film uniqueness ledger.

| Request | Skill |
|---|---|
| Ad, promo, commercial, product video, 6-60s | **this skill** |
| Short film, cartoon, animation, music video, visual poem, 30s-5min | `film-director` |
| A 3-minute brand film with a story, product incidental | `film-director`, keeping the disclaimer rules below |
| Ad ideas, ad variants, a campaign across accounts | **this skill** |

The test when a request straddles the line: **does the film exist to make someone want a product?**
If yes it is an ad whatever its runtime. If the product is a setting rather than a purpose, hand it
to `film-director`.

Both skills share this fleet layer and the `inbox/<shot-id>.<ext>` contract, so footage routed by
either is interchangeable. `film-director` emits its routing needs in exactly the schema
`fleet.py plan --needs` expects — `id`, `need`, `seconds`, `note`, `best_for`.

`siblings.py run` wires the two together automatically: `montage.py` inside `watch` looks
for `rhythm.py` through `VE_DIR`, and the runner sets it in the child environment, so beat
detection works without anything being exported by hand.

`siblings.py doctor --deep` verifies ffmpeg and the required filters through
`video-editor/doctor.py`. If it reports problems, treat `video-editor` as unavailable and use
the fallbacks below.

If neither is installed and the user wants the full pipeline, tell them once, plainly:

> Two optional skills would improve this: `video-editor` for professional assembly, captions
> and per-platform export, and `watch` so I can review the footage visually before you post
> it. Install with your host's skill installer — with the `skills` CLI that is
> `npx skills add genchebur90-debug/video-editor-skill -g` and
> `npx skills add bradautomates/claude-video -g`; on a host without one, clone the two
> repositories next to this skill and they will be found. I can proceed without them — the edit will
> be draft quality and I won't be able to check the result visually.

Don't nag. Say it once, then work with what exists.

---

## `video-editor` — post-production

**It owns, and you must not reimplement:** trimming, dead-air removal, concat with
transitions, speed ramps, freeze frames, J/L cuts, subject-tracking vertical reframe, HDR
tone mapping, colour grading, LUTs, film looks, two-pass stabilisation, denoise, broadcast
dialogue processing, sidechain ducking, EBU R128 loudness normalisation, animated captions
with platform safe zones, per-platform export profiles, beat detection, and pre-publish QC.

### The common path — one command

```bash
python3 scripts/siblings.py run video-editor playbook.py -- ad \
  --clips shot1.mp4 shot2.mp4 shot3.mp4 \
  --music bed.mp3 \
  --look warm_ad \
  --beat-sync \
  --platform reels \
  --captions words.json \
  --caption-preset brand_ad \
  --cta "Try it free" \
  --qc \
  --out ad_reels.mp4
```

Playbooks: `short` (general short-form), `ad` (commercial), `ugc` (UGC register).
Add `--dry-run` to see the plan without rendering.

Looks available: `clean`, `punch`, `teal_orange`, `film`, `warm_ad`, `cold_tech`, `bw`.
Match the look to the register and category — `warm_ad` for food, `cold_tech` for hardware,
`film` for arthouse, `clean` for UGC.

**Captions carry the register too.** `--caption-preset` picks a whole look — font, size,
case, colour, position, motion — not just an animation style. Never leave it to the default;
a UGC ad with brand typography reads as an ad, and a brand film with bouncing yellow caps
reads as cheap. The register you locked in Phase 2c decides it:

| Register | `--caption-preset` |
|---|---|
| UGC | `ugc_soft`, or `tiktok_native` for a native auto-caption feel |
| Humour | `tiktok_punch`, `meme_bold` for a two-word punchline |
| Straight commercial | `brand_ad` |
| Arthouse, sensory / ASMR | `minimal_lux` |
| Process / craft doc, mockumentary | `doc_lower` |
| Retro pastiche, hyper-stylised graphic | `meme_bold` or `contrast_box`, per the palette |
| Any register, busy or bright footage | `contrast_box` |

Run `python3 scripts/siblings.py run video-editor captions.py -- presets` for the full list with what each is for. Pass
`--accent "#RRGGBB"` from the ad's palette — the preset's own accent is a placeholder, and an
accent pulled from the product beats the default cyan every time.

### Individual operations, when you need control

```bash
# Vertical reframe with subject tracking (respects platform safe zones)
python3 scripts/siblings.py run video-editor reframe_smart.py -- landscape.mp4 vertical.mp4 --safe tiktok

# Concat with a transition
python3 scripts/siblings.py run video-editor ops.py -- concat a.mp4 b.mp4 c.mp4 --out assembled.mp4

# Colour grade
python3 scripts/siblings.py run video-editor color.py -- grade in.mp4 out.mp4 --look warm_ad

# Broadcast audio: dialogue chain + loudness
python3 scripts/siblings.py run video-editor audio_pro.py -- voice in.mp4 out.mp4 --preset ugc --platform reels

# Burn captions inside the safe zone
python3 scripts/siblings.py run video-editor captions.py -- burn cut.mp4 final.mp4 --preset tiktok_native --safe tiktok

# Export per platform
python3 scripts/siblings.py run video-editor deliver.py -- export master.mp4 out_tiktok.mp4 --profile tiktok
python3 scripts/siblings.py run video-editor deliver.py -- export master.mp4 out_reels.mp4  --profile reels
python3 scripts/siblings.py run video-editor deliver.py -- export master.mp4 out_feed.mp4   --profile feed_4x5

# Pre-publish QC — exits 1 on failure
python3 scripts/siblings.py run video-editor qc.py -- out_reels.mp4 --platform reels || echo "QC FAILED"
```

Export profiles: `reels`, `tiktok`, `shorts`, `square`, `feed_4x5`, `youtube_hd`,
`youtube_4k`, `master_prores`.

Most `video-editor` scripts print JSON to stdout — parse it rather than guessing at
results. `doctor.py` is the exception: it prints a human-readable table and the word
`READY` on success, which is what `siblings.py doctor --deep` looks for.

### Multi-platform delivery pattern

Produce one master, then export per destination. Reframe *before* captioning so captions
land correctly in each aspect ratio.

```bash
# master at 1080x1920
python3 scripts/siblings.py run video-editor playbook.py -- ad --clips ... --platform reels --out master.mp4

# then per destination
python3 scripts/siblings.py run video-editor deliver.py -- export master.mp4 deliver/tiktok.mp4 --profile tiktok
python3 scripts/siblings.py run video-editor deliver.py -- export master.mp4 deliver/reels.mp4  --profile reels
python3 scripts/siblings.py run video-editor qc.py -- deliver/tiktok.mp4 --platform tiktok
```

### Fallback without `video-editor`

Plain ffmpeg. Tell the user it's draft quality — no subject tracking, no dialogue processing,
no loudness normalisation, no QC.

```bash
printf "file '%s'\n" shot1.mp4 shot2.mp4 shot3.mp4 > list.txt
ffmpeg -f concat -safe 0 -i list.txt -c:v libx264 -crf 20 -preset medium \
  -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -movflags +faststart draft.mp4

# rough loudness pass
ffmpeg -i draft.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11 -c:v copy draft_norm.mp4
```

Do not attempt hand-rolled subject-tracking reframe or caption animation. Recommend
installing `video-editor` instead.

---

## `watch` — seeing video

Extracts frames and a transcript from a local file or a URL, then prints frame paths.
**You then `Read` each path** — that's how the images enter your context. It isn't a vision
API; it's your own multimodality.

### Reviewing your own ad (Phase 7)

```bash
python3 scripts/siblings.py run watch watch.py -- ad_reels.mp4 \
  --detail balanced --no-whisper
```

Then open every frame path printed. Check against the Phase 7 list: product fidelity,
hook strength muted, text inside safe zone, hands and physics, continuity.

Force frames at moments that matter — the hook, the proof shot, the CTA card:

```bash
python3 scripts/siblings.py run watch watch.py -- ad_reels.mp4 \
  --detail balanced --no-whisper --timestamps 0:00,0:01,0:08,0:14
```

To read on-screen text, raise resolution (costs more image tokens):

```bash
python3 scripts/siblings.py run watch watch.py -- ad_reels.mp4 --resolution 1024 --timestamps 0:13,0:14
```

### Studying a reference ad

When the user shares a competitor ad or an ad they admire:

```bash
python3 scripts/siblings.py run watch watch.py -- "https://youtu.be/XXXX" --detail efficient
```

Analyse: hook mechanism and its timing, structure, cut rhythm, lighting scheme, register,
where text sits, CTA design. Feed that into Phase 2b and Phase 4 rather than copying it —
a reference ad is one point on the slate, not the whole slate.

That URL assumes `yt-dlp` is installed and the source isn't login-walled. Instagram and TikTok
usually are, and some sandboxes have no `yt-dlp` at all — ask for the file rather than fighting
the download.

**If the user also said what they liked about it, don't stop at the analysis.** Run the intake
in `reference-ledger.md`: a one-off reading improves this ad, a filed card and a promoted rule
improve every ad after it.

### Measuring a reference instead of describing it

Frames tell you what is on screen; they don't tell you the cut rhythm. **Run `montage.py`
alongside the frames** and the reference stops being an impression and becomes numbers you can
reproduce:

```bash
python3 scripts/siblings.py run watch montage.py -- --video ref.mp4 --beats-from-audio
```

Returns: shot count and every shot length, average and median, cuts per 10s, a length
histogram, whether the pace accelerates or relaxes, how many cuts fire inside the first three
seconds, the share of cuts landing on a beat with the mean offset, the grade's warmth and
whether it drifts, and integrated loudness.

Why this matters for directing: "fast-paced with punchy music" is not a brief anyone can
execute. "Eleven shots in 15s, average 1.4s, accelerating to 0.6s at the payoff, 82% of cuts
on the beat, grade cools then warms on the reveal" *is* a brief — and it transfers to a
completely different product.

Set your own edit's targets from those numbers, then run the same command on your finished cut
and compare. A reference at 8 cuts per 10s against your 2 turns a vague "it feels slower than
the reference" into something precise enough to fix.

**Never copy the shot list.** Take the structure — pacing curve, hook density, beat
relationship, grade arc — and apply it to this product's own concept. Reproducing someone's
frames is plagiarism, reads as derivative, and wastes the slate you already built.

If the shot count looks lower than the frames obviously show, the cuts are luma-similar: lower
`--threshold` (0.20, then 0.12) and re-run before trusting the pacing figures.

### Detail modes

| Mode | Frames | Use |
|---|---|---|
| `transcript` | none | Speech only, no visual review |
| `efficient` | up to 50, keyframes | Fast pass, reference ads |
| `balanced` | up to 100, scene-aware | **Default for reviewing your own ads** |
| `token-burner` | uncapped | Forensic checks only |

Practical notes: frame rate is capped at 2 fps; default frame width 512px (use 1024 only to
read text); accuracy degrades on videos over ~10 minutes — irrelevant for ads. Use
`--no-whisper` for ads without meaningful speech to skip transcription entirely.

**Transcription cost gate:** if the ad has speech and no native captions exist, `watch` needs
a Whisper API key (`GROQ_API_KEY` or `OPENAI_API_KEY`). That's a paid call — mention it before
running, per Rule 2. For most ads `--no-whisper` is fine since you wrote the script yourself.

### Fallback without `watch`

```bash
mkdir -p /tmp/frames && ffmpeg -i ad_reels.mp4 -vf fps=1 /tmp/frames/f_%03d.jpg
```

Then open those frames. Local files only, no transcript, no scene detection.

---

## Combined Phase 7 sequence

```bash
# 1. assemble
python3 scripts/siblings.py run video-editor playbook.py -- ad --clips inbox/*.mp4 --music bed.mp3 \
  --look warm_ad --platform reels --captions words.json --qc --out master.mp4

# 2. look at it
python3 scripts/siblings.py run watch watch.py -- master.mp4 --detail balanced --no-whisper
#    → open each frame, judge against the Phase 7 checklist

# 3. export per destination
python3 scripts/siblings.py run video-editor deliver.py -- export master.mp4 deliver/reels.mp4  --profile reels
python3 scripts/siblings.py run video-editor deliver.py -- export master.mp4 deliver/tiktok.mp4 --profile tiktok

# 4. gate
python3 scripts/siblings.py run video-editor qc.py -- deliver/reels.mp4 --platform reels

# 5. product identity: plate beside the frames, then the fields
python3 scripts/identity.py sheet --plate .campaign/assets/<c>/products/<p>/plate.jpg \
  --candidates master.mp4 --at 2.0 --out review/identity.png
#    → open review/identity.png, then answer every field:
python3 scripts/campaign.py verify --product <p> --shot master

# 6. log the variant so it isn't reused on another account
python3 scripts/campaign.py register --variant v1 --account ig_main --platform reels
```

If step 2 reveals a problem needing regeneration, **return to the Routing Gate** — retries
cost credits and need approval.
