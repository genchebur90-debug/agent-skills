# agent-skills

Portable [Agent Skills](https://agentskills.io) that work in **Claude Code**, **OpenAI Codex**
and **Kimi CLI** from the same source.

| Skill | What it does |
|---|---|
| [`ad-film-director`](skills/ad-film-director) | Turns any product into finished commercial ad films — art direction, script, generation routing, multi-platform delivery |

---

## ad-film-director

A commercial director, not a prompt generator.

Give it a product — shampoo, burger, car, apartment, SaaS — and it works the way an agency
would: figure out who's buying and why, pick the creative register, design the lighting for
that specific material, write the script and the hook, author the shot prompts, keep the
product and characters consistent, and deliver correctly-sized files for every platform.

### What makes it different

**It treats each product as its own problem.** Glossy plastic, seared beef and a lit window
at dusk want opposite lighting, pacing and length. The skill carries lighting schemes for
twelve product categories — a softbox placed to make one controlled highlight streak for
gloss, backlight from behind-above so steam and juice read for food, raking sidelight so
fabric has relief. Applying one look to everything is the clearest tell of amateur AI ad work.

**It never spends your money without asking.** Before any generation it runs a *Routing Gate*:
it shows you exactly where each shot can come from, grouped by what it costs you — credits you
already own, a manual step in a browser, or a top-up you'd have to buy. It always names the
cheapest viable path first, never pre-selects a paid one, and never quotes a price as certain.

**It works even where generation isn't automatable.** Most consumer AI subscriptions have no
API, so the skill has three modes:

| Mode | When | How it works |
|---|---|---|
| **Autonomous** | Shell + a working generation API | Generates, assembles, reviews and exports on its own |
| **Hybrid** | Shell, but platforms are web-only | Produces a copy-paste generation packet; you generate in the browser and drop files in `inbox/`; it resumes |
| **Text** | No shell at all (e.g. Notion) | Pure directing: brief, register, script, storyboard, prompts, captions — all in chat |

**It's configurable to your setup.** A `fleet.yaml` describes *your* platforms, accounts,
plans and budgets. The skill routes each shot to whichever platform can actually do the job,
rotates across your accounts so you don't drain one, and tracks what's left.

**It knows what it shouldn't do itself.** Post-production goes to the
[`video-editor`](https://github.com/genchebur90-debug/video-editor-skill) skill; watching
video goes to [`watch`](https://github.com/bradautomates/claude-video). Neither is required —
without them it degrades to a draft ffmpeg render and says so.

---

## Install

```bash
git clone https://github.com/genchebur90-debug/agent-skills.git
cd agent-skills/skills/ad-film-director
./install.sh
```

That symlinks the skill into every host's directory, so `git pull` updates all of them at
once. Then describe your platforms:

```bash
cp fleet.example.yaml fleet.yaml
$EDITOR fleet.yaml
./install.sh --check
```

Restart your agent host, and ask for an ad.

<details>
<summary>Other install options</summary>

```bash
./install.sh --project     # into ./.agents/skills and ./.claude/skills of a repo
./install.sh --copy        # copy instead of symlink (Windows)
./install.sh --check       # what's installed, what's missing
./install.sh --uninstall   # remove
```

Manual placement, if you prefer. The skill directory goes in whichever your host reads:

| Host | Path |
|---|---|
| Claude Code | `~/.claude/skills/` or `.claude/skills/` |
| Codex | `~/.agents/skills/` or `.agents/skills/` |
| Kimi CLI | `~/.config/agents/skills/`, `~/.agents/skills/`, or the Claude/Codex paths |

For Notion: paste `SKILL.md` into a page and designate it as a Skill in
Settings → Notion AI → Skills. The creative direction works fully; scripts don't run there.

</details>

### Requirements

- **Python 3.8+** — for the scripts. Stdlib only, nothing to `pip install`.
- **ffmpeg + ffprobe** — for assembly and export. `brew install ffmpeg` /
  `sudo apt install ffmpeg`.
- **A generation platform** — any subscription works. An API key means it can generate for
  you; without one it hands you paste-ready prompts.

Optional but recommended:

```bash
npx skills add genchebur90-debug/video-editor-skill -g   # post-production
npx skills add bradautomates/claude-video -g             # visual review
```

---

## Using it

Just ask. The skill triggers on ad, promo, commercial, product video, or campaign requests.

```
Make me three Reels variants for this shampoo — here's a product photo.
```

It will ask a few things it can't infer, propose a register with reasoning, then stop at the
Routing Gate and show you where each shot can be generated and what it costs. After you
choose, it produces either finished files or a generation packet.

### What comes out

**Autonomous mode** — finished MP4s per platform, correctly sized, captioned, loudness-normalised,
QC-checked, logged in the campaign registry.

**Hybrid mode** — a `packet.md` with numbered shots: exact prompt, platform, account, aspect
ratio, duration, reference image to attach, and the filename to save. Generate, drop into
`inbox/`, say done.

**Text mode** — the whole thing in chat, formatted to paste anywhere.

### Scripts

All optional; the skill works without running any of them.

```bash
python3 scripts/fleet.py detect                  # mode + usable platforms
python3 scripts/fleet.py plan --needs plan.json  # routing options, grouped by cost
python3 scripts/fleet.py budget                  # credits left per account

python3 scripts/packet.py --plan plan.json --out packet.md
python3 scripts/generate.py --plan plan.json     # dry run; --confirm to actually generate

python3 scripts/campaign.py init --name summer-launch
python3 scripts/campaign.py add-character --name mascot --refs a.png b.png c.png
python3 scripts/campaign.py next --account ig_main
```

---

## Running several accounts

Built for it. The campaign registry stops the two things that go wrong at scale:

**The same cut on two accounts.** Overlapping audiences read duplicates as spam.
`campaign.py register` refuses a variant already placed on that account, and warns when one
starts appearing in several places.

**A character drifting over months.** The usual cause is generating video 8 from a frame of
video 7 — drift compounds until it's a different person. The registry stores canonical
reference images and the exact wardrobe and lighting wording, and the skill always generates
from those.

```bash
python3 scripts/campaign.py check --account ig_main   # what has this account had?
python3 scripts/campaign.py next  --account ig_main   # what's still unused
```

---

## Structure

```
skills/ad-film-director/
├── SKILL.md                      the director: modes, seven phases, routing gate
├── fleet.example.yaml            template for describing your platforms
├── references/
│   ├── product-artdirection.md   12 categories → light, texture, camera, pace
│   ├── creative-registers.md     humour / commercial / arthouse / UGC
│   ├── script-craft.md           structures, hooks, VO copy, CTA
│   ├── platforms.md              capabilities, access, specs, safe zones
│   ├── consistency.md            product and character protocol
│   └── delegation.md             sibling commands and fallbacks
├── scripts/                      fleet · packet · generate · campaign
├── assets/brief-template.md
└── install.sh
```

`SKILL.md` stays under 500 lines and the references load only when the current phase needs
them — progressive disclosure, so the skill doesn't eat your context on every run.

---

## Notes

**On accuracy.** `references/platforms.md` holds model versions, endpoints and pricing
guidance. This field moves monthly, so the skill treats all of it as needing verification and
never quotes a price as certain. If something's stale, that file is the only one to update.

**On browser automation.** The skill will not automate consumer web UIs. It violates their
terms of service and risks the accounts. For web-only platforms it uses the generation packet
instead — which costs only credits you already own.

---

## Licence

MIT. See [LICENSE](LICENSE).
