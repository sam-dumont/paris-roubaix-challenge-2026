# Paris-Roubaix Challenge 2026: Race Planner

I needed a pacing tool, a wind analyzer, and a Garmin course editor for a one-off event. That's typically 2-3 paid subscriptions for something I'll use once. Instead, I built the whole thing in a 2-hour conversation with [Claude Code](https://claude.ai/claude-code): a Garmin FIT course file with sector markers, an interactive road book map with wind/elevation visualization, and a pacing/nutrition plan.

Nobody's going to reuse this code for their own Paris-Roubaix prep (but feel free). The point is: this is the kind of one-off, multi-tool problem that used to mean either paying for subscriptions or spending a weekend in spreadsheets. Now it's a conversation.

## Before & After

**Before:** An official GPX file with no sector info, a Strava segment list, and a vague plan to "eat enough and not blow up on Arenberg."

**After:** A Garmin Edge loaded with 41 course points that trigger "Up Ahead" alerts at every sector entry/exit and food station. An interactive road book with ETAs, wind analysis, elevation profile, and an exact shopping list (4 gels, 3 Clif bars, 8 Beta Fuel sachets).

## Quick Start

```bash
uv add gpxpy fit-tool garmin-fit-sdk requests folium

uv run python generate_fit.py    # -> prc26-145km-sectors.fit (Garmin course file)
uv run python race_plan.py       # -> race_plan.json + console plan
uv run python generate_map.py    # -> prc26_course_map.html (interactive map)
```

## What You Get

### Garmin FIT Course File (`generate_fit.py`)

Takes the official 145km GPX and produces a FIT course file with:
- **19 sector entries** (DANGER type): names like `19-5*-ARNBG`
- **19 sector exits** (GENERIC type): names like `END S19`
- **3 food station markers** (FOOD type)

Sector start/end coordinates are hardcoded as `(start_lat, start_lon, end_lat, end_lon)` tuples. Paris-Roubaix cobblestone sectors are well-documented public roads, and most of them exist as verified segments on popular cycling platforms with precise GPS data. If you want to adapt this for a different route or event, you'll need to provide your own sector coordinates in the same format.

### Race Plan Simulator (`race_plan.py`)

Pacing and nutrition model calibrated from two real rides:

| Parameter | Source | Value |
|-----------|--------|-------|
| Road speed | Recent ride (97km, same week) | 22.0 km/h |
| Cobble speed (5-star) | PRC 2025 (Carrefour de l'Arbre) | 18.0 km/h |
| Cobble speed (3-star) | PRC 2025 (avg sectors 8-1) | 21.0 km/h |
| Fatigue | After km 100 | -7% speed |
| Elevation | GPX profile, +671m total | +3 km/h penalty per 1% climb |
| Wind | Open-Meteo forecast, SE 12-15km/h | +13min vs no-wind baseline |
| Rider weight | Me | 100 kg |

Outputs a timeline with ETAs at every sector and food station, nutrition reminders (gels before each 5-star sector), a pacing comparison (ideal vs elevation vs wind), and sector-by-sector tactical notes.

### Interactive Road Book Map (`generate_map.py`)

Self-contained 265KB HTML file:
- Route with color-coded sector overlays (grey/gold/orange/red by difficulty)
- Clickable sector badges with ETA and tactical notes
- Collapsible road book panel: timeline, nutrition, wind info
- Wind impact layer: red = headwind, green = tailwind, with direction arrows
- SVG elevation profile at bottom with sector bands and wind zones
- Three map tiles: OpenStreetMap, Satellite, CartoDB Light

Share the HTML file directly. All data is embedded, only map tiles need internet.

## The 19 Sectors

| # | Name | km | ETA | Notes |
|---|------|-----|------|-------|
| S19 ★★★★★ | Trouee d'Arenberg | 51 | 11:01 | Forest trench. Ride the crown. GEL here. |
| S18 ★★★ | Wallers a Helesmes | 58 | 11:18 | Recovery sector after Arenberg. |
| S17 ★★★★ | Hornaing a Wandignies | 64 | 11:35 | LONGEST (3.7km). Pace like a TT. |
| S16 ★★★ | Warlaing a Brillon | 72 | 11:54 | Bumpy but rideable. Drink here. |
| S15 ★★★★ | Tilloy a Sars-et-Rosieres | 75 | 12:03 | Uphill kicker mid-sector. |
| S14 ★★★ | Beuvry-la-Foret a Orchies | 82 | 12:32 | Right after Ravito 2. |
| S13 ★★★ | Orchies | 87 | 12:44 | Urban. Don't get stuck. |
| S12 ★★★★ | Auchy-lez-Orchies a Bersee | 93 | 12:59 | Long, exposed, windy. |
| S11 ★★★★★ | Mons-en-Pevele | 98 | 13:13 | THE hardest. Climbing on cobbles. GEL here. |
| S10 ★★ | Merignies a Avelin | 104 | 13:31 | Gift sector. Eat, drink. |
| S9 ★★★ | Pont-Thibault a Ennevelin | 108 | 13:39 | Watch for potholes on entry. |
| S8 ★★ | Templeuve (Moulin de Vertain) | 114 | 14:13 | Sprint through. |
| S7 ★★★ | Cysoing a Bourghelles | 120 | 14:32 | Gravel on the left bend. |
| S6 ★★★ | Bourghelles a Wannehain | 122 | 14:36 | Keep legs turning. |
| S5 ★★★★ | Camphin-en-Pevele | 126 | 14:49 | FINALE STARTS. Sharp left mid-sector. |
| S4 ★★★★★ | Carrefour de l'Arbre | 128 | 14:56 | Where it's won. Empty the tank. GEL here. |
| S3 ★★ | Gruson | 131 | 15:03 | Coast and recover. |
| S2 ★★ | Willems a Hem | 138 | 15:23 | Last cobbles. Stay focused. |
| S1 ★ | Pave Roubaix | 146 | 15:43 | 300m into the Velodrome. Soak it in. |

## Background

This replaces a stack of paid cycling tools:

| What I needed | Typical solution | What I built |
|---|---|---|
| Course file with sector markers | Paid course editors | `generate_fit.py` |
| Pacing with wind + elevation | Paid pacing/wind analysis tools | `race_plan.py` |
| Interactive road book map | Paid premium map features | `generate_map.py` |
| Nutrition planning | Training platforms / spreadsheet | Built into `race_plan.py` |

That's 2-3 subscriptions for a one-off event. Total time with Claude Code: ~2 hours. Total time cleaning up the repo and writing docs for public release: longer than the actual build. Classic.

The conversation wasn't "write me a script." It was iterative: getting sector coordinates, debugging UTF-8 encoding on a Garmin display (Unicode stars are 3 bytes each, who knew), calibrating a speed model from last year's race FIT file, and arguing about how many gels is too many gels.

The full development log with all the back-and-forth is in [SESSION_LOG.md](SESSION_LOG.md).

## Files

| File | Description |
|------|------------|
| `generate_fit.py` | FIT course file generator |
| `race_plan.py` | Pacing/nutrition simulator |
| `generate_map.py` | Interactive HTML road book map |
| `prc26-145kmvf.gpx` | Official 145km challenge GPX (input) |
| `segment_cache.json` | Local coordinate cache (gitignored, you build your own) |
| `race_plan.json` | Exported timeline data (consumed by map) |
| `prc26-145km-sectors.fit` | Generated Garmin FIT file |
| `prc26_course_map.html` | Generated interactive map |
| `prompt.md` | Original prompt that started the project |

## Credits

- Route data: [Paris-Roubaix Challenge](https://www.parisroubaixchallenge.com/en/the-race/route) official GPX
- Sector coordinates: manually extracted from Strava segment pages
- Weather forecast: [Open-Meteo](https://open-meteo.com/) API
- AI-assisted development: [Claude Code](https://claude.ai/claude-code) (Anthropic)
- Libraries: [fit-tool](https://pypi.org/project/fit-tool/), [garmin-fit-sdk](https://pypi.org/project/garmin-fit-sdk/), [gpxpy](https://pypi.org/project/gpxpy/), [Folium](https://python-visualization.github.io/folium/)

## License

MIT. The GPX file is property of the Paris-Roubaix Challenge organization.
