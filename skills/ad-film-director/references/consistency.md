# Consistency Protocol

Load before generating anything involving a recurring product or character.

Consistency is a **protocol you follow**, not an outcome you hope for. Models drift. The
techniques below don't reduce drift by degrees — they change whether drift can happen at all.

Two separate problems, often confused:

- **Product consistency** — the object must be *the user's actual product*, identical in
  every shot. Failure here is fatal: a warped logo or wrong label makes the ad unusable.
- **Character consistency** — a person or mascot must be recognisably the same, within one
  ad and across a campaign that may run for months.

---

## Part 1 — Product consistency

### The one rule that matters most

**Never let a model invent the product.** Given only text, a model produces *a* shampoo
bottle — not the user's. The label will be wrong, the shape approximate, the logo garbled.
No amount of prompt detail fixes this.

Therefore: **always ask for real product photos in Phase 1.** If none exist, say plainly
that the product in the ad will not be their product, and offer the alternatives below.

### The canonical frame workflow

1. **Obtain or create one canonical reference frame** — the product, correctly lit per its
   category (see `product-artdirection.md`), on a clean background, label legible, at the
   angle that best describes its form (usually 3/4).
   - Best: a real photograph the user provides.
   - Acceptable: an image-generation pass that *edits* a real product photo into the desired
     lighting and background, keeping the actual label.
   - Last resort: fully generated. Say so, and expect label drift.

2. **Generate every product shot from that frame** using image-to-video, not text-to-video.
   The first frame is then literally the real product, and the model animates from it.

3. **Keep clips short.** 3–5 seconds. Drift accumulates with duration — an 8-second clip
   ends further from the reference than two 4-second clips do. Generate short, assemble later.

4. **Constrain the motion.** The more the product moves and rotates, the more surfaces the
   model must invent. Prefer camera movement over product rotation, and slow moves over fast.
   A slow push in on a static bottle is nearly always faithful; a fast tumble rarely is.

5. **Verify every clip.** Check the label, the logo, the closure, the proportions, the colour.
   Reject and regenerate rather than shipping a wrong product. Use the `watch` skill —
   see `delegation.md`.

### When you must show the product from several angles

Generate a small set of canonical frames first — front, 3/4, profile, detail — all consistent
with each other, all derived from real photography. Then treat each as the first frame for its
own clips. Do not ask one model call to rotate the product through 180° and stay faithful.

### Model features that help

Names vary by platform and change often. Look for:

- **Image-to-video / first-frame conditioning** — near-universal. Your primary tool.
- **First-and-last-frame interpolation** — supply both ends, model fills the motion. Excellent
  for a controlled product move that must land on an exact composition.
- **Reference-image conditioning** (sometimes "reference mode", accepting 2–3 images) — the
  most mature approach where available; lets you supply product plus environment plus style.
- **Reference-to-video** — some platforms accept a reference clip or image set to carry a
  subject across shots.

Check `platforms.md` and the platform's own current docs for which of these exists today.

### Reality checks

- Small text on packaging degrades in almost every model. If the label copy must be legible,
  plan to **composite it in post** rather than generate it. The `video-editor` skill can
  overlay a clean logo or label graphic.
- Reflective and transparent products drift most, because the model must invent what they
  reflect. Keep their surroundings simple and dark.
- If a product has an unusual shape, expect the model to normalise it toward something
  familiar. Short clips and tight camera moves suppress this.

---

## Part 2 — Character consistency

### Within a single ad

1. **Cast first.** Generate one canonical portrait of the character before any scene work:
   neutral expression, even light, clear features, framed head-and-shoulders. This is the
   reference for everything.
2. **Generate a small reference set from it** — front, 3/4, profile, and one full-body if the
   character will be seen in full. Each derived from the canonical portrait so they agree.
3. **Build each scene from the reference set**, via image-to-video or reference-image
   conditioning. Never describe the character in words alone and hope for a match — verbal
   descriptions produce family resemblance, not identity.
4. **Keep clips short** (3–5s) for the same drift reason as products.
5. **Fix wardrobe, hair and lighting in writing** and repeat those exact words in every
   prompt. Changing the described light changes the perceived face.

### Across a campaign, over months

This is where most projects lose the character. The discipline:

- **Store the canonical reference set as campaign assets**, not as scratch files.
  `campaign.py add-character --name mascot --refs ...` records them.
- **Always generate from the stored references**, never from a frame of the most recent video.
  Generating from generated output compounds drift — by video ten the character is someone
  else. This is the single most common cause of campaign-level drift.
- **Record what worked**: the platform, the model, the seed if exposed, and the exact wardrobe
  and lighting wording. Reuse them verbatim.
- **Re-verify against the original reference every few videos.** Put the canonical portrait
  and a new frame side by side and actually look.

### Hard limitations to design around

- **Two distinct referenced characters in one frame is unreliable in every current model.**
  Design around it: shot-reverse-shot instead of a two-shot, or one character in focus with
  the other out of focus or out of frame.
- Hands remain the most common failure. Count fingers in review. Avoid prompting complex hand
  action near the product unless you'll verify every frame.
- Faces in profile drift more than faces front-on.
- Children and animals are less controllable than adults.

### When maximum fidelity is required

Some platforms offer trained character adapters (LoRA-style) built from a set of images — this
gives the strongest identity lock available. If the user has that capability and a genuinely
recurring mascot, it's worth the setup: typically 15–30 varied images of the character, then
generate in short clips regardless.

**Gate this through the Routing Gate** — training costs money or credits and must be approved.

---

## Part 3 — Environment and style consistency

Often overlooked, and it undermines an ad as much as a drifting product.

- **Anchor the environment** the same way as the product: generate or select one canonical
  establishing frame, then derive shots from it.
- **Fix the palette and grade in words** and repeat them in every prompt. Drifting colour
  across shots is instantly noticeable when they're cut together, even if each shot looks
  fine alone.
- Better still: **grade the assembly, not the generations.** Ask for neutral-ish output and
  apply one consistent look in post via `video-editor`. Colour consistency achieved in the
  grade is reliable; colour consistency achieved by prompting is not.

---

## Part 4 — The preservation clause

Models fill space. If your composition needs an area kept clear — for a caption, a logo, or
a lower-third — say so explicitly, in the negative:

> …the lower third of the frame stays dark and empty throughout, no light creep, no objects
> entering that area

Without this the model will drift something bright into the exact zone you reserved, and the
caption becomes illegible. Text-zone planning belongs in the shot prompt, not in post.

---

## Review checklist before accepting any clip

Run through this every time. It takes seconds and saves regeneration credits.

1. **Is the product still the product?** Label, logo, colour, closure, proportions.
2. **Is the character still the character?** Compare against the canonical reference, not
   against the previous clip.
3. **Hands, fingers, teeth, eyes** — count and check.
4. **Physics** — does liquid pour downward, does fabric fall correctly, does anything
   float or intersect impossibly?
5. **Reserved zones** — did anything creep into the text area?
6. **Continuity with adjacent shots** — light direction, colour, time of day.

Any failure: regenerate rather than accept. **Flag the cost of the retry to the user first**
if regeneration consumes paid credits.
