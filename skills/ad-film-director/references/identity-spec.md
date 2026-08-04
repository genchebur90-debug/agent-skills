# Identity Spec — what "the same product" means, per family of product

Load in Phase 1, the moment you know what the product is. `consistency.md` says the product
must stay identical; this file says **identical in what respects**, which is the question you
have to answer before you can check anything.

The reason it exists: "is the product still the product?" is unanswerable as written. A
burger has no label. A car has no cap. An apartment cannot be photographed on a black
sweep. Every category has a different short list of features a buyer uses to recognise this
object and no other, and the ad fails at exactly the moment one of them quietly changes.

So the spec is small on purpose. Not a description of the product — **the few facts that
would make a buyer say "that's not it"**.

---

## The interview, once, in Phase 1

Four questions, asked about any product from a wrench to a mortgage:

1. **What would make a buyer say "that's not the one I know"?** Three to six features, no
   more. If you list twelve you have written a description, not an identity.
2. **What is allowed to vary?** Angle, distance, background, hands holding it, time of day.
   Naming this is as useful as naming the fixed parts, because it tells you what you may
   generate freely.
3. **Which variant is this?** 50ml or 100ml, hardtop or convertible, single or double patty.
   The wrong variant is a wrong product that survives every check written in general terms.
4. **What must never appear?** Competitor items, the old packaging, the discontinued colour,
   a second unit of the same product in frame.

Then record it, because an identity that lives in the conversation dies with the context
window:

```bash
python3 scripts/campaign.py add-product --name noir-50 --profile pack \
  --refs photos/flacon_front.jpg photos/flacon_34.jpg \
  --identity "50ml square amber-glass flacon, three-line black lockup, gold collar" \
  --label-lines "MAISON X" "NOIR ABSOLU" "50 ml e" \
  --closure "faceted black cap on, unless the shot is an actual spray" \
  --colour "amber juice, black type, gold collar" --material "thick clear glass" \
  --must "gold collar ring" "circumflex over the o in Absolu" \
  --forbid "a second bottle in frame" "the 100ml version"
```

`campaign.py lockcard --text` then prints that block on demand, and `packet.py` puts it on
every shot page. That is the whole mechanism: identity stops being something you remember
and becomes something the pipeline carries.

---

## Families

Pick the nearest with `--profile`. The list is not a taxonomy of products, it is a taxonomy
of *how things go wrong*.

### `pack` — bottles, jars, tubes, boxes, cans, fragrance, cosmetics, drinks

**Identity:** exact label wording and line order · logo lockup · closure present · vessel
silhouette · material and tint · fill level and liquid colour.

**How it fails:** the type garbles or vanishes; the cap goes missing and the pack reads as
in-use; the silhouette normalises toward a generic bottle; a transparent fill turns milky.

The type *is* the product here. Never prompt a blank pack — a bottle without its lockup is a
generic object, and every frame containing one is rejected. Full argument, and the recorded
case where a self-imposed "no text on the glass" ban cost two hours, is in `consistency.md`.

### `food` — burgers, pizza, coffee, ice cream, plated dishes

**Identity:** build and layer order · portion and proportions · doneness and colour ·
garnish and sauce · the vessel or wrapper it is served in.

**How it fails:** the model adds a second patty, swaps sesame for plain, changes the cheese
melt, garnishes with something the kitchen doesn't serve. Nobody notices in the frame; the
client notices in one second.

Food has a further constraint the other families don't: it must look *edible*, and edible is
a lighting problem before it is a prompt problem — see `product-artdirection.md` §2. Steam,
gloss and condensation are the identity of freshness, not decoration.

### `vehicle` — cars, motorcycles, bicycles, boats, machinery

**Identity:** model and body shape · grille and light signature · wheel design · body colour
and finish · badges · the trim details that separate versions.

**How it fails:** the light signature is the first thing to drift and the first thing an
enthusiast spots. Wheels change design between shots. The badge becomes a smear. A model gets
"improved" toward a more generic silhouette.

Never generate a vehicle from words if it is a real make. Plate it from photographs and move
the camera, not the car.

### `space` — apartments, houses, hotels, restaurants, gyms, clinics

**Identity:** layout and sightlines · window shape and the view through them · floor and wall
finishes · fixed furniture · light direction and time of day.

**How it fails:** the same room grows a different window, the kitchen island moves, the view
outside changes city between shots, morning light becomes evening halfway through the ad.

Continuity here is spatial as well as visual: two shots of one room must be reconcilable as
the same room. Plate the establishing frame, derive every other angle from it, and keep a
written note of where north is.

### `apparel` — clothing, shoes, bags, jewellery, watches

**Identity:** cut and silhouette · colourway · material and weave · hardware and fastenings ·
logo placement · dial and hand details on a watch.

**How it fails:** stitching invents itself, a strap changes buckle, the colourway shifts half
a tone under a warm grade, a watch grows a fourth subdial.

Fabric must move to read as fabric, and movement is where the weave drifts. Short clips.

### `device` — phones, laptops, appliances, hardware, tools

**Identity:** form factor and proportions · port and button layout · finish and colour ·
branding placement · screen content when the screen is visible.

**How it fails:** ports multiply or migrate, a bezel thins, the logo relocates, the screen
shows invented UI.

Screen content is composited, never generated. Treat it as lettering.

### `screen` — apps, SaaS, dashboards, games

**Identity:** the real UI, captured not invented · brand colours and type · the exact screen
states shown · cursor and gesture behaviour.

**How it fails:** the model produces something that looks like software and is not the
product. This family has the highest failure rate of all, because a plausible interface is
easy to generate and worthless.

Record the screen. Animate the recording. AI generation belongs to the environment around the
device, not to the pixels on it.

### `service` — salons, courses, travel, logistics, insurance

**Identity:** the proof object the buyer actually sees · staff look and uniform · environment
and signage · documents or interfaces shown.

**How it fails:** there is no object, so nothing anchors the ad and every shot is a different
business. Find the proof object first — the chair, the certificate, the van, the dashboard —
and lock it like a product.

### `person` — a founder, a creator, a named spokesperson

**Identity:** face and build · wardrobe · hair · voice and accent · the setting they always
appear in.

Follow `consistency.md` Part 2 for the character workflow. The addition here: a real person
carries legal identity too. Do not generate a recognisable real human without permission, and
never put words in a real person's mouth that they did not approve.

---

## Anything not on the list

Take the nearest family and correct it with `--must`. The families are shortcuts, not a
closed set. The test is the same for a wrench, a funeral service or a B2B logistics API:

> Name the three to six features whose change would make the buyer say "that's not it".
> Those, plus the plate, are the identity. Everything else is direction.

If you genuinely cannot name three, the product is being advertised on a promise rather than
an object — that is a `service`, and the work is to find its proof object.

---

## Where the spec is used

| Moment | Use |
|---|---|
| Phase 1 | Ask the four questions, record with `campaign.py add-product` |
| Phase 4 | Identity constrains art direction: a locked colourway limits the palette |
| Phase 6, per prompt | `campaign.py lockcard` — the block beside the prompt, never inside it |
| Phase 6, before generating | `planlint.py` refuses shots that hold a locked thing with no plate |
| Phase 7, per clip | `campaign.py verify --product X` fields, plus `identity.py sheet` |

**The distinction that matters in the prompt itself:** the prompt *points* at the product
("the flacon from @Image1"), it never *describes* it. The lock card sits next to the prompt
so a human can check the output — putting its contents into the prompt body would be exactly
the second description that production-order.md forbids. `planlint` warns when a prompt starts
spelling out a locked product's material, colour or label.
