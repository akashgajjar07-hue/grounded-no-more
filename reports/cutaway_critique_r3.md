# Cutaway critique, round 3

**Page:** `docs/lab/cutaway.html` (drawings `docs/assets/svg/cutaway.svg` and `cutaway-simple.svg`, logic in `docs/lab/cutaway.js`)
**Viewed at:** 1440×900 @2x and 390×844 @3x, Chromium through Playwright. I waited for `data-ready` plus 2.8 s each time.
**Evidence:** `reports/traces/cutaway-critic-r3/`
- desktop: `d_static`, `d_crop_{nose,mid,wing,tail}`, `d_hover14/18/22`, `d_focus05`, `d_after_leave`, `d_after_last_tab`
- phone: `p_static`, `p_full`, `p_open14` (this opens row 22, because the list is in zone order), `p_open18`, `p_tap03`

## Verdict in one line
This is a strong, on-brand interactive diagram. The sheet furniture is now poster grade: the title block, dimensions, torn copper cut edges, lit system runs and docked card. The airframe and the parts are still the weak half. The wing, gear, APU and fuel pumps float rather than sit in structure. A cutaway-poster fan would admire the presentation, then start counting what is missing.

## Scores (1–5)
| Criterion | Score | Why |
|---|---|---|
| Craft | 3.5 | The linework is confident, the ghosting hierarchy is clear (bright outline, mid frames, faint far wing) and the copper cut edges are lovely. Junctions are unresolved, though. The wing meets the belly as a flat plate with no fillet or box. The fin trailing edge stops short of the fuselage. Main wheels hang in mid-air ahead of a stub leg. The nose gear is a bare stick. |
| Detail | 3.5 | The engine now reads well: fan face, cut nacelle, core, and the IDG and EDP slung underneath. The fin has ribs, and the wing cut shows the probes. The mid-body is still made of wire "crates", with no seats, floor-beam ladder, keel or centre wing box. The tail cone has no APU body or aft pressure bulkhead, so 24, 25 and 26 float in empty space. |
| Legibility | 4.0 | Callouts are numbered and grouped into side columns, and the Plex Mono labels read at 1440. Hover dims everything else, so the active part pops. Several leaders still cross each other and the structure. The worst are 03, 04 and 05 (long diagonals over the nose), 13 (it ends at the nacelle lip, not at a valve), 18/19 (two leaders converge on one wheel blob) and 26 (it crosses the fin). The phone badges overlap each other in the nose and gear clusters. |
| Brand fit | 4.5 | It sits exactly in the brand: #09131F ground, titanium ghost lines, teal glow parts, copper cut edges and tick marks, a Plex Mono title block and an honesty line. Minor point: the hover card covers the title block and legend, which are the sheet's most "Blueprint" elements. |
| Would a cutaway-poster fan admire it? | 3.0 | They would admire the sheet composition and the interaction. They would not yet admire the drawing as a drawing. There is no structural density where the eye lands (wing root, gear bay, tail cone), and the parts are primitives rather than objects. |

**Mean: 3.70 / 5**

## Interaction and accessibility checks (all pass)
- **Hover:** the card docks top-left, the active part, leader and tag go teal, the rest dims, and the relevant system run lights up (fuel to the APU, hydraulics to the brakes). Moving the mouse away hides the card after 140 ms.
- **Tab order:** strictly 01 → 26, then on to "Back to the workspace". Leaving 26 hides the card (`hidden=true`, no active classes). Escape hides the card while focus stays on the part. Enter goes to `index.html#/parts?pn=…`.
- **Click:** clicking part 01 goes to `#/parts?pn=GN-29-R012`. There were no console errors.
- **Phone:**
  - The tap targets measure 43.99 CSS px.
  - The list has 26 zoned disclosure rows. Opening a row expands it with facts and a link, and moves the ring marker and the 2.5× inset to that part, with a caption strip such as "22 Wing · Aileron servo control".
  - Tapping a badge on the drawing opens the matching row.
  - The figure is still short: 179 px tall at 348 px wide.

## Originality
It is clearly original. The geometry is procedural (long generated path lists, and the SVG notes it comes from a simple 3-D model). The only text in the SVGs is generic: numbers, "GENERIC NARROWBODY", "NOT ENGINEERING DATA · NTS", LENGTH 36.8 m, SPAN 33.9 m and HEIGHT 11.9 m. These are deliberately generic figures that don't match any one type exactly. A grep for manufacturer, type and engine names found matches only inside coordinate numbers. There are no logos, liveries, registrations or traced silhouettes. Part numbers use the fictional `GN-` scheme.

## Top 5 remaining improvements (priority order)

### 1. Seat every floating part in structure: wing box, gear bay, APU bay
- **Centre wing box:** under the floor at the wing root, draw a box with a front spar, a rear spar and 3 ribs (T3, 0.9 opacity), with the upper skin cut in copper. Move the two fuel boost pumps (14) inside it, on the rear spar face. Today they hover below the belly ahead of the wing.
- **Main gear:** draw a trunnion at the rear spar, an oleo leg (two nested cylinders), a side brace (two-link) and an axle. Hang wheels 19 and brake 18 on that axle, so the wheel sits below and slightly behind the leg, not in front of it. Add a wheel-well outline (a dashed ellipse) in the belly fairing.
- **Nose gear:** draw a leg, a drag brace and a torque link. Put the steering actuator (10) on the leg collar and wheel 15 on the axle.
- **APU bay:** draw an aft pressure bulkhead (a dome, T3) and an APU body in the tail cone (a cylinder plus a reduction gearbox block plus an exhaust cone out of the tail tip). Mount 25 (fuel control unit) and 26 (starter) on its gearbox. Move 24 (elevator servo) to the tailplane rear spar or hinge line, and point its leader there.

### 2. Untangle the leaders: no crossings, no leaders across the airframe outline, one bend each
- Re-sort each callout column by each part's projected y, after the moves in item 1, so leaders fan out without crossing.
- Re-route 03, 04 and 05 so they enter the fuselage through the nose cut, not across the frames. Their anchors sit in the forward cargo and avionics area, so place their tags in the lower-left column (between 07 and 08), not upper-left.
- Re-anchor 13 (bleed air valve) to a drawn valve body on the pylon or core case (see item 3), not the nacelle lip.
- Give 18 and 19 separate anchors: 19 on the tyre's outer face, 18 on the brake stack visible through the hub.
- Route 26 behind the fin: a horizontal run, then drop into the tail cone below the fin root.
- Cap leaders at 300 units, with one bend each.
- Keep the 3-unit #09131F halo wherever a leader crosses structure.

### 3. Turn primitives into recognisable objects (2–4 extra strokes each)
- **Pumps (14, 16):** a cylinder, a flange disc and two port stubs.
- **Valves (03, 13):** a butterfly body plus a square actuator on a short stem.
- **LRUs (04, 05, 07, 08, 11, 12):** boxes with a handle line and a connector strip, sitting in a two-shelf avionics rack (T3) under the flight-deck floor.
- **Servos (21, 22, 24):** a cylinder, a piston rod and a clevis, attached to a hinge line.
- **Main wheel and brake:** a tyre torus, a hub, and a 5-disc brake stack visible in the hub.
- **ACM (02):** a fan-scroll volute.
- Keep the teal glow, but drop fill opacity to about 0.35 so the inner strokes show.

### 4. Give the airframe structural rhythm and thickness where the eye lands
- **Fuselage frames:** draw every frame, with every 4th at T3 and the rest at T4, so the barrel has a beat.
- **Floor:** add the floor-beam ladder at T3 and a keel beam under the wing box.
- **Cabin:** cull the far-half cabin "crate" boxes. Replace the near-half boxes with simple seat-row glyphs (a back line plus a cushion line, 0.2 opacity). This removes the moiré in the mid-body.
- **Wing:** give it real thickness (t/c ≈ 0.11 at the root, 0.09 at the tip). Close the wingtip outline. Show the front and rear spars with ribs about every 1.2 m inside the copper cut.
- **Wing root:** add a belly fairing curve where the wing joins the fuselage.
- **Fin:** close the fin trailing edge into the fuselage, and add the rudder hinge line.
- **Far tailplane:** draw it as a closed ghost outline.

### 5. Card placement and phone density
- **Desktop card:** dock it into empty space instead of over the title block and legend. Use the lower-right band under the far wing (about x 1260–1590, y 640–860 in viewBox units), or switch the dock per part (left for aft parts, right for forward parts). Alternatively, shrink the title block to sit beside the card.
- **Phone, taller drawing:** crop the simple viewBox tighter around the airframe (about 1000×470, dropping empty sky above the far wing). At 348 px wide the figure then grows from 179 px to about 230 px tall.
- **Phone, frames:** bring back the T3 frames at 0.35 opacity.
- **Phone, badge collisions:** run a relaxation pass on the badges. Push overlapping dots apart along their leader direction to a 2-unit minimum gap, and draw a 0.6 tick back to the anchor. The overlaps are 07/11/09/10/12, 13/14/18/19 and 24/25/26.
- **Phone, dimming:** when a row is open, dim the non-active badges to 0.35, as on desktop.

## Keep
- The title block and legend.
- The copper torn cut edges with hatched section faces.
- The lit system runs.
- The docked 2×2 fact card with station chips and "+N flags".
- The strict numeric keyboard model with a clean exit.
- The phone pattern: zoned disclosure list, sticky figure, ring plus 2.5× inset and caption strip.
- The honesty line under the figure.
