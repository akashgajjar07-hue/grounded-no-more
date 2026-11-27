# Guided tour v2.2: motion critique from the recorded video

Reviewer: an outside motion/UX critic, judging only what the video shows. I did not read the tour code.
Source: the existing Playwright recordings `private/tour_videos/tour_{chromium,webkit}_{1440,390}.webm` (recorded 16:03–16:07, same commit as `bbe64a4`). I decoded each one at 10 fps with Chromium `<video>` + canvas, the same method `record_and_check.py` uses. That gave 304–307 frames per video. Frame `#n` is t = n/10 s from the start of the video. Frames and contact sheets are in the session scratchpad, not in the repo.

Bar: calm, premium, "Apple-keynote smooth". To pass, both smoothness and polish must score ≥ 4.5.

## What one step looks like (the same in all 4 combinations)

All 30 transitions follow the same visible sequence. Chromium 1440, step 1→2, frames 61–78:

| frames | what is on screen |
|---|---|
| 61–62 | steady step 1: dimmed page, spotlight, card |
| 63 | card and spotlight fade out, and the dim starts lifting (one frame) |
| 64–68 | **old page fully lit and still, with no dim, card or spotlight, for about 0.4–0.5 s** |
| 69 | cross-fade: **old and new pages both at about 50 %, text over text** |
| 70 | new page fully lit, no dim |
| 71–73 | dim comes back and the spotlight ring draws on the target |
| 74–76 | card fades in, already in its final place (it does not move) |

From the old card leaving (#63) to the new card being solid (#75) takes about 1.2 s. Of that, about 0.45 s is a static, fully lit hold of the page the viewer is leaving. Mean luminance over that span is roughly 21 → 31 → 19: the scrim switches off and back on at every step.

The checker's gates are all met, and the video agrees:
- I found no blank, dark or flat frames.
- The card never moves while visible and never jumps (at most one position, set while it is hidden).
- The spotlight is never on a skeleton or empty box.
- No chart replays behind the card: histograms, frontier and map are already drawn when the new page appears.
- Card text fits every step.

The problems below are about how it feels, not about mechanics.

---

## Chromium 1440×900

- **Open → step 1 (#14–25):** Mission Control cross-fades to AOG Response Lab in one frame (#16). That frame is a full double exposure: the hero headline "The right spare…" sits over the timeline, and both breadcrumbs ("Mission Control" and "AOG Response Lab") are on top of each other. #17 is the lit page. The dim arrives over #18–20, the card from #21, solid by #22. The card sits under the timeline target and does not cover it. Calm apart from #16.
- **1→2 (#61–78):** as in the table. Hold #64–68, double exposure #69 (AOG timeline and "Send a spare from AUH…" visible through the aircraft drawing), dim #71–73, card #74–76. The card sits right of the aircraft spotlight and does not cover it. Parts Intelligence lands scrolled so the top of the right-hand alert is cut under the top bar ("reliability engineering and warranty review first:" is clipped, #70/#76). The card has about 110 px of empty space between the body text and the progress bar (#76).
- **2→3 (#114–129):** hold #117–120, double exposure #121 (histogram ghosted over the aircraft), new page #122, dim #123–125, card #126. The card sits left of the KPI strip and covers the form, not the target (#128). The histogram is already drawn, with no replay. About 100 px of dead space inside the card again.
- **3→4 (#166–181):** hold #169–172, double exposure #173 (map and BOM panel over the histogram), dim #175–177, card #178–179. Two problems on the steady frame (#181):
  - the spotlit BOM panel runs off the bottom of the viewport, so the ring is cut at y≈895;
  - the card covers the page headline mid-sentence ("The Network Plan keeps 44 repairable…").
  - The spotlight also shows an empty grey grid cell next to "416 h · 26 times". That is a page layout gap, but the tour puts it under the light.
- **4→5 (#218–233):** hold #222–224, double exposure #225, dim #227–229, card #230. Planner Action Centre lands scrolled mid-list:
  - the spotlit row sits 8 px under the top bar, and a clipped line of text shows above it (#233);
  - there is no page title, column header or group header in view, so the viewer can't see what the list is.
  - Three of six card body lines; the card is about 40 % empty.
- **5→6 (#270–287):**
  - #272: the card's primary button changes from **"Next" to "Finish" while the card still reads "STEP 05 / 06"**, one frame before the card fades out.
  - Hold #274–277, with one row under the parked pointer showing its hover tint. That is an automation artefact, but a real user's resting cursor would do the same.
  - Double exposure #278, dim #280–282, card #283–285.
  - The step 6 spotlight wraps the whole frontier chart and runs off the bottom of the viewport (ring cut, x-axis not visible, #287).

## Chromium 390×844 (bottom sheet)

- **Open → 1 (#13–28):** the double exposure lasts **two frames** (#15, #16). The sheet fades in over #20–21, and the page text "lowest total cost: AED 238k…" shows through it at partial opacity. Solid from #22. Calm otherwise.
- **1→2 (#61–78):** sheet fades out #63, hold #64–67, **two-frame double exposure #68–69** (timeline over aircraft), new page #70, dim #71–73. The sheet fades in over #74–75 with "4 parts hide a known problem…" readable through it, and is solid at #76. The aircraft target is fully clear of the sheet.
- **2→3 (#114–135):** hold #117–120, double exposure #121, dim #123–125, sheet #126–127. **The spotlight sits on a small info note, "This is the hub pool. Switch to 'One outstation'…" (#129).** The "> 99.9 %" KPI it belongs to is scrolled off the top. The card talks about the Network Plan keeping 17 spares and being "almost always on the shelf", but the number that proves it is not on screen. This is the weakest step on phones.
- **3→4 (#166–186):** hold #169–172, double exposure #173–174, dim #175–177, sheet #178–180. The table target is clear of the sheet. The page heading is off-screen; the breadcrumb is truncated to "Ne…".
- **4→5 (#218–237):** hold #221–224, double exposure #225, dim #227–229, sheet #230–232. The step 5 sheet holds three lines of text in about 370 px. **Roughly half the sheet is empty** (#233–237), and it covers 44 % of the screen for nothing.
- **5→6 (#270–289):**
  - #272: the "Finish" label appears while the card still says step 5 (same as desktop).
  - Hold #273–277, with the hover tint on the "Review / AUH" row (#274–276).
  - Double exposure #278–279, dim #280–283, sheet #284–285.
  - The chart spotlight is complete on phones (axis visible), but the chart title is scrolled off.

## WebKit 1440×900

The same sequence and timing as Chromium, within ±1 frame, in all six transitions (#14–25, #63–80, #115–132, #168–185, #221–236, #275–290). The differences:

- **Double exposure is two frames, not one** (#69–70, #122, #174–175, #226, #278). The dissolve reads longer and muddier than in Chromium.
- **The scrollbar thumb flashes at the right edge** after each programmatic scroll and stays visible behind the scrim for about 1 s (#72–80, #125–132, and others). On a dark, quiet frame it is a bright moving sliver.
- #64: the card is still drawn at full strength while the dim is lifting. In #65 card, spotlight and dim are all gone, so the card's exit looks like a cut more than a fade.
- Everything else matches Chromium, including the same faults:
  - BOM panel clipped at the bottom (#181);
  - Planner row jammed under the top bar (#233);
  - frontier spotlight runs past the viewport (#287);
  - "Finish" label swap (#274).

## WebKit 390×844

- Sequence and timing are the same as Chromium 390 (#14–29, #62–81, #115–132, #167–186, #222–239, #272–289).
- **The top bar is see-through in WebKit:** page text is readable inside it, behind the Simple/Expert toggle. Examples: "already sits decides how long the…" (#66–70) and "AVERAGE AND LIKELY RANGE" (#222–227). The Chromium 390 frames at the same moments (#66, #67, #222, #226) show a clean, opaque-looking bar.
- The scrollbar thumb flashes on the right edge through every step (#16–29, #70–81, #230–239).
- Double exposure is two frames in every transition (#16–17, #68–70, #226–228, #278–279).
- The same step 3 footnote spotlight, half-empty step 5 sheet, and "Finish" label swap (#274).

---

## Scores (1–5)

| | score | reasons |
|---|---|---|
| **Smoothness** | **3.5** | Nothing stutters or jumps: no blank frames, no card moves, no chart replays, and the rhythm is identical at every step. But each step **lifts the scrim, holds a fully lit still of the page you are leaving for about 0.45 s, dissolves, then drops the scrim again**. Brightness swings about 50 % up and back every 5 s, and there is a visible dead pause in the middle. The dissolve's double exposure (1 frame in Chromium, 2 in WebKit) is the least premium frame in the film. Keynote-smooth would be a scrim that stays down and one continuous handoff. |
| **Polish** | **3.5** | Three faults show in every combination: the double-exposed text-over-text frame, the "Next → Finish" label changing on the outgoing card (#272/#274), and a fixed-height card or sheet that is 40–50 % empty on short steps. On top of that: spotlights clipped by the viewport edge (step 4 and step 6 desktop), a target row jammed under the top bar (step 5), a WebKit scrollbar flash, the WebKit phone top bar showing content through it, and the step 3 phone spotlight on a footnote. |
| **Continuity** | **3.5** | Card and spotlight placement is stable and logical within each step, and the card never covers its target. But focus is lost between steps: the scrim and spotlight disappear entirely, so the eye has nothing to follow from step N to N+1. Each new page lands scrolled to the target with its heading off-screen (steps 2, 4, 5, 6 on desktop; every step on phone), so the viewer loses where they are. On phone, step 3 tells one story and lights another. |
| **Legibility** | **4.0** | Card type is crisp, well spaced, high contrast, and fits every step in both engines. The dimmed context stays readable, which is good. Points off for: the card covering the step 4 headline mid-word, translucent card or sheet text overlap during its 2-frame fade on phones, WebKit top-bar text collisions, and clipped text lines above the step 2 and step 5 targets. |

**Verdict: neither smoothness (3.5) nor polish (3.5) reaches 4.5.** The mechanics pass the checker; the choreography doesn't yet feel premium.

## Top 5 issues, ranked, each with a fix

1. **The scrim switches off, a lit still of the old page holds, then the scrim comes back, at every step** (e.g. Chromium 1440 #63–73, WebKit 1440 #64–74, every transition).
   *Fix:* keep the dim layer (and ideally a spotlight placeholder) up for the whole tour. On Next:
   - fade only the card out (150 ms);
   - run the page change under the scrim, so the spotlight ring shrinks and fades on the old target, then the page changes, then the ring grows on the new target;
   - bring the card in.

   If the router needs to wait for the next page to be ready, wait while the scrim stays down: a dimmed still reads as calm, a lit still reads as stalled. Target 700–800 ms from card-out to card-in with no luminance swing over 10 %.

2. **Cross-fade double exposure: text over text** (Chromium #16, #69, #121, #173, #225, #278; 2 frames in WebKit and on phones).
   *Fix:* don't dissolve two full pages into each other. Use a fade-through for the content area only:
   - old page to about 0 opacity over 120 ms;
   - new page from 0 with a 4–8 px rise over 180 ms;
   - keep the sidebar and top bar out of the transition (`view-transition-name` on them, so they don't change).

   With issue 1 fixed, the whole page change happens under a 60–70 % scrim and any overlap becomes invisible.

3. **The spotlight composition fights the viewport.** The target is clipped at the bottom (step 4 BOM panel #181; step 6 frontier chart #287), jammed 8 px under the top bar (step 5 row #233), or the heading is scrolled away (all phone steps).
   *Fix:*
   - scroll so the target's top lands about 96–120 px below the top bar, showing its section heading where possible;
   - if a target is taller than the space left (viewport minus top bar, minus the sheet on phone), spotlight a defined sub-region. Step 4: the BOM stats block down to "Hours grounded". Step 6: the plot area including the x-axis. Or cap the ring at the viewport and fade the edge, so the ring never shows a cut corner.
   - Add a check: spotlight rect fully inside `[bar + 16, innerHeight − 16]` (or above the sheet on phone).

4. **Phone step 3 spotlights a footnote, not the stat** ("This is the hub pool…" note, Chromium 390 #129, WebKit 390 same). The card's claim ("almost always on the shelf") has no visible proof.
   *Fix:* on phones, target the KPI tile "> 99.9 % chance the part is on the shelf" (or the KPI strip plus the note), and scroll it into the clear space above the sheet. Spot-check every phone step for the same "story names a number that isn't lit" problem.

5. **Card and sheet finish details:**
   - the primary button changes from "Next" to "Finish" on the outgoing step 5 card (#272 Chromium, #274 WebKit);
   - the fixed-height card or sheet is 40–50 % empty on short steps (step 5 desktop #233, step 5 phone #233–237);
   - the card is translucent with page text showing through during its fade on phones (#20, #74–75, #178–179).

   *Fix:*
   - change card content only after it reaches opacity 0;
   - size the card to the longest text but put the controls directly under the text, so the leftover space falls at the bottom where it is not noticed. Or let the card change height by at most one line, while hidden, between steps;
   - on phones, give the sheet an opaque background from frame 1 and fade or slide in only its contents, or slide the sheet up 12 px with opacity, so page text never shows through it.

   Also worth doing, outside the top 5:
   - hide the scrollbar during the tour, or use `scrollbar-gutter` / `overflow: overlay`, to stop the WebKit thumb flash;
   - make the WebKit phone top bar opaque, or give it a working `-webkit-backdrop-filter`;
   - move the step 4 desktop card so it doesn't cut the page headline mid-sentence (place it below the headline, over the map's lower half).

## Notes on method

- I judged from decoded video frames at 10 fps. Playwright video in headless mode can stretch waits slightly, so the 0.4–0.5 s hold may be shorter on a real machine. It is still a lit pause between two dimmed states, and that is what reads as un-premium.
- The hover tint on a list row (5→6, #274–276) comes from the automation's parked mouse pointer. I note it but don't score it.
- No project files were changed apart from this report.
