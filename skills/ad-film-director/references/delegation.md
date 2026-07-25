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

## Detection

Run once at the start of a production and remember the result.

```bash
# video-editor — locate it, then verify its dependencies
for d in ./video-editor ~/.claude/skills/video-editor-skill/video-editor \
         ~/.agents/skills/video-editor-skill/video-editor \
         ~/.codex/skills/video-editor-skill/video-editor; do
  [ -f "$d/playbook.py" ] && export VE_DIR="$d" && break
done
[ -n "$VE_DIR" ] && python3 "$VE_DIR/doctor.py"

# watch — locate its script
for d in ~/.claude/skills/watch ~/.agents/skills/watch ~/.codex/skills/watch \
         ~/.claude/plugins/cache/claude-video/watch/*/skills/watch; do
  [ -f "$d/scripts/watch.py" ] && export WATCH_DIR="$d" && break
done
```

`doctor.py` verifies ffmpeg and required filters. If it reports problems, treat
`video-editor` as unavailable and use the fallbacks below.

If neither is installed and the user wants the full pipeline, tell them once, plainly:

> Two optional skills would improve this: `video-editor` for professional assembly, captions
> and per-platform export, and `watch` so I can review the footage visually before you post
> it. Install: `npx skills add genchebur90-debug/video-editor-skill -g` and
> `npx skills add bradautomates/claude-video -g`. I can proceed without them — the edit will
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
python3 "$VE_DIR/playbook.py" ad \
  --clips shot1.mp4 shot2.mp4 shot3.mp4 \
  --music bed.mp3 \
  --look warm_ad \
  --beat-sync \
  --platform reels \
  --captions words.json \
  --caption-style tiktok \
  --cta "Try it free" \
  --qc \
  --out ad_reels.mp4
```

Playbooks: `short` (general short-form), `ad` (commercial), `ugc` (UGC register).
Add `--dry-run` to see the plan without rendering.

Looks available: `clean`, `punch`, `teal_orange`, `film`, `warm_ad`, `cold_tech`, `bw`.
Match the look to the register and category — `warm_ad` for food, `cold_tech` for hardware,
`film` for arthouse, `clean` for UGC.

### Individual operations, when you need control

```bash
# Vertical reframe with subject tracking (respects platform safe zones)
python3 "$VE_DIR/reframe_smart.py" landscape.mp4 vertical.mp4 --safe tiktok

# Concat with a transition
python3 "$VE_DIR/ops.py" concat a.mp4 b.mp4 c.mp4 --out assembled.mp4

# Colour grade
python3 "$VE_DIR/color.py" grade in.mp4 out.mp4 --look warm_ad

# Broadcast audio: dialogue chain + loudness
python3 "$VE_DIR/audio_pro.py" voice in.mp4 out.mp4 --preset ugc --platform reels

# Burn captions inside the safe zone
python3 "$VE_DIR/captions.py" burn cut.mp4 final.mp4 --style tiktok --safe tiktok

# Export per platform
python3 "$VE_DIR/deliver.py" export master.mp4 out_tiktok.mp4 --profile tiktok
python3 "$VE_DIR/deliver.py" export master.mp4 out_reels.mp4  --profile reels
python3 "$VE_DIR/deliver.py" export master.mp4 out_feed.mp4   --profile feed_4x5

# Pre-publish QC — exits 1 on failure
python3 "$VE_DIR/qc.py" out_reels.mp4 --platform reels || echo "QC FAILED"
```

Export profiles: `reels`, `tiktok`, `shorts`, `square`, `feed_4x5`, `youtube_hd`,
`youtube_4k`, `master_prores`.

Every script prints JSON to stdout — parse it rather than guessing at results.

### Multi-platform delivery pattern

Produce one master, then export per destination. Reframe *before* captioning so captions
land correctly in each aspect ratio.

```bash
# master at 1080x1920
python3 "$VE_DIR/playbook.py" ad --clips ... --platform reels --out master.mp4

# then per destination
python3 "$VE_DIR/deliver.py" export master.mp4 deliver/tiktok.mp4 --profile tiktok
python3 "$VE_DIR/deliver.py" export master.mp4 deliver/reels.mp4  --profile reels
python3 "$VE_DIR/qc.py" deliver/tiktok.mp4 --platform tiktok
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
python3 "$WATCH_DIR/scripts/watch.py" ad_reels.mp4 \
  --detail balanced --no-whisper
```

Then `Read` every frame path printed. Check against the Phase 7 list: product fidelity,
hook strength muted, text inside safe zone, hands and physics, continuity.

Force frames at moments that matter — the hook, the proof shot, the CTA card:

```bash
python3 "$WATCH_DIR/scripts/watch.py" ad_reels.mp4 \
  --detail balanced --no-whisper --timestamps 0:00,0:01,0:08,0:14
```

To read on-screen text, raise resolution (costs more image tokens):

```bash
python3 "$WATCH_DIR/scripts/watch.py" ad_reels.mp4 --resolution 1024 --timestamps 0:13,0:14
```

### Studying a reference ad

When the user shares a competitor ad or an ad they admire:

```bash
python3 "$WATCH_DIR/scripts/watch.py" "https://youtu.be/XXXX" --detail efficient
```

Analyse: hook mechanism and its timing, structure, cut rhythm, lighting scheme, register,
where text sits, CTA design. Feed that into Phase 2 and Phase 4 rather than copying it.

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

Then `Read` those frames. Local files only, no transcript, no scene detection.

---

## Combined Phase 7 sequence

```bash
# 1. assemble
python3 "$VE_DIR/playbook.py" ad --clips inbox/*.mp4 --music bed.mp3 \
  --look warm_ad --platform reels --captions words.json --qc --out master.mp4

# 2. look at it
python3 "$WATCH_DIR/scripts/watch.py" master.mp4 --detail balanced --no-whisper
#    → Read each frame path, judge against the Phase 7 checklist

# 3. export per destination
python3 "$VE_DIR/deliver.py" export master.mp4 deliver/reels.mp4  --profile reels
python3 "$VE_DIR/deliver.py" export master.mp4 deliver/tiktok.mp4 --profile tiktok

# 4. gate
python3 "$VE_DIR/qc.py" deliver/reels.mp4 --platform reels

# 5. log the variant so it isn't reused on another account
python3 scripts/campaign.py register --variant v1 --account ig_main --platform reels
```

If step 2 reveals a problem needing regeneration, **return to the Routing Gate** — retries
cost credits and need approval.
