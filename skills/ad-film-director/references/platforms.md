# Platforms: Generation and Delivery

Load in Phase 3 (routing) and Phase 7 (delivery).

Two unrelated things live here: **where footage comes from**, and **where it goes**.

> **Verification notice.** Model versions, capabilities, endpoints and prices change monthly.
> Everything in Part 1 was accurate when written (mid-2026) but **must be treated as needing
> verification** before you rely on it — especially pricing. Never quote a price to the user
> as certain. Part 2 (delivery specs) is far more stable.

---

# PART 1 — Generation platforms

## The access question decides everything

Before capability, ask: **can the agent call it, or must a human click?**

| Access type | Meaning | Consequence |
|---|---|---|
| **host** | The agent's own environment renders it | Agent generates directly, spending none of the user's credits |
| **api** | Working API, key present, credits available | Agent generates directly |
| **ui** | Subscription is web-only, or API not included in the plan | Agent writes a packet, human generates |
| **api-paid** | API exists but needs credits bought separately | **Warn with an estimate, ask first** |

A crucial and frequently misunderstood point: **most consumer AI subscriptions do not include
API access.** The web plan and the API are usually separate products with separate billing.
Having a paid subscription does *not* imply programmatic access. Always check the `access`
field in the fleet config rather than assuming.

## The overlap trap — the most expensive routing mistake

Aggregator platforms resell the same frontier models everyone else has. So a user's paid
subscription and the agent's own host tools routinely overlap on the biggest names, and
routing a shot to the paid platform out of habit spends a credit to get something that was
already free.

**The value of a subscription is the models nobody else has, not the ones it shares.** Before
routing any shot, ask which platform *uniquely* offers what this shot needs. `fleet.py
inventory` computes the overlap automatically and emits an `also_on_host` warning listing the
duplicated models — read it and route accordingly.

Three things justify paying when a host route exists, and they are all ceilings rather than
preferences:

- **Resolution.** Host video is commonly capped below 4K. A shot that must be delivered in 4K
  is a legitimate reason to spend.
- **Clip length.** Host clips are short (often 8s). A single unbroken longer take can't be
  faked by stitching.
- **A model the host lacks entirely.** This is the main event — the genuinely different
  aesthetic or capability the subscription was bought for.

Say which ceiling forced the decision when you route a shot to a paid platform. "Higher
quality" is not a reason; "needs 4K for the client master" is.

## Credit pools expire — spend them or lose them

Most subscription credits reset monthly and **do not roll over**. That makes a monthly pool an
allowance, not a reserve, and it changes production planning: credits sitting unused three days
before a reset are about to become nothing.

Record `resets` and `renews_on` in the fleet config so `inventory` can warn before the deadline.
When a large pool is close to resetting, say so — it is often the moment to shoot the ambitious
variant rather than the safe one.

Two more billing realities worth carrying into every estimate:

- **The displayed price can be an estimate, not the bill.** Some platforms show a figure on the
  generate button that the final charge exceeds, occasionally by multiples. Read the usage log
  after a run rather than trusting the panel, and never quote a platform's estimate to the user
  as a certainty.
- **Cost varies enormously *within* one model.** Duration, resolution, quality tier and optional
  features can swing the price by an order of magnitude under the same model name. "Which model"
  is not enough to predict cost; the configuration is what bills.

## Capability map — what to route where

Match the shot's need to a platform's strength, not to whatever is cheapest.

| Shot need | Look for a platform whose strength is | Notes |
|---|---|---|
| Hero product shot, physical realism | Physics fidelity, high resolution | Worth a manual UI step on the best platform available |
| Product with legible label/logo | Text legibility, image-to-video | Or composite the label in post |
| Talking presenter, lipsync | Avatar / talking-head specialism | Dedicated avatar tools beat general video models here |
| Human motion, walking, gesture | Human-motion quality | General models still struggle with hands |
| Fast style exploration | Cheap, fast iteration | Use drafts to choose a look, then commit |
| Character across many shots | Reference-image conditioning | See `consistency.md` |
| Product move landing on exact framing | First-and-last-frame interpolation | Strong control when available |
| Clip with usable synchronised audio | Native audio generation | Rare and valuable; most models are silent |
| Cuts or changes landing on a musical beat | **Audio reference input** | Supply the real track as a reference and instruct changes onto its beats. Beat-syncing in post is the fallback, not the method |
| A specific movement, exactly | **Video reference input** | Pass a clip of the move; described motion is reinvented every generation |
| Several looks or variants on one subject | Many reference images in one call | 5–9 image slots means one call, not one per variant |
| Stylised, comedic, meme-register | Stylisation over realism | Realism is not the goal here |

## Landscape notes (mid-2026 — verify before relying)

Written as guidance about *kinds* of capability, since specific versions move fast.

- **Google Veo (3.1 at time of writing)** — the standout for physical-product realism, text
  legibility, and the only one delivering genuinely usable native audio in a single pass.
  Per-call clip length is short (around 8s), so sequences are stitched in post. Available to
  consumer subscribers through Flow and the Gemini app (**UI only**); the API is a separate,
  usage-billed product.
- **Kling (3.0 / O3 line)** — strong human motion and character consistency, with multi-shot
  storyboarding and reference-to-video modes. Good for anything with people.
- **Runway (Gen-4 / Gen-4.5)** — the most mature reference-image system (accepts multiple
  reference images), longer clips, and audio added in the 4.5 line. Best choice when a brand
  character or product must persist across many shots.
- **Sora (2)** — cinematic quality and strong prompt adherence; multi-shot storyboard tooling.
- **Luma Ray (Ray3)** — first-and-last-frame interpolation ("Frames") makes it excellent for
  controlled product moves; HDR headroom is useful if you grade afterwards.
- **Alibaba Wan (2.6)** — reference-to-video with voice, fast drafts, and earlier versions
  have open weights if self-hosting matters.
- **MiniMax Hailuo** — economical drafts, high-motion social content.
- **Pika** — stylised work and multi-asset composition.
- **ByteDance Seedance (2.0 line)** — the strongest multimodal reference model available at the
  time of writing: one call accepts images, video and audio together (see the verified contract
  below), holds a subject across changes, and outputs up to 15s of multi-shot video with
  dual-channel audio. ByteDance's own materials describe output as watermark-free and cleared for
  commercial use — but **licensing and regional availability still need checking in your own
  jurisdiction** before commercial delivery; there were access restrictions reported after the 2026
  legal disputes. Reachable both through consumer UIs (mitte and others) and through aggregators.

Aggregators (**fal.ai**, **Replicate**, **magica.ai**) front many of these behind one key
with a uniform async pattern — submit, receive a request id, poll until complete. Useful
when your subscriptions don't cover a needed capability. Verify model identifiers before
use; they change.

### Seedance 2.0 — verified input contract (2026-07-31)

Worth writing down exactly, because guessing at it produces invented limitations. Confirmed
against the live schema and ByteDance's own published materials.

**Mixed-modality input in a single call**, addressed from inside the prompt with `@` handles:

| Input | Handle | Limit |
|---|---|---|
| Images | `@Image1`, `@Image2`… | up to 9 |
| Video clips | `@Video1`… | up to 3, 2–15s combined |
| Audio clips | `@Audio1`… | up to 3, ≤15s combined, mp3/wav |

Prompts address them directly: `@Image1 as the first frame, reference @Video1 for the camera
movement, use @Audio1 for the music`. Two entry modes exist — first/last frame (one image plus a
prompt) and universal reference (the mixed set above).

Output: 4–15s, six aspect ratios including `9:16`, native ceiling **2K** with 4K promised in a
later release, optional generated audio.

**What ByteDance itself names as still-weak**, which is more useful than any strength list:

- **Multi-subject consistency.** Multi-subject *interaction* is a headline strength, but holding
  two identities without drift is not. Two locked characters in one frame is a risk to design
  around — separate clips, or one in focus — rather than a wall.
- **Text rendering accuracy.** So prices, labels, legible copy and UI chrome stay in the edit.
  A cursor or a simple shape may well render; test it once cheaply rather than assuming either way.
- **Complex editing effects.**

**Delivery differs by route, and it matters.** The consumer UI takes local files by drag and drop.
The aggregator API accepts **public HTTPS URLs only** — a plate sitting behind an authenticated
URL cannot be fetched, which reads as "the model won't take images" when in fact the files never
arrived. Publish the plates first, or work in the UI.

### magica.ai API shape (verified 2026-07-26)

Worth documenting exactly, because it's one of the few aggregators whose *subscription*
credits are spent through the API rather than requiring separate purchase.

```bash
# Run a model — note: modelId in the PATH, parameters nested under `input`
curl -X POST https://api.magica.com/api/v1/nodes/{modelId}/run \
  -H "Authorization: Bearer $MAGICA_API_KEY_1" \
  -H "Content-Type: application/json" \
  -d '{"subModelId":"...","input":{"prompt":"..."}}'
# → {"runId": "..."}

curl https://api.magica.com/api/v1/nodes/runs/{runId} \
  -H "Authorization: Bearer $MAGICA_API_KEY_1"
```

| Need | Endpoint |
|---|---|
| Discover model ids | `GET /v1/models`, `GET /v1/models/search?q=video` |
| Input fields for a model | `GET /v1/models/{modelId}/schema` — **read before running** |
| Price of a model | `GET /v1/models/{modelId}/pricing` |
| **Exact pre-run cost** | `POST /v1/nodes/estimate-credits` with `{nodes:[{type,data,subModelId?}]}` |
| **Live credit balance** | `GET /v1/credits/balance` → `{availableBalance, formatted}` |
| Generated assets | `GET /v1/media-library` |

Keys are prefixed `gx_`, created at Settings → API Keys → Manage → Create Key, and shown
**only once**. Up to 10 per account. Default limits 60 requests/min and 1000/day per key,
configurable upward. `429` responses carry `Retry-After`.

The autonomous agent surface (Tasks) is **not** exposed via API — only Flow (workflows) and
Nodes (direct model execution). Nodes is what this skill uses.

### Alternative: MCP instead of scripts

magica also runs an MCP server at `https://api.magica.com/api/mcp` (23 tools), officially
supporting Claude Code, Claude Desktop, Cursor and Codex. Connecting it lets the host call
models directly without `generate.py`.

```bash
claude mcp add --transport http magica https://api.magica.com/api/mcp \
  --header "Authorization: Bearer $MAGICA_API_KEY_1"
```

Trade-off worth explaining to the user: MCP is less setup and needs no scripts, but it
binds to **one key at a time**, so multi-account rotation and the credit ledger are lost.
Use MCP for exploration; use `generate.py` when running a fleet of accounts.

## Routing procedure

1. Read `fleet.yaml`. Filter to platforms whose `can` covers the shot's need.
2. Split by `access`: ✅ api-with-credits, 🖐 ui, 💰 api-paid, 🚫 nothing suitable.
3. Rank the viable ones by `best_for` match, then by `priority`.
4. Check remaining budget; apply account selection.
5. **Present the options and ask** — see §3 of SKILL.md. Never skip.

**A subtlety worth internalising: `api` and `ui` cost the user the same — nothing new.**
One is convenient, the other needs a human click, but both spend credits already owned.
So convenience must never outrank quality: if a UI-only platform is better at this
specific shot, route there and accept the manual step. Only `api-paid` deserves a
penalty, because it means new money. `fleet.py plan` ranks this way already.

In practice that gives an asymmetry worth naming: **hero shots go to the best platform
available even when manual; drafts and volume go to whatever is automatic.** A single
manual step for the one shot that does the persuading is a good trade.

## Account selection

Two strategies, set by `prefer_fullest_account` in the fleet config:

- **Fullest first (default)** — pick the account with the most budget left. Right when
  accounts hold one-off allocations, because it keeps every account usable instead of
  exhausting them one at a time.
- **Round-robin** — plain rotation. Fine when budgets reset monthly and are unknown.

Either way, spread the work. `fleet.py` tracks spend in `.fleet-state.json` and warns when
an account drops below the configured threshold.

With per-account API keys, name them by pattern — `auth_env_pattern: PLATFORM_KEY_{n}` —
and the selected account resolves to its own key automatically. `fleet.py keys` reports
which are present without ever printing a value.

## Live cost and balance

Some platforms expose their real numbers, which turns the Routing Gate from an estimate
into a fact. Where available, use them:

- **Balance before quoting** — never tell the user "you have credits" without checking.
- **Exact pre-run cost** — if the platform can price a job before running it, quote that
  figure rather than a rule of thumb.

`generate.py` does this automatically in its dry run (the `live` block in its output) and
`generate.py --balances <platform>` reports every account on a platform at once. When a
platform has no such endpoint, fall back to the `est_cost_note` in the config and say
plainly that it is an estimate needing verification.

## Browser automation — do not

Automating consumer web UIs (Flow, Grok, and similar) **violates their terms of service** and
risks losing the accounts. Bot protections are active. There is no safe workaround, and the
downside — losing several paid accounts — dwarfs the convenience.

The correct pattern for UI-only platforms is the **generation packet**: the agent produces
exact prompts and settings, the human generates and downloads, the agent resumes. This is
fully legitimate and costs only the credits the user already owns.

---

# PART 2 — Delivery specs

More stable than Part 1, but still worth a sanity check for a paid campaign.

## Master file

Produce one master, then export per destination:

**1080×1920, 9:16, H.264, MP4, 30fps, yuv420p, faststart, AAC audio**

This covers TikTok, Reels and Shorts. Add a 4:5 export for the Instagram feed and a 16:9 for
YouTube proper.

## Safe zones — the detail that ruins ads

Platform UI overlays cover parts of the frame, and **each platform covers different parts.**
Text placed under a UI element is unfixable after posting. Design for this at composition
time — reserve the zone in the shot prompt (see the preservation clause in `consistency.md`).

### Instagram Reels (1080×1920 canvas)

| Edge | Reserve |
|---|---|
| Top | ~250px |
| Bottom | ~250–340px (profile row, caption, CTA) |
| Left / Right | ~60px |

### TikTok (1080×1920 canvas)

| Edge | Reserve |
|---|---|
| Top | ~150–200px |
| Bottom | ~350px (caption, controls) |
| **Right** | **~180px** (like / comment / share / profile column) |
| Left | ~60px |

**TikTok's right-hand column is the trap.** A caption centred for Instagram can sit directly
under TikTok's icon stack. If one asset must serve both, keep text within the *intersection*
of both safe areas — roughly centre-frame, above 350px from the bottom and 180px from the
right.

The `video-editor` skill applies per-platform safe zones automatically when you pass
`--safe tiktok` or `--safe reels`.

## Format specs

| | Instagram Reels | Instagram feed | TikTok | YouTube Shorts |
|---|---|---|---|---|
| Resolution | 1080×1920 | 1080×1350 | 1080×1920 | 1080×1920 |
| Ratio | 9:16 | 4:5 | 9:16 | 9:16 |
| Optimal length | 15–30s | — | 9–15s | 6–15s |
| Max length | 90s (Reels) | — | 10 min upload | 60s |
| Codec | H.264 | H.264 | H.264 | H.264 |
| Bitrate | 3.5–8 Mbps | 3.5–8 Mbps | 5–8 Mbps | 5–8 Mbps |
| Frame rate | 30fps | 30fps | 30fps (23–60 accepted) | 30fps |
| Audio | AAC, optional | AAC | AAC, sound-on culture | AAC |
| Captions | **effectively mandatory** | recommended | recommended | recommended |

4:5 (1080×1350) remains the preferred Instagram feed ratio — it occupies more vertical scroll
space than 1:1. Keep 1:1 as a cross-platform fallback.

## Loudness

Target around **−14 LUFS integrated with true peak at −1.5 dBTP** for social delivery.
Platforms normalise anyway; delivering hot only causes limiting artefacts.
`video-editor`'s `audio_pro.py` and its EBU R128 pass handle this — don't hand-roll it.

## Sound-on versus sound-off

- **Meta / Instagram** — assume muted. 80–85% of viewing has no audio. Every claim, joke and
  CTA must survive silently. Burn in captions.
- **TikTok** — sound-on by default, full-screen and immersive. Design *for* audio, but caption
  anyway for accessibility and for the muted minority.
- **YouTube Shorts** — mixed. Caption.

## Performance benchmarks

Useful for judging whether a creative is working. Hook rate is viewers still watching at 3s.

| Platform | Hook rate median | Top 10% | Best CTR length |
|---|---|---|---|
| Meta / Instagram | ~28% | ~45% | 15–30s |
| TikTok | ~33% | ~55% | 9–15s |
| YouTube | ~22% | ~38% | 6–15s |

Meta hook rate under 15% means the creative is dead — replace the opening rather than tuning
the middle. Completion rate favours shorter cuts than CTR does, so a 9s cutdown and a 20s
version serve different objectives and are both worth having.

UGC-style creative typically beats polished on hook rate and CTR; polished wins brand recall
and higher-ticket intent. See `creative-registers.md`.

## Multi-account delivery

Running several accounts in parallel has two failure modes:

1. **The same cut on two accounts.** Overlapping audiences read duplicates as spam. Use the
   variant registry (`campaign.py register`) and check before assigning.
2. **A character drifting across a campaign.** Always generate from stored canonical
   references, never from the last video's frames. See `consistency.md`.

Make variants by changing the hook first (highest leverage), then register, claim, length,
CTA. Change one variable at a time if you want to learn which one moved the numbers.
