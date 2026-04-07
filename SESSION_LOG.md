# Session Log

Development log from the Claude Code session that built this project. One continuous conversation, ~2 hours, April 7, 2026.

## Phase 1: Understanding the Problem (15 min)

**Prompt:** "Here's a GPX file and a prompt.md with Strava segment URLs for each cobblestone sector. Make me a FIT course file for my Garmin Edge 1050 with sector entry/exit markers."

**What happened:**
- Read `prompt.md` and the GPX file structure (1,924 trackpoints, 3 waypoints, 146.7km)
- Launched parallel agents: one to explore the GPX, one to research the `fit-tool` library API, one to look up sector coordinates
- Noted the start/end GPS coordinates of each sector from the Strava segment pages I provided
- Verified all 18 segment names against the official sector list

I also provided an image of the official men's race sector table (29 sectors) alongside the challenge sector list (18 segments). Cross-referencing showed the challenge uses the same sector numbering as the men's race for sectors 19 and below.

## Phase 2: Sector Corrections (10 min)

My corrections:
- "Templeuve L'Epinette is missing from the GPX": confirmed, excluded
- "Cysoing and Bourghelles are cut, use these shorter segments instead": I provided two replacement segment URLs for the portions that are actually on the challenge route
- "Auchy is 4 stars, not 5": corrected the difficulty rating
- Final count: **19 sectors** (not 18), mapping to men's race sectors S19 through S1

Claude verified the two replacement segments. "Cysoing a Bourghelles - secteur pave 1" (0.95km) maps to S7, "secteur pave 2" (0.71km) maps to S6.

## Phase 3: FIT File Generation (20 min)

- Read the `fit-tool` library source code to understand the exact API (property names, field types, timestamp format in milliseconds, coordinate handling)
- Found the example course file in the library's examples directory: critical for getting the message ordering right
- Implemented the sector matching algorithm: for each sector's known start/end coordinates, find the nearest GPX trackpoint within 100m
- Generated the FIT file on first try: all 41 course points, monotonically increasing distances

Key detail: the `fit-tool` library accepts coordinates in degrees (not semicircles) and timestamps in milliseconds since Unix epoch. The library handles FIT epoch conversion internally. This wasn't documented, it was discovered by reading the field definitions in `course_point_message.py`.

## Phase 4: Garmin Display Bug (5 min)

I reported: "The sector names do not look good, it's like it's truncated."

Root cause: Unicode star characters (U+2605) are 3 bytes each in UTF-8. A name like `S19★★★★★ ARNBG` is 24 bytes, well past the Garmin's ~15-byte display limit. Names with fewer stars (like `S6★★★ BRGH`) happened to fit, making the truncation look inconsistent.

Fix: switched to all-ASCII format: `{sector}-{N}*-{ABBR}` (e.g., `19-5*-ARNBG`, max 13 bytes).

## Phase 5: Interactive Map (10 min)

I asked: "Can you generate a high res map of the course with sector overlays?"

Claude built an interactive HTML map with folium: GPX route as a green line, sector overlays colored by difficulty with clickable markers, food station markers, and multiple tile layers.

## Phase 6: Race Plan and Speed Model (15 min)

I asked: "Add the estimated time with a departure at 8:00 AM. Take into account the route profile. I added a FIT file of my own last year."

Claude decoded the 2025 PRC FIT file (70km route): 24.6 km/h moving avg, 164 bpm, 184W. Extracted per-sector speeds by matching last year's GPS track to the known sector coordinates. After fixing a coordinate bug (garmin-fit-sdk returns semicircles, not degrees), we got actual cobblestone speeds: 5-star at 19.8 km/h, 3-star at 24.2 km/h, road at 25.0 km/h.

I corrected the pacing: "No way I'm doing 24.8. That was for the SHORT COURSE. Drop to 22 km/h." Also provided a recent 97km ride from the same week (22.2 km/h avg) as a better baseline.

Result: speed model calibrated at 22.0 km/h road, 18-22 km/h cobbles, 7% fatigue after km 100.

## Phase 7: Nutrition Iteration (15 min)

The most back-and-forth phase:

1. **First model**: 160g carbs/hour. My reaction: "WAY TOO HIGH, this is pro level. My gut can't handle that."
2. **Reduced to 130g/h**. Me: "I PREFER TO DRINK THAN EAT BASICALLY"
3. **Drink-first strategy**. Me: "I use SiS Beta Fuel gels AND drinks. 900ml bidons with a single pack. And Clif Bars. CLIF FOR LIFE"
4. **Adjusted for 900ml bidons** (80g carbs each). Me: "I did not train my gut for a while"
5. **Dropped to gels-as-backup**. Me: "but I ran a marathon with gels every 40 minutes" ... "but that was a while ago" ... "yes only 2 gels" ... "or 3"
6. **Final model**: drink-first (~67g/h from Beta Fuel), 3 gels hardcoded before 5-star sectors (Arenberg, Mons, Carrefour), Clif bars at food stations only

Final numbers: ~80g carbs/h while riding, 4 gels total (incl. pre-start), 3 Clif bars, 8 Beta Fuel sachets. I also asked for the exact shopping list: how many packs of each product to buy and bring.

## Phase 8: Wind Integration (10 min)

I asked: "Can you find the wind predictions?"

- Fetched the April 11 forecast from Open-Meteo: SE wind, 12-15 km/h, 6-18 C, dry
- Fetched last year's race day (April 12, 2025) for comparison: ESE 10 km/h, similar pattern
- Built wind speed adjustment: compute rider bearing from GPX, calculate headwind component, adjust speed by 0.3 km/h per km/h headwind (conservative for a 100kg rider)
- Added per-sector wind indicators: `13km/h tail` or `9km/h head`

Pacing comparison:

| Scenario | Finish | Delta |
|----------|--------|-------|
| Ideal (flat, no wind) | 15:28 | baseline |
| + Elevation (+671m) | 15:31 | +3 min |
| + Elevation + Wind | 15:44 | +16 min |

Wind costs 13 minutes. Elevation only 3 (course is flat). Most cobble sectors get a tailwind (heading NW back to Roubaix). The outbound leg south to Arenberg faces the headwind.

## Phase 9: Map Enhancements (15 min)

Several rounds of iteration:

1. **Road book panel**: collapsible timeline with ETAs, nutrition notes at each sector
2. **Panel overlap**: initially top-right, conflicting with layer control. Moved to top-left.
3. **Nutrition on own line**: I sent screenshots showing text running together. Added line breaks.
4. **Wind impact layer**: red/green route overlay showing headwind vs tailwind per 5km segment. First attempt had misaligned segments because the distance calculation used `sqrt(dlat^2 + dlon^2) * 111km` instead of haversine. At 50N, 1 degree longitude is 71km, not 111km. Fixed with proper cumulative distance.
5. **Wind arrows**: first version too big and too many, overlapping the sector badges. Reduced to small 20px circles every 20km, offset perpendicular to the route.
6. **Elevation profile**: SVG panel fixed to bottom of map. Elevation area chart + sector bands (colored by difficulty) + wind zones (red/green background) + food station markers. First version too tall, reduced to 100px with `viewBox` for full-width scaling.
7. **Map centering**: added `fit_bounds` so the entire course is visible on load.

## What Worked Well

- **Hardcoded sector coordinates**: extracting the start/end GPS of each sector once and baking them into the code means zero external dependencies at runtime. The matching algorithm just finds the nearest GPX trackpoint to each coordinate.
- **Calibrating from real ride data**: my own FIT files gave ground truth for cobblestone vs road speeds, actual stop durations, and HR/power baselines. A recent 97km ride from the same week turned out to be the best baseline.
- **Iterative nutrition modeling**: going from "160g/h" to "my gut says no" to "drink-first, 3 gels before 5-star sectors" produced a plan I actually trust and will follow.

## What Was Tricky

- **UTF-8 on Garmin**: the star character issue was non-obvious. Display truncation was inconsistent because it depends on byte count, not character count, and different names had different star counts.
- **garmin-fit-sdk coordinate format**: the decoder returns semicircles (raw FIT values), not degrees. Caused the sector matching against last year's ride to silently fail (all "no match") until the conversion was added.
- **Loop course matching**: Roubaix is both start and finish, so S1's coordinates matched the start of the route (km 0) instead of the end (km 146). Fixed with a monotonic constraint: each sector must match after the previous one.
- **Wind segment alignment on map**: the crude distance formula doesn't account for longitude compression at 50N. Caused wind overlay segments to land on wrong parts of the route.

## Tools and Libraries

| Tool | Role |
|------|------|
| `fit-tool` 0.9.15 | FIT file creation (course, records, course points) |
| `garmin-fit-sdk` 21.195.0 | FIT file decoding/verification |
| `gpxpy` 1.6.2 | GPX parsing (trackpoints, waypoints, elevation) |
| `folium` 0.20.0 | Interactive map generation (Leaflet.js wrapper) |
| `requests` | Open-Meteo weather API |
