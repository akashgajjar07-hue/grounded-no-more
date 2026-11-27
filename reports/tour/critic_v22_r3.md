> AI-generated review used during development — not a review by a human aviation professional.

# Tour motion critique: v2.2, round 3 (independent, judged from video frames only)

**Method.** I used the four recordings in `private/tour_videos/` as they were (no re-recording): Chromium and WebKit, at 1440x900 and 390x844, full 6-step tour in Play mode. Headless Chromium decoded each one at 10 fps (`<video>` + canvas, driven by `.venv/bin/python` + Playwright). That gave 306, 308, 306 and 311 frames. Frame N is at t = N x 100 ms. I built contact sheets for frames −3…+16 around every transition and opened single frames at full size where something looked wrong. I did not read the tour code.

**WebKit recorder artefacts (discounted).** Frames 0–2 (1440) and 0–3 (390) are fully white. About 120 frames (1440) and 77 frames (390) are exact copies of the frame before (diff < 0.05). These are screencast stalls; for example, WebKit 1440 frames 25–27 are frozen. I did not count them as page problems. One side effect: WebKit shows fewer in-between frames, so its transitions look cleaner than Chromium's. The Chromium recordings are the stricter evidence.

## Pattern seen in every transition
1. The card fades out in about 2 frames. The scrim stays down.
2. For about 300–500 ms nothing moves: card gone, old target still lit. Sometimes a **"Loading next step…" pill** shows at the bottom centre (Chromium 1440 f24, f127, f229; Chromium 390 f24).
3. The sidebar's active item switches to the next page **before** the breadcrumb and content change. For 1–2 frames the sidebar names page N+1 while the top bar and content still show page N (Chromium 1440 f24–25 "AOG Response Lab" vs "Mission Control"; f76 "Parts Intelligence" vs "AOG Response Lab"; f179 "Network Positioning" vs "Rotable & Repair").
4. The spotlight starts its glide **over the old page**, then the content crossfades under it. For about 1 frame both pages show at once, and the overlap is most legible inside the bright spotlight.
5. The spotlight settles in 2–3 frames (about 200–300 ms). After that it does not move again.
6. The card fades in (or the phone sheet slides up) only after the spotlight is still. **I never saw the spotlight move while the card was visible.** The card never covers its target. No chart replays: histogram, frontier curve and bar rows stay put from settle to card-out.

## Observations by transition

### Chromium 1440
- **open → 1 (f17–30):** The scrim fades in smoothly (f18–23). f24 shows the "Loading next step…" pill. **f25: a small, empty spotlight rectangle appears in the middle of the hero, between the headline and the plane.** It has no target. f26: heavy double exposure. The hero headline "…ight spare, at the… craft needs it." reads clearly *inside* the new timeline spotlight, and the old page ghosts across the lower half. f27: settled, with a faint ghost still bottom right. f29–30: the card fades in, placed bottom right, clear of the target.
- **1 → 2 (f71–82):** Card out f72–73. f76: sidebar ahead of the breadcrumb. f77: the breadcrumb text is double-exposed ("AOG Res… / Parts Intelligence" overprinted). The spotlight is a tall morphing box over the *old* AOG page and lights the half-faded timeline and a "Send a spare…" heading. f78: new page, still a ghost in the right column, spotlight not yet in place. f79: settled on the aircraft. f81–82: card fades in to the right of the plane. Clean afterwards.
- **2 → 3 (f122–132):** Card out f123. f124–127: about 400 ms idle; the pill shows at f127. f128: the spotlight starts growing on the old plane. f129: new page, spotlight oversized, cutting through the "(NB)" dropdown and the "17 pooled spares…" line. f130: still moving, and the **right edge clips "AED 1.8M" and "DERIVED"**. f131: settled on the KPI strip. f132: card to its left.
- **3 → 4 (f175–184):** f179: spotlight slides right and clips the first KPI ("CHANCE THE PART IS…" cut). **f180: worst frame in this recording.** Inside the spotlight the old KPI strip and the new plan table overprint into an unreadable jumble. f181: settled, though the lower edge is tight on the last table row. f183–184: card below the table.
- **4 → 5 (f225–234):** f229: pill. **f230: the spotlight runs off the right edge of the viewport (clipped).** f231: double exposure of the old table and the new urgent row. f232: still resizing. f233: settled on the GN-32-R014 row. f234: card below the row.
- **5 → 6 (f275–284):** Card out f276–277. **f280: the spotlight grows to cover four rows of the old Actions table, a wrong target.** f281: the old table and the new frontier chart overprint inside the spotlight. f282: settled on the chart. f284: card to its right. No redraw of the curve.

### Chromium 390
- **open → 1 (f17–31):** Smooth scrim fade (f18–23). f24: pill over the plane. **f25: the spotlight lands on the hero copy and lights "ion, before a / raft needs it." mid-word.** This is a clearly wrong target, and the most visible glitch in the four videos. f26: new page with the spotlight still growing and clipping "T+14h" and "Grounded 14 h". f27–28: settled. f29–31: the sheet slides up once and stops.
- **1 → 2 (f72–83):** Sheet slides down (f72–73). The scrim and old spotlight hold. f77: old page fades with the spotlight on it. f78: new page, spotlight already on the aircraft. Clean. f81–83: sheet up. **This is the best transition in the set.**
- **2 → 3 (f123–134):** Sheet down f123–124. f125–128: about 400 ms idle. f129: new page, the spotlight's bottom edge cuts through "This is the hub pool. Switch to 'One…". f130: settled. f132–134: sheet up.
- **3 → 4 (f175–185):** About 400 ms idle (f176–179). **f180: double exposure inside the spotlight; the KPI grid and the plan table overprint.** f181: settled.
- **4 → 5 (f226–236):** f231: double exposure of the table and the urgent row. f232: settled.
- **5 → 6 (f277–287):** f282: double exposure of the Actions rows and the frontier chart. f283: settled.

### WebKit 1440 (stalls discounted)
- **open → 1:** f27: sidebar ahead of the breadcrumb. **f28: spotlight mid-glide, clipping the right of the timeline ("T+14 h", "Released" cut).** f29: settled. f30–31: card in.
- **1 → 2:** f79: spotlight mid-morph over the crossfading pages. f80: settled. f82–83: card in.
- **3 → 4:** f179: spotlight slides off the KPI strip, clipped at the right. f180: new page with the spotlight partly offset. f181: settled.
- **5 → 6:** **f280: spotlight covers six rows of the old Actions list (wrong target).** f281: oversized over the chart. f282: settled.
- Other transitions follow the same pattern with fewer in-between frames.

### WebKit 390 (stalls discounted)
- **open → 1:** **f28: a small spotlight over the hero shows a ghost of "at the right / before an / needs it" inside it, overlaid on the new timeline.** f29–30: settled. f31–33: sheet up.
- **3 → 4:** f182: old page fades. f183: new page with the spotlight already in place. Clean.
- **5 → 6:** f283 → f284. Clean.
- WebKit 390 is the cleanest of the four combinations, partly because the recorder captured fewer frames.

## Checklist summary
| Check | Result |
|---|---|
| Blank, dark or flat frames | None from the page. The scrim dims to about 13/255 luminance, but content stays readable. WebKit white and frozen frames are recorder artefacts. |
| Two pages visible at once | **Yes, about 1 frame per transition**, most legible inside the spotlight (C1440 f26, f77, f180, f231, f281; C390 f180, f231, f282; W390 f28). |
| Card or spotlight jumping or moving more than once | The card enters and leaves once per step. The spotlight is one continuous glide of 2–3 frames, but it **starts while the old page is still showing**. |
| Spotlight moving while the card is visible | Never seen. |
| Spotlight on a wrong or empty target, or clipped | **Yes, every transition, mid-glide:** C390 f25 (hero text), C1440 f25 (empty box), f280 / W1440 f280 (old table rows), C1440 f130, f230 and W1440 f28 (clipped at an edge). Every settled position is correct and unclipped, though C1440 f181 is tight at the bottom. |
| Text reflow while visible | None seen. |
| Chart replaying | None seen. |
| Card covering its target | Never. |
| Calm and premium? | Holds are calm. Each change between steps reads as "fade out, wait, flicker, settle" rather than one gesture. The pause with the "Loading next step…" pill and the 1-frame overprint read as engineering, not choreography. |

## Scores (1–5)
- **Smoothness: 3.9.** About 59 fps feel during holds, and the glide itself is short and eased. Each transition still has a visible hitch: a 300–500 ms dead pause after card-out, then a 1-frame overprint and a 2–3-frame settle that starts over the wrong content.
- **Polish: 3.6.** The "Loading next step…" pill, a spotlight briefly lighting random hero copy or old table rows, edge clipping mid-glide, and the sidebar active state changing ahead of the breadcrumb are each small. Together they appear in every transition, and that is below a premium bar.
- **Continuity: 3.8.** The scrim never drops, the spotlight is a single element that glides, and the card only appears once the spotlight is still. All good. The old and new page share one frame instead of handing off cleanly, and the chrome (sidebar vs top bar) changes out of sync.
- **Legibility: 4.4.** Settled states are excellent. The card always sits beside or below its target, the phone sheet is opaque, text is crisp and never reflows, and nothing replays. Points come off only for the overprinted frames inside the spotlight.

## Verdict
**FAIL** against the 4.5 bar for both smoothness (3.9) and polish (3.6). Steady states are close to premium. The six changes between steps are not there yet.

## Top 3 remaining issues
1. **The spotlight starts gliding before the new page is in place.** For 1–2 frames it lights wrong or empty targets: hero copy at C390 f25, an empty box at C1440 f25, old table rows at C1440/W1440 f280. It also clips at the viewport edge (C1440 f130, f230; W1440 f28). The spotlight should leave only once the new target exists, or fade and move rather than resize across old content.
2. **A 1-frame double exposure of the old and new page, inside the brightest part of the screen** (C1440 f26, f77, f180, f231, f281; C390 f180, f231, f282; W390 f28). The page change should finish (old fully gone) before the spotlight reveals the new region, or be hidden under the scrim.
3. **Dead time and visible plumbing between steps.** There is about 300–500 ms of nothing after card-out, sometimes with a "Loading next step…" pill (C1440 f24, f127, f229; C390 f24). The sidebar active item also switches 1–2 frames before the breadcrumb and content (C1440 f24, f76, f179; W1440 f27). Prefetch so the pill never shows, and switch the sidebar and top bar in the same frame as the content.
