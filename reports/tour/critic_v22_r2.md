> AI-generated review used during development — not a review by a human aviation professional.

# Guided tour — motion/UX critique, v2.2 round 2

Bar: calm, premium, "Apple-keynote smooth". To pass, both smoothness and polish must score ≥ 4.5.

Method: fresh recordings from `scripts/tour/record_and_check.py` (current `main`, f338214), Chromium and WebKit at 1440×900 and 390×844, Play mode from the "60-second tour" button. Each video was decoded at 10 fps in Chromium (`<video>` + canvas) into 280 JPEG frames, then viewed as labelled contact sheets. Frame numbers below are 10 fps indices (frame N = N/10 s into the video). In all four videos the transitions start at about these frames: open #19–22, 1→2 #65, 2→3 #113, 3→4 #159, 4→5 #206, 5→6 #253.

Checker result for this run: Chromium 1440, Chromium 390 and WebKit 1440 pass. WebKit 390 fails `a_brightness_swing` and `a_no_flat_frames` (see the note under WebKit 390).

## Per combination, per transition

### Chromium 1440×900
- **Open (#18–23).** Before any dim arrives, #19–20 are already broken at full brightness:
  - the top bar breadcrumb and the sidebar's active item switch to "AOG Response Lab" while the Mission Control hero is still on screen;
  - the Lab's "Pick a grounding to replay" strip (AOG-0081 … cards) renders through and over the "Results" panel, with "Results" overprinting it.

  #21 is a dimmed cross-fade with the spotlight on the hero. By #22 the spotlight is on the timeline and the card has arrived. The dim-in and glide take about 200 ms. That is too abrupt for an opening, and the first thing a viewer sees after the click is a layout collision.
- **1→2 (#65–70).** The card fades out at #65. #66–68 are a still of the old page under the dim, but:
  - the breadcrumb and sidebar already read "Parts Intelligence" (#67);
  - a strip of the new page ("Narrowbody / Widebody / All fleet | Nose wheel steering actuator") shows through at mid-height (#67–68), so two pages are partly visible.

  #69 is a double exposure: the old "Send a spare from AUH…" text shows through the new page, the spotlight is still changing shape, and the card is already at about 70 % opacity, overlapping the spotlight's right edge by about 25 px. #70 has settled. The card never covers the target once settled, and its text fits.
- **2→3 (#113–117).** The card is out at #113. The header switches to "Rotable & Repair" over the old page (#114–115). #116 is a messy frame: the ghost of the aircraft and the new metric strip and histogram overlap inside a spotlight that is still moving. At #117 the card is in and the spotlight is on the KPI strip. The histogram does not replay (#117–121 are identical).
- **3→4 (#159–164).** The same pattern. The header changes over the old still (#161–162). #163 is a double exposure of the metric strip and the plans table, text over text. By #164 everything has settled. The plans table is fully inside the viewport (round 1's clipping is fixed).
- **4→5 (#206–212). This is the worst transition.**
  - The header changes early, and the Planner Action Centre bar list (Materials planning, Repair control, Procurement, AOG desk) shows through under the old Network Positioning still (#208–209).
  - #210 is a near-empty dark frame (luminance 12.6 against about 17 steady, contrast 8.6 against about 19). The page area is black except the footer, and the old spotlight content is a horizontally stretched snapshot ("…ebook is at other airports. Keep urgent spares" smeared across the ring).
  - #211: the card is already visible, but the spotlight covers two rows (GN-27-R007 and GN-32-R014) and the table is still reflowing (no "Urgent" pill on the target row yet, and the rows below it are spaced differently).
  - #212: the spotlight snaps to the single correct row and the rows re-flow. So the spotlight moves twice, and the page reflows under a visible card.
- **5→6 (#253–259).** The card is out at #253 and the header switches to "Capital Optimiser" over the old still (#255–256). #257 is a dark, flat frame (luminance 14.0, contrast 7.9) with the old table ghosted inside the ring. At #258 the card is visible while the spotlight is still gliding, with a slight overlap. #259 has settled. The frontier chart is fully drawn on arrival (no replay) and fits the viewport.

### Chromium 390×844 (phone sheet)
- **Open (#18–23).** Cleaner than desktop: no leak of the other page is visible in the phone layout. #21 is a dimmed cross-fade, and at #22 the timeline is spotlit and the opaque sheet is sliding up. It settles at #24. The timeline's heading is cropped under the top bar (a half-line of body text, "…already sits decides how long the plane stays down", above the ring).
- **1→2 (#65–71).** The sheet slides down (#65–66), the old still holds (#66–68), #69 is a cross-fade with the timeline ghosted behind the aircraft, then the sheet slides back up with step 2 (#69–71). The sheet is opaque (round 1's see-through is fixed). Dropping and lifting the sheet every step is busier than it needs to be.
- **2→3 (#113–117).** #116 is a dark dip (luminance 15.8 against about 23–30): the ghost aircraft sits inside a shrinking ring. At #117 the ring is on the "> 99.9 % chance the part is on the shelf" KPI block, which is the right target now (round 1's issue 4 is fixed).
- **3→4 (#160–165).** #163 is a double exposure: the KPI block and the plans table overprint inside the ring, illegible for that frame. Settled at #165.
- **4→5 (#206–212).** At #208–209 a line of the new page ("tie up money or go to waste. Acting early") appears under the old still. #210 is a dark frame. At #211 the ring is on the GN-32-R014 card while the sheet rises, and the list below shifts slightly between #211 and #212.
- **5→6 (#253–258).** #257 is a dark frame with the old list ghosted. At #258 the chart is complete (no replay) and the sheet is up. Clean otherwise.

### WebKit 1440×900
- **Open (#18–23).** The same pre-dim collision as Chromium, held for one frame longer: #20–21 show the "AOG Response Lab" header and sidebar over the Mission Control hero, with the grounding strip overprinting "Results", undimmed. At #22 the spotlight is on the timeline with the hero headline ghosted inside the ring.
- **1→2 (#65–71).** The same pattern as Chromium: the header switches early (#67), and the new page strip shows mid-screen (#67–68). At #69 the new page appears in a different layout from its settled state (a "Share of the risk 57 %" tile and an "Extra spares…" callout that are gone by #70, so it is still reflowing). At #70 the card is in while the ring is still about 15 px short of its final height, and it finishes growing at #71.
- **2→3 (#113–117).** #115 is a broken composite: the bottom roughly 15 % of the screen is undimmed (the old page's "Source…" line, legend and "Compare two fixes" heading show at full brightness), and the ring holds new-page inputs at an offset over the ghost aircraft. #116: the ring is still travelling. #117 has settled. This may be partly a WebKit capture artefact, but it is what the recording shows.
- **3→4 (#159–164).** At #163 the card is already near full opacity at its final spot while the ring is still about 40 px off its target. Settled at #164.
- **4→5 (#206–212).** Worse than Chromium. #207–209: the header and the Planner bar list show through early. #210: the card is fully visible, and the ring sits over two rows, shifted horizontally. #211: the ring is over two rows again, shifted the other way. #212: it snaps to the correct row as the table reflows. That is three spotlight positions with the card on screen.
- **5→6 (#253–258).** At #256 the ring has grown to frame four rows of the old list, which reads as a deliberate highlight of the wrong thing, and the new chart's x-axis is visible under the old page. At #257 the card is in while the ring is still gliding, overlapping it by about 13 px. #258 has settled.

### WebKit 390×844
- **Transitions.** Open (#21–24), 1→2, 2→3 (#113–117), 3→4 and 5→6 (#253–258) behave like Chromium 390, with one cross-fade or ghost frame each (for example #116 and #255). The ring targets are correct, and the sheet is opaque.
- **Capture artefact, not scored.** During step 2 (#79–101) and from late step 4 through step 5 (#191–225), the whole frame slides sideways, by up to about 55 % of the width, showing white beside it, and some frames are pure white (#97–101, #212–216, #220–225). This is what fails the checker for this combination. A separate WebKit 390 run of the full tour without video sampled `scrollX`, `visualViewport.offsetLeft`, `scrollWidth` and the body `transform` every 50 ms: they stayed at 0 / 0 / 390 / none throughout. So the page never moves, and these frames are almost certainly a WebKit screencast artefact. I have not scored them against the tour. The checker failure for this combination is therefore a recorder problem, not a tour problem, but re-record to confirm.

## Scores (1–5)

| | score | reasons |
|---|---|---|
| **Smoothness** | **4.0** | The scrim now stays down for the whole tour, and luminance between steps is steady. That is the big win over round 1. But every transition has a "fade, wait, snap" rhythm: the card fades out, a still holds for about 300 ms, then the page dissolves and the spotlight glides in about 150–200 ms. The glide is too quick to read as calm. 4→5 and 5→6 add a dark, flat frame (Chromium #210 and #257, phone #116 and #210). In 4→5 the spotlight resettles 1–2 times with the card visible (Chromium #211→212, WebKit #210→212). |
| **Polish** | **3.5** | The very first frames after the CTA show the next page colliding with Mission Control at full brightness (desktop #19–21). The header and sidebar switch while the old content is still shown, at every step. Strips of the new page show under the "still" (#67, #209, WebKit #256). There is a stretched snapshot in #210 and a broken undimmed band in WebKit #115. The card arrives before the spotlight lands (#69, WebKit #163, WebKit #257). The fixes since round 1 are real: opaque sheet, card content that never changes while visible, the right KPI on phone, no clipping. |
| **Continuity** | **4.0** | One persistent dim, one spotlight, and card placement that is logical for each target and never covers it once settled. Charts don't replay. Lost points: the chrome changes ahead of the content, the 4→5 spotlight first lands on the wrong rows, and the sheet drops and rises on every phone step. |
| **Legibility** | **4.5** | Every card's text fits without overflow at both sizes. The phone sheet is opaque, and the lit target carries the number the card talks about. Text over text appears only in single 100 ms transition frames (#116, #163, phone #163). Headings above phone targets are cropped to a stray half-line. |

**Verdict: FAIL.** Smoothness (4.0) and polish (3.5) are both below 4.5. This round is clearly better than round 1 (3.5 / 3.5), but it does not yet feel keynote-smooth.

## Top 5 remaining issues, ranked, with fixes

1. **The opening shows two pages colliding before the dim arrives** (Chromium 1440 #19–20, WebKit 1440 #20–21).
   - The route, the header and the sidebar change and the Lab content renders under the undimmed home page.
   - *Fix:* on the CTA click, first fade the scrim in over the home page (about 200 ms) and capture the View Transition snapshot. Only then navigate.
   - Do not update the breadcrumb, sidebar or `#view` until the snapshot is captured (`document.startViewTransition(() => router.go(...))`, with the scrim already up).
   - Give the opening 500–600 ms: scrim in, then a ring that grows from the CTA to the timeline, then the card. That is the first impression.
2. **4→5: the spotlight lands on the wrong rows and resettles while the card is visible; the table reflows under it** (Chromium 1440 #211→212, WebKit 1440 #210→212, Chromium 390 #211→212).
   - *Fix:* wait for the `?station=` / `?pn=` filter to finish rendering before you measure the target. Wait for the target row to have its "Urgent" pill, then two rAFs, then a ResizeObserver/MutationObserver quiet window of about 100 ms on the list.
   - Gate the card's fade-in on the spotlight's `transitionend`, not on a timer.
   - Add a checker rule: the spotlight rect stays the same for every frame where the card's opacity is above 0.
3. **The swap frame is dark, flat or double-exposed, and in one case shows a stretched snapshot** (Chromium #116, #163, #210, #257; phone #116, #163, #210, #257).
   - *Fix:* make the content swap an opacity-only fade-through with no geometry morph. Set `::view-transition-group(*)` animations to none for the page content, so the old snapshot never scales into the new box (that is the stretch in #210).
   - Fade the old content out over 120 ms. Start the new content at 0, with a 4–6 px rise over 200 ms, beginning at about 80 ms, so the content area's brightness never drops below about 90 % of steady.
   - Make sure the new page has painted its data before the transition starts.
4. **The chrome changes ahead of the content, and the new page leaks under the "still"** (header and sidebar at Chromium #67, #114, #161, #208, #255; new-page strips at #67–68, #208–209, WebKit #256, phone #208).
   - *Fix:* give the top bar and the sidebar their own `view-transition-name` and swap them in the same frame as the content, or cross-fade the breadcrumb text with it.
   - Make the held still cover the full content area (its clip currently lets the new page's rows show beneath it), or keep the new `#view` at `visibility: hidden` until the swap.
5. **The rhythm is "stall then snap", and the card beats the spotlight** (card early at Chromium #69, WebKit #70, #163, #257; phone sheet drops and rises at #65–71 on every step).
   - *Fix:* cut the still hold to 120 ms or less, and lengthen the spotlight glide to 380–450 ms with `cubic-bezier(.4, 0, .2, 1)`, running under the content fade-through.
   - Start the card fade-in about 60–80 ms after the ring lands.
   - On phones, keep the sheet in place and cross-fade only its contents (with a 4 px rise), instead of sliding the whole sheet down and up each step.

Also seen, outside the top 5:
- The WebKit 1440 #115 frame leaves an undimmed band at the bottom. Make the scrim layer `position: fixed; inset: 0` with its own compositing layer (`will-change: opacity`), and re-check it after fix 3.
- Phone targets show a stray half-line of the paragraph above them. Scroll so the ring's top is 16 px or more below the top bar, with the section heading fully visible or fully hidden.
- WebKit 390 recordings show sideways-shifted and white frames that the page does not cause (probe: `scrollX` 0, no overflow). Re-record or exclude them, so the checker failure doesn't hide real regressions.

## Round 1's top 5: status

1. **The scrim drops and a lit still holds at every step: FIXED.** The dim stays down for the whole tour, and the hold is now dimmed. Luminance between steps is steady except the single swap frame (see issue 3).
2. **Double exposure, text over text: PARTLY FIXED.** It is down to one frame per transition, but it is still visible (Chromium #116, #163, phone #163). There is a new variant: dark or stretched swap frames in 4→5 and 5→6. The suggested step of keeping the sidebar and top bar out of the transition was not done, and they now change early.
3. **The spotlight fights the viewport: MOSTLY FIXED.** The step 4 plans table, the step 6 chart and the step 5 row all sit fully inside the visible band. Phone targets still show a cropped half-line above the ring.
4. **The phone step 3 spotlight is on a footnote: FIXED.** The ring is on the "> 99.9 %" KPI block (Chromium 390 #117 onward, WebKit 390 #117 onward).
5. **Card and sheet finish details: FIXED.**
   - The button label no longer changes on the outgoing card: step 5 shows "Next" until hidden, and "Finish" appears only on step 6.
   - The sheet is opaque from its first frame.
   - Card content never changes while visible.
   - The card no longer leaves a large empty area on short steps.

No project files were changed apart from this report. Frames and contact sheets are in the session scratchpad.
