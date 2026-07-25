# Creative Registers

Load in Phase 2b. Choosing the register is a strategic decision, not a matter of taste.
A technically flawless ad in the wrong register fails.

Four registers cover almost all commercial short-form work.

---

## Quick decision matrix

| If this is true | Register |
|---|---|
| Impulse purchase, low price, young audience, TikTok-first | **UGC** or **Humour** |
| Considered purchase, mid-to-high price, trust matters | **Straight commercial** |
| Luxury, fragrance, jewellery, premium property, brand-building | **Arthouse** |
| Challenger brand fighting an established leader | **Humour** |
| Category is boring and everyone is polished | **Humour** or **UGC** |
| Regulated category (pharma, finance, health claims) | **Straight commercial** |
| Software, apps, productivity | **Humour** or **UGC** |
| Cold traffic, direct response, performance campaign | **UGC** |
| Retargeting, brand recall, high-ticket close | **Straight commercial** or **Arthouse** |

**Performance reality:** UGC-style creative outperforms polished production on hook rate
(roughly +31%) and click-through (roughly +33%) because it reads as native content rather
than as an ad. Polished production wins on brand recall and on higher-ticket purchase intent,
because production value itself signals substance. Strong advertisers run both, weighted
around 60% UGC for prospecting and 40% polished for retargeting and brand.

Never let this table override an explicit brand guideline. If the user has a defined tone,
that wins.

---

## 1. UGC — user-generated, or convincingly like it

**What it is.** Shot as if by a customer on a phone. Imperfect framing, real environments,
direct address to camera, natural speech. The persuasion comes from *apparent authenticity*.

**When it wins.** Cold traffic. Impulse categories. Cosmetics and skincare — by a wide
margin the strongest performer there. Apps. Supplements. Anything a real person can
demonstrate.

**Craft rules.**
- Imperfection is the point. Slightly off-centre framing, a hand adjusting the phone, a
  natural stumble in speech. Perfect framing destroys the effect.
- Handheld, natural light, real rooms. A kitchen at 8am beats a studio.
- Open mid-thought, as if the camera started late: "…okay so I've been using this for
  three weeks and —"
- The product enters the frame the way a real person would hold it — not presented.
- Speak to one person, not an audience.
- Captions styled like native platform captions, not like brand typography.

**In AI generation.** Ask explicitly for phone-camera characteristics: slight handheld drift,
natural window light, a real domestic interior, a slightly imperfect frame. Models default to
polished cinematic output, so you must actively suppress it. Avatar tools (HeyGen and similar)
are strong here for a presenter — that's their home ground.

**Risks.** Regulated categories: an authentic-sounding personal claim is still a claim.
Never fabricate testimonials or results.

## 2. Humour

**What it is.** A comic premise carries the product message. Persuasion through the goodwill
of having been entertained.

**When it wins.** Challenger brands. Boring categories where everyone else is earnest. Low
price points. Software. Food. Gyms. Younger audiences. Anywhere a polished ad would be
scrolled past on sight.

**Craft rules.**
- **One joke, one setup, one turn.** Fifteen seconds holds a single comic idea.
- The product should be *inside* the joke, not appended after it. If you could remove the
  product and the joke still works, the ad fails.
- Land the turn by second 6–8, then let the product be the resolution.
- Understatement outperforms mugging. Deadpan reads as confident; frantic reads as desperate.
- Exaggerate the *problem*, never the product's performance.
- Test it muted. If the joke needs audio, half the Meta audience misses it.

**Comic structures that work in 15 seconds.**
- *Escalation* — the problem gets absurdly worse, then the product ends it.
- *Deadpan mismatch* — an epic treatment of a trivial problem.
- *Expectation break* — sets up a cliché, then swerves.
- *Understated hero* — everyone panics, one person calmly uses the product.

**In AI generation.** Comic timing lives in the edit, not the generation. Generate slightly
longer clips than you need so you can find the beat. Facial comedy is still unreliable —
prefer situational and physical humour over subtle expression work.

**Risks.** Humour that mocks the customer. Jokes that overshadow recall — funny but nobody
remembers the brand. Cultural humour that doesn't travel.

## 3. Straight commercial

**What it is.** Confident, well-made, unironic persuasion. Clear promise, clean
demonstration, credible tone. The default register of professional advertising.

**When it wins.** Considered purchases. Mid-to-premium pricing. Trust-dependent categories:
clinics, finance, supplements, cars, appliances. Retargeting. Enterprise software. Any
category where looking substantial is part of the pitch.

**Craft rules.**
- Lead with the benefit, demonstrate it, prove it, ask for the action.
- Production value carries meaning here: clean light, stable camera, intentional grade.
- Show the product working, not the product sitting.
- Specificity builds credibility. "Charges in 22 minutes" beats "charges fast."
- Voiceover, if used, should be plain and unhurried. Announcer-voice reads as dated.
- One claim, proven visually. A claim you show beats three you state.

**In AI generation.** This register benefits most from the highest-quality generation you
have available — it's worth routing hero shots to a manual UI on a premium platform. Physical
realism and clean product fidelity matter more here than anywhere else.

**Risks.** Blandness. The failure mode is competent and forgettable. A distinctive visual
idea is what saves it.

## 4. Arthouse

**What it is.** Mood, atmosphere and craft carry the message. Sparse or no dialogue. The
product appears as an object of desire rather than a solution to a problem.

**When it wins.** Fragrance. Jewellery and watches. Premium spirits. High-end property.
Fashion. Brand films. Anything where the purchase is emotional and the price is high enough
that justification would cheapen it.

**Craft rules.**
- Withhold. Show less than you want to. Suggestion outperforms explanation.
- Let shots breathe: 3–4s each, sometimes longer.
- Sound design over music, or music that's genuinely good rather than stock-uplifting.
- Extreme control of light and colour. A single, committed palette.
- Text minimal. Often just the product name at the end.
- No feature list, no CTA beyond the brand mark. Asking too directly breaks the spell.

**In AI generation.** The most forgiving register technically, because abstraction and
shallow focus hide model artefacts. Slow moves, macro detail and controlled darkness all
generate well. Frequently the best register when generation quality is limited.

**Risks.** Beautiful and meaningless. If nobody can tell what's being sold, it isn't an ad.
Also fails badly on cold performance traffic — it needs an audience that already cares.

---

## Mixing registers

Usually a mistake within a single ad — mixed tone confuses. But it works well **across** a
campaign: arthouse for brand-building on the main account, UGC for prospecting on a second,
humour for the experimental one. The variant registry (`campaign.py`) keeps track of which
register went where.

The one reliable *within*-ad mix: UGC opening as a hook, resolving into a polished product
shot. Native-feeling entry, credible payoff.

---

## Presenting the choice to the user

Don't ask "what register do you want?" — most people don't think in these terms. Instead
recommend one with a one-line reason and offer one alternative:

> For a shampoo aimed at 20-somethings on Reels I'd go **UGC** — cosmetics is the category
> where it performs best, and a real person showing hair that stopped frizzing is more
> persuasive than a studio bottle shot. Alternative: **straight commercial** if you want
> the brand to read premium rather than friendly. Which direction?

Then commit fully. A half-committed register reads as indecision.
