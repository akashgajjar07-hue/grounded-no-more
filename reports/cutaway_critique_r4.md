# Cutaway critique, round 4

**Page:** `docs/lab/cutaway.html` (drawings `docs/assets/svg/cutaway.svg` and `cutaway-simple.svg`, logic in `docs/lab/cutaway.js`, styles in `docs/lab/cutaway.css`)
**Evidence:**
- Supplied screenshots in `docs/design-review/`: `cutaway-r4-1440.png`, `cutaway-r4-1440-hover.png` (part 08 hovered), `cutaway-r4-390.png` and `cutaway-r4-390-open.png` (row 08 open).
- Close-up renders of `cutaway.svg` at about 3× (nose, mid-body, main gear, wing, tail) made in headless Chromium for this review. They are scratch files and are not committed.
- A code read of the hover, focus, Escape, reduced-motion, phone list, marker and inset logic in `cutaway.js`.

## Verdict in one line
The presentation is still poster grade, and it improved in one visible way: the hover card now docks top-left, clear of the title block. The drawing underneath has barely moved since round 3. The wing is still a flat plate. The wheels still float off their legs. The tail cone is still empty, with no APU or bulkhead. The leaders still dive across the airframe. This is a strong lab page, not yet a landing hero.

## Scores (1–5)
| Criterion | Score | Why |
|---|---|---|
| Craft | 3.5 | **Good:** the copper torn cut edges with hatched faces, the three line weights (bright outline, mid frames, faint far wing) and the engine cut are well done. The fin trailing edge now closes into the fuselage. **Weak:** the junctions are still unresolved. The wing joins the belly as a zero-thickness plate with no fillet or fairing. The nose-wheel leg ends above wheel 11, leaving a visible gap. The main wheels hang off a bare stick with no side brace or trunnion. The tailplanes are single outlines with no thickness. Under the belly, the teal system runs loop around in a tangle that reads as spaghetti, not routed pipework. |
| Detail | 3.5 | **Better:** the wheels now have tyre and hub rings, and a brake face shows on 18/19. The pumps are flanged cylinders, the LRUs are boxes, and the engine (fan blades, core rings, IDG and EDP slung beneath) is the best object on the sheet. **Still missing:** the mid-body is wire "crates", with no seats, floor-beam ladder or keel. There is no centre wing box, so the fuel boost pumps (02) sit under the cabin floor ahead of the wing, not in a tank. The tail cone has no APU body and no aft pressure bulkhead, so 24 and 26 are tiny blobs in empty space. The fin is empty, with no spars or rudder hinge line. |
| Legibility | 3.5 | **Works:** the numbered tags are clear, and on hover everything else dims, the active part goes teal and its system run lights. **Problems:** the leaders still break the basic rules. 01, 02 and 03 drop vertically through the whole upper fuselage. 04, 05 and 06 run long diagonals over the nose frames. 26 cuts across the fin. 24 runs down through the tailplane. The anchors for 20 and 21 almost coincide on the wing. The callout columns are ragged: the left tags step between three x positions, and 12, 13, 14 and 15–19 float mid-sheet. The Plex Mono labels are about 11 px at 1440, which is legible but small for a hero. **Phone:** the figure is still only about 172 CSS px tall at 348 px wide. Badges overlap in five clusters: 13/06/12/05/14, 10/08, 17/18/19, 23/20/21 and 26/25/24. |
| Brand fit | 4.5 | It is squarely on brand: #09131F ground, titanium ghost lines, teal parts and runs, copper cuts and ticks, a Plex Mono title block, an honesty line, and the fictional `GN-` part numbers. The card no longer covers the title block. Points against: at rest, the teal system runs are nearly as bright as the parts, which weakens the rule that teal means a modelled part. The title block and legend take the prime upper-left quadrant, which a hero would give to the aircraft. |
| Would a cutaway-poster fan admire it? | 3.0 | They would admire the sheet furniture, the cut edges and the interaction. Then they would look where the eye lands (wing root, gear bay, tail cone) and find no structure: parts as primitives, a flat wing, floating wheels and an empty APU bay. This is the same verdict as round 3, because the drawing itself has not crossed that line. |

## Interaction and accessibility (from the screenshots and the code read)
- **Hover, focus, Escape:** hover and focus show the card. Escape hides it, both on the part and at document level. After the mouse leaves, a 140 ms timer hides the card.
- **Labels:** each part has an `aria-label` and points to a polite live region through `aria-describedby`.
- **Motion:** prefers-reduced-motion skips the line-drawing intro, in both the JS and the CSS.
- **Phone, hover state:** the card shows the counts, repair time, spares chips by station, hours grounded, a recommendation with "+3 flags", and a link to the part page.
- **Phone, open row:** opening a row moves the ring marker and the 2.5× inset to the part, dims the other badges and shows a caption strip ("08 Landing gear · Nose wheel steering actuator"). The rows are grouped by zone and use `aria-expanded` and `aria-controls`.
- **Inset problem:** the 2.5× inset for 08 is a jumble of teal boxes and copper lines. You cannot pick out the actuator in it.

## Top 5 remaining issues (priority order)

### 1. Seat the floating parts in drawn structure (wing box, gear, APU bay)
This is unchanged since round 3, and it is the main thing between 3.6 and 4.3.
- **Centre wing box:** draw a box under the floor at the wing root (front spar, rear spar, 3 ribs, cut upper skin in copper). Move the fuel boost pumps (02) onto its rear-spar face.
- **Main gear:** draw a trunnion, a two-cylinder oleo, a two-link side brace and an axle. Hang 18/19 on that axle, with a dashed wheel-well outline in the belly fairing.
- **Nose gear:** close the gap between the leg and wheel 11. Add a drag brace and torque links, and put 08 on the leg collar.
- **Tail cone:** add an aft pressure bulkhead dome and an APU body (case, gearbox, exhaust out of the tail tip). Mount 24 and 26 on the APU gearbox, and put 25 on the tailplane hinge line.

### 2. Re-route the leaders: no crossing the airframe outline, one bend each, tidy columns
- Bring 01, 02 and 03 in from below or behind the fuselage instead of dropping through its top skin. Place their tags beside their anchors.
- Shorten 04, 05 and 06 so they enter through the nose cut.
- Route 26 behind the fin, and 24 around the tailplane, not through it.
- Separate the anchors for 20 and 21 by at least 12 units.
- Snap the tags to a few fixed columns (for example one left x, one right x, and one bottom row) and sort each column by anchor y, so no two leaders cross.
- Cap each leader at about 300 units.

### 3. Give the wing and tail real section and rhythm, and declutter the mid-body
- Give the wing thickness (t/c about 0.11 at the root, 0.09 at the tip), a belly fairing at the root, and front and rear spars with ribs about every 1.2 m inside the copper cut.
- Give the tailplanes a closed, thick outline, and draw the fin spars and rudder hinge line.
- Cull the far-half cabin crates. Replace the near half with faint seat-row glyphs and a floor-beam ladder, which removes the mid-body moiré.

### 4. Calm the system runs so teal means a part
- At rest, drop the runs to about 0.25 opacity, with a thinner stroke or a dash, and light them fully only on hover or focus.
- Route them along the floor beams and spars as orthogonal runs with bend radii, not freehand loops under the belly.
- This also makes the active run on hover pop harder.

### 5. Phone figure: height, badge collisions and inset clarity
- Crop the simple viewBox tighter (drop the sky above the far wing), so the figure grows from about 172 px to about 230 px tall at 348 px wide.
- Run a relaxation pass on the badges along the leader direction (at least a 2-unit gap, with a tick back to the anchor) for the five overlapping clusters.
- For the 2.5× inset, ghost everything except the active part, so the part reads at a glance instead of drowning in neighbouring teal.

## Keep
- The title block and legend (consider shrinking them for the hero crop).
- The copper torn cut edges and hatched section faces.
- The top-left docked fact card.
- The engine drawing.
- The strict numeric keyboard model and Escape handling.
- The phone pattern: zoned disclosure list, ring plus inset, and caption strip.
- The honesty line.

**Mean: 3.60 / 5**
