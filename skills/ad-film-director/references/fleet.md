# Fleet — the user's own generation platforms

Load in §4 of `SKILL.md`: the first time a user works with this skill, whenever the Routing
Gate needs to know what is available, and whenever a subscription changes.

Every user's set of platforms is different, so the skill reads a `fleet.yaml` describing
what *this* user actually has.

### First run: set it up FOR them, by asking

**Never tell the user to go read a YAML file.** Most people asking for an ad have no
interest in config schemas, and sending them to edit one is how a skill gets abandoned.

If `fleet.yaml` doesn't exist (`fleet.py detect` reports `using_example_config: true`),
run the interview:

```bash
python3 scripts/fleet.py setup     # returns the questions to ask, not a config
```

Ask those questions in plain language, in small batches, then **write `fleet.yaml`
yourself** and tell them what you wrote. The whole exchange should feel like:

> Which AI tools do you already pay for that can make images or video?
> — *I've got Google AI Pro, a few HeyGen accounts, and 6 magica accounts.*
>
> Good. For each: how many accounts, and do you use them in a browser or do you have an
> API key?
> — *7 Google, 10 HeyGen, 6 magica. All in the browser, I don't know about API keys.*
>
> That's fine — I'll set them all up as browser-based, which means I write you exact
> prompts and you generate. One exception worth knowing: magica does include API access
> with your subscription, so I could generate there automatically if you get a key. Want
> me to explain how, or leave it manual for now?

Note what happened there: no jargon, sensible defaults, and the *one* upgrade worth
mentioning was surfaced without being pushed. Do that.

Never ask the user to paste an API key into the chat. Keys belong in the environment —
a shell profile, or the host's own credential store when it has one. You only ever check
whether they're present, never what they are.

### Where the config lives

`fleet.yaml` describes real accounts and balances, so it is gitignored and never shipped
with the skill. That also means it must not live *only* inside the skill folder, which a
reinstall overwrites. Search order:

| Order | Location | Use |
|---|---|---|
| 1 | `$FLEET_CONFIG` | Explicit override; wins over everything |
| 2 | `./fleet.yaml` | A per-project fleet, alongside the work |
| 3 | `<skill>/fleet.yaml` | Classic location |
| 4 | `~/.config/ad-film-director/fleet.yaml` | **Durable** — survives reinstalling the skill |

Write a user's config to **option 4** unless they ask otherwise, and `chmod 600` it. The
spend log and rotation cursor follow the config, except when the only config found is the
shipped example — then state goes to the durable directory so history isn't wiped by an
update.

Never assume the skill's folder is laid out as `scripts/…`. Hosts install skills in
different shapes, some flat; the scripts locate their own root by looking for `SKILL.md`
or `fleet.example.yaml` and work in either.

### Day-to-day commands

```bash
python3 scripts/fleet.py inventory                 # what the user owns — run this first
python3 scripts/fleet.py detect                    # mode + what's usable
python3 scripts/fleet.py keys                      # which keys are set (values never shown)
python3 scripts/fleet.py plan --needs plan.json    # routing options per shot
python3 scripts/fleet.py budget                    # credits left per account
python3 scripts/fleet.py pick --need video --best-for physical-realism
python3 scripts/generate.py --balances magica      # live balance, every account
```

### Know the arsenal before you promise anything

**Run `inventory` once at the start of a production.** It answers in one call the question you
would otherwise guess at: what can this user actually generate with? Plans, seats, credits
left, what resets when, and which route costs them nothing. Guessing produces two failures —
promising a shot the fleet can't deliver, and sending someone to a browser for something that
renders here for free.

Say something when the `warnings` array does. Three kinds matter:

**`expiring`** — credits that reset and don't roll over. A monthly pool is an allowance, not a
reserve; unspent credits are simply lost. If a large pool is days from resetting, mention it:
it changes what's worth making this week.

**`balance_stale`** — a hand-typed balance nobody has checked recently. Platforms without an
API can't be read programmatically, so the figure is only as good as its `verified_on` date.
Call it an estimate and ask them to confirm before planning a big run around it.

**`also_on_host`** — the platform can run a model the host renders for free. Never spend a
paid credit on a model that is free here. Those credits exist to buy what the host *cannot*
do; spending them on overlap is waste.

### Where each shot should come from

`access` ranks routes by what they cost the user, and `host` is the cheapest that exists — no
key, no browser step, none of their credits.

| Route | Marker | Use it for |
|---|---|---|
| `host` | ✅ HOST | Anything the host does well. First choice. |
| `api` | ✅ INCLUDED | Volume, drafts, iteration — automatic, credits already owned. |
| `ui` | 🖐 MANUAL | Models the host lacks, or a ceiling only this platform clears. Worth the manual step for hero shots. |
| `api-paid` | 💰 TOP-UP | Only with explicit approval and an estimate. |

The decision is capability, not convenience: **route by what a platform uniquely gives you.**
A subscription's value is the models nobody else has, not the ones it shares with the host.
When a host clip is capped at 8 seconds or 1080p and the shot genuinely needs more, that is a
real reason to spend a credit — say which constraint forced it.

Host shots come back as **render orders**, not files: `generate.py` prints the tool, the
arguments and a `save_as` path. Execute each with your own tools, write to exactly that path,
and assembly proceeds identically for host, API and manual footage. The filename contract is
the one `packet.py` already uses, so nothing downstream can tell how a clip arrived.

Rule 1 still applies to host shots. Free is not the same as approved: show the slate and the
shot list, get a yes, then render.

### What the fleet layer gets right

**Convenience never outranks quality.** `api` and `ui` cost the user the same — nothing
new. So a UI-only platform that's *better at this shot* wins, manual step and all. Only
`api-paid` is penalised, because it means new money. In practice: hero shots go to the best
platform even when manual; drafts and volume go to whatever is automatic.

**Several accounts on one platform are used intelligently.** With `prefer_fullest_account`
on (the default), the account with the most credits left is chosen — so all of them stay
usable instead of one being drained. Per-account keys resolve automatically from
`auth_env_pattern`. Spend is tracked in `.fleet-state.json`.

**Real numbers where they exist.** Some platforms expose a live balance and an exact
pre-run cost. `generate.py`'s dry run surfaces those in a `live` block — quote *those*
figures at the Routing Gate, not a rule of thumb. Where a platform has no such endpoint,
fall back to `est_cost_note` and say plainly that it's an estimate needing verification.

`references/platforms.md` has per-platform capabilities, access paths, exact endpoint
shapes, and current model notes. **Treat version numbers and prices there as needing
verification** — this field moves monthly.

---
