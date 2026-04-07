#!/usr/bin/env python3
"""PRC26 145km Race Day Plan — pacing, nutrition, and timeline."""

import json
import math
import os
from datetime import datetime, timedelta

import gpxpy

GPX_FILE = "prc26-145kmvf.gpx"
CACHE_FILE = "segment_cache.json"
MATCH_THRESHOLD_M = 100

# Elevation speed adjustment: per 1% gradient
CLIMB_PENALTY_PER_PCT = 3.0   # lose 3 km/h per 1% uphill
DESCENT_BONUS_PER_PCT = 1.5   # gain 1.5 km/h per 1% downhill (capped)
START_TIME = datetime(2026, 4, 11, 8, 0, 0)  # 8:00 AM local

# Wind forecast (Open-Meteo, fetched 2026-04-07 for 2026-04-11)
# SE wind ~130-140° at 12-15 km/h, gusting as afternoon warms
# Route goes S then N: headwind component going south, tailwind returning
WIND = {
    "direction_deg": 135,
    "direction_label": "SE",
    "speed_kmh_morning": 12,
    "speed_kmh_afternoon": 15,
    "temp_start": 6,
    "temp_peak": 18,
    "rain_pct": 0,
    "summary": "SE 12-15km/h. Headwind going south, tailwind returning. Dry, 6→18°C.",
}

# Last year's data: 70km @ 24.6 km/h moving avg, 184W avg, 164 bpm avg
# Cobble speeds from last year (sectors 8→1):
#   5★: 19.8 km/h (Carrefour de l'Arbre)
#   4★: 23.3 km/h (Camphin)
#   3★: 24.2 km/h (avg of Cysoing/Bourghelles)
#   2★: 24.0-28.6 km/h
#   1★: 25.5 km/h
# Road moving speed: ~25.0 km/h

# Speed model (km/h) — conservative for 145km (last year was 70km @ 24.6)
COBBLE_SPEED = {5: 18.0, 4: 19.5, 3: 21.0, 2: 22.0, 1: 23.0}
ROAD_SPEED = 22.0  # km/h — realistic for 145km, not the 70km sprint
FATIGUE_THRESHOLD_KM = 100  # after this, slow down
FATIGUE_FACTOR = 0.93  # 7% slower after threshold
FOOD_STOP_MIN = 12  # minutes per food station
START_DELAY_MIN = 3  # congestion at start

# Nutrition — SiS Beta Fuel + Clif Bars
# Strategy: DRINK-FIRST. Only 2 gels on the bike. Clif at stations.
GEL_CARBS = 40        # Beta Fuel gel = 40g carbs
BIDON_ML = 900        # 900ml bidons
BIDON_CARBS = 80      # 1 Beta Fuel pack per 900ml bidon = 80g carbs
CLIF_CARBS = 43       # Clif bar ≈ 43g carbs
GEL_INTERVAL_MIN = 120 # ~3 gels during ride (before each 5★ sector)
DRINK_RATE_ML_H = 750  # sip steadily — ~750ml/hour

SECTORS = [
    {"sector": 19, "stars": 5, "short": "ARNBG",  "name": "Trouée d'Arenberg"},
    {"sector": 18, "stars": 3, "short": "WALLR",  "name": "Wallers à Hélesmes"},
    { "sector": 17, "stars": 4, "short": "HORNNG", "name": "Hornaing à Wandignies"},
    {"sector": 16, "stars": 3, "short": "WRLNG",  "name": "Warlaing à Brillon"},
    {"sector": 15, "stars": 4, "short": "TILOY",  "name": "Tilloy à Sars-et-Rosières"},
    { "sector": 14, "stars": 3, "short": "BVRY",   "name": "Beuvry-la-Forêt à Orchies"},
    {"sector": 13, "stars": 3, "short": "ORCHS",  "name": "Orchies"},
    { "sector": 12, "stars": 4, "short": "AUCHY",  "name": "Auchy-lez-Orchies à Bersée"},
    { "sector": 11, "stars": 5, "short": "MONS",   "name": "Mons-en-Pévèle"},
    {"sector": 10, "stars": 2, "short": "MRGNS",  "name": "Mérignies à Avelin"},
    {"sector":  9, "stars": 3, "short": "ENNVL",  "name": "Pont-Thibault à Ennevelin"},
    { "sector":  8, "stars": 2, "short": "TMPLV",  "name": "Templeuve (Moulin de Vertain)"},
    { "sector":  7, "stars": 3, "short": "CYSNG",  "name": "Cysoing à Bourghelles"},
    {"sector":  6, "stars": 3, "short": "BRGH",   "name": "Bourghelles à Wannehain"},
    {"sector":  5, "stars": 4, "short": "CMPHN",  "name": "Camphin-en-Pévèle"},
    {"sector":  4, "stars": 5, "short": "ARBRE",  "name": "Carrefour de l'Arbre"},
    {"sector":  3, "stars": 2, "short": "GRUSN",  "name": "Gruson"},
    {"sector":  2, "stars": 2, "short": "HEM",    "name": "Willems à Hem"},
    {"sector":  1, "stars": 1, "short": "RUBX",   "name": "Pavé Roubaix"},
]

# Food stations with approximate km positions (from generate_fit.py output)
FOOD_STATIONS = [
    {"name": "Saméon", "km": 32.0},
    {"name": "Beuvry-la-Forêt", "km": 80.7},
    {"name": "Templeuve", "km": 113.5},
]

# Sector positions on the 145km course (from generate_fit.py output)
SECTOR_POSITIONS = {
    19: (51.3, 53.6),  18: (57.5, 58.9),  17: (64.1, 67.8),
    16: (71.6, 74.0),  15: (75.0, 77.4),  14: (81.9, 83.3),
    13: (86.8, 88.6),  12: (92.9, 95.4),  11: (98.3, 101.3),
    10: (104.4, 105.0),  9: (107.7, 109.1),  8: (113.8, 114.3),
     7: (120.2, 121.1),  6: (121.5, 122.3),  5: (125.6, 127.4),
     4: (128.3, 130.3),  3: (130.5, 131.6),  2: (138.3, 139.7),
     1: (146.2, 146.2),
}


def haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing(lat1, lon1, lat2, lon2):
    """Bearing in degrees (0=N, 90=E, 180=S, 270=W) from point 1 to point 2."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def build_elevation_profile(gpx_path):
    """Build profile: list of (km, elevation, lat, lon)."""
    with open(gpx_path) as f:
        gpx = gpxpy.parse(f)
    pts = list(gpx.tracks[0].segments[0].points)

    cum_dist = 0.0
    profile = [(0.0, pts[0].elevation or 0, pts[0].latitude, pts[0].longitude)]
    for i in range(1, len(pts)):
        d = haversine(pts[i - 1].latitude, pts[i - 1].longitude,
                      pts[i].latitude, pts[i].longitude)
        cum_dist += d
        profile.append((cum_dist / 1000, pts[i].elevation or 0, pts[i].latitude, pts[i].longitude))
    return profile


def interpolate_profile(profile, km, field_idx):
    """Interpolate a field from the profile at a given km."""
    for i in range(1, len(profile)):
        if profile[i][0] >= km:
            k0, k1 = profile[i - 1][0], profile[i][0]
            v0, v1 = profile[i - 1][field_idx], profile[i][field_idx]
            if k1 == k0:
                return v0
            frac = (km - k0) / (k1 - k0)
            return v0 + frac * (v1 - v0)
    return profile[-1][field_idx]


def get_gradient(profile, from_km, to_km):
    """Average gradient (%) between two km marks."""
    e_start = interpolate_profile(profile, from_km, 1)
    e_end = interpolate_profile(profile, to_km, 1)
    dist_km = to_km - from_km
    if dist_km < 0.01:
        return 0.0
    return (e_end - e_start) / (dist_km * 1000) * 100


def get_bearing(profile, from_km, to_km):
    """Average bearing (degrees) of the route between two km marks."""
    lat1 = interpolate_profile(profile, from_km, 2)
    lon1 = interpolate_profile(profile, from_km, 3)
    lat2 = interpolate_profile(profile, to_km, 2)
    lon2 = interpolate_profile(profile, to_km, 3)
    return bearing(lat1, lon1, lat2, lon2)


def get_wind_effect(profile, from_km, to_km, wind_dir_deg, wind_speed_kmh):
    """Compute headwind component (positive = headwind, negative = tailwind).

    wind_dir_deg: meteorological "from" direction (135 = wind FROM SE).
    Returns (headwind_kmh, speed_adjustment_kmh).
    """
    rider_bearing = get_bearing(profile, from_km, to_km)
    # Angle between wind source and rider direction
    # headwind when wind_from == rider_bearing (riding into the wind)
    angle = math.radians(wind_dir_deg - rider_bearing)
    headwind = wind_speed_kmh * math.cos(angle)
    # Speed impact: ~0.3 km/h per 1 km/h headwind for a 100kg rider at 22 km/h
    speed_adj = -headwind * 0.3
    return headwind, speed_adj


def adjust_speed_for_gradient(base_speed, gradient_pct):
    """Adjust speed based on gradient. Positive = uphill."""
    if gradient_pct > 0:
        adjusted = base_speed - gradient_pct * CLIMB_PENALTY_PER_PCT
    else:
        adjusted = base_speed + abs(gradient_pct) * DESCENT_BONUS_PER_PCT
    return max(12.0, min(adjusted, base_speed + 8))


def format_time(dt):
    return dt.strftime("%H:%M")


def stars_str(n):
    return "*" * n


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Load elevation profile from GPX
    print("Loading elevation profile...")
    elevation_profile = build_elevation_profile(GPX_FILE)
    total_ascent = sum(max(0, elevation_profile[i][1] - elevation_profile[i-1][1])
                       for i in range(1, len(elevation_profile)))
    print(f"  Total climbing: +{total_ascent:.0f}m")

    # Build a sorted list of all events on the course
    events = []

    # Add sectors
    for sec in SECTORS:
        entry_km, exit_km = SECTOR_POSITIONS[sec["sector"]]
        events.append({
            "km": entry_km,
            "type": "sector_start",
            "sector": sec["sector"],
            "stars": sec["stars"],
            "name": sec["name"],
            "short": sec["short"],
            "exit_km": exit_km,
        })

    # Add food stations
    for fs in FOOD_STATIONS:
        events.append({
            "km": fs["km"],
            "type": "food",
            "name": fs["name"],
        })

    events.sort(key=lambda e: e["km"])

    # Simulate the ride
    current_time = START_TIME + timedelta(minutes=START_DELAY_MIN)
    current_km = 0.0
    elapsed_riding_min = 0.0  # total riding time (excl. stops)

    total_cobble_km = 0
    total_cobble_min = 0
    total_road_km = 0
    total_road_min = 0
    total_stop_min = 0

    # Nutrition tracking — SiS Beta Fuel + Clif Bars
    # Carbs are tracked from: gels, bars, drinks (consumed), station food
    # Fluid is tracked as total consumed (= riding time * drink rate)
    gel_count = 0
    bar_count = 0
    last_fuel_min = 0   # last gel/bar riding-time marker
    bidon_sets = 0      # number of bidon refills (2 bidons each)
    carbs_gels = 0
    carbs_bars = 0
    carbs_station = 0
    carbs_drink = 0     # from Beta Fuel bidons (consumed via sipping)
    fluid_total = 0     # total ml consumed

    timeline = []

    # Pre-start
    timeline.append({
        "time": format_time(START_TIME),
        "km": 0.0,
        "event": "START — Roubaix",
        "note": "Eat breakfast 2-3h before. Last gel 15min before start.",
        "nutrition": "2x Beta Fuel bidons (160g carbs). Pre-start gel: +40g.",
    })
    bidon_sets = 1
    gel_count = 1            # pre-start gel
    carbs_gels = GEL_CARBS   # 40g from pre-start gel

    # Hardcoded gel moments: before each 5★ sector
    GEL_SECTORS = {19, 11, 4}  # Arenberg, Mons-en-Pévèle, Carrefour de l'Arbre

    def check_gel_for_sector(sector_num):
        """Return gel note if this is a hardcoded gel sector."""
        nonlocal gel_count, carbs_gels
        if sector_num in GEL_SECTORS:
            gel_count += 1
            carbs_gels += GEL_CARBS
            return f"GEL #{gel_count} (Beta Fuel, 40g) — fuel up before 5★"
        return ""

    for ev in events:
        target_km = ev["km"]

        # Travel from current position to event
        if target_km > current_km:
            gap_km = target_km - current_km
            fatigued = current_km >= FATIGUE_THRESHOLD_KM
            gradient = get_gradient(elevation_profile, current_km, target_km)
            # Wind effect: interpolate speed based on time of day
            hours_in = (current_time - START_TIME).total_seconds() / 3600
            wind_speed = WIND["speed_kmh_morning"] + (WIND["speed_kmh_afternoon"] - WIND["speed_kmh_morning"]) * min(1, hours_in / 7)
            _, wind_adj = get_wind_effect(elevation_profile, current_km, target_km, WIND["direction_deg"], wind_speed)

            speed = adjust_speed_for_gradient(ROAD_SPEED, gradient) + wind_adj
            if fatigued:
                speed *= FATIGUE_FACTOR
            speed = max(12.0, speed)

            travel_min = gap_km / speed * 60
            current_time += timedelta(minutes=travel_min)
            current_km = target_km
            total_road_km += gap_km
            total_road_min += travel_min
            elapsed_riding_min += travel_min

            # Drinking: steady sipping of Beta Fuel mix
            fluid_consumed = travel_min / 60 * DRINK_RATE_ML_H
            fluid_total += fluid_consumed
            # Carbs from drink: 80g per 900ml, consumed at drink rate
            carbs_drink += fluid_consumed / BIDON_ML * BIDON_CARBS

        if ev["type"] == "sector_start":
            sector_km = ev["exit_km"] - ev["km"]
            stars = ev["stars"]
            fatigued = current_km >= FATIGUE_THRESHOLD_KM
            gradient = get_gradient(elevation_profile, ev["km"], ev["exit_km"])
            hours_in = (current_time - START_TIME).total_seconds() / 3600
            wind_speed = WIND["speed_kmh_morning"] + (WIND["speed_kmh_afternoon"] - WIND["speed_kmh_morning"]) * min(1, hours_in / 7)
            headwind, wind_adj = get_wind_effect(elevation_profile, ev["km"], ev["exit_km"], WIND["direction_deg"], wind_speed)

            cobble_speed = adjust_speed_for_gradient(COBBLE_SPEED[stars], gradient) + wind_adj
            if fatigued:
                cobble_speed *= FATIGUE_FACTOR
            cobble_speed = max(12.0, cobble_speed)

            cobble_min = sector_km / cobble_speed * 60
            total_cobble_km += sector_km
            total_cobble_min += cobble_min

            # Gel before 5★ sectors only
            fuel_note = check_gel_for_sector(ev["sector"])

            grade_str = f" {gradient:+.1f}%" if abs(gradient) > 0.2 else ""
            if headwind > 1:
                wind_str = f" 🌬{headwind:.0f}km/h head"
            elif headwind < -1:
                wind_str = f" 🌬{abs(headwind):.0f}km/h tail"
            else:
                wind_str = ""
            timeline.append({
                "time": format_time(current_time),
                "km": current_km,
                "event": f"S{ev['sector']} {stars_str(stars)} {ev['name']}",
                "note": f"{sector_km:.1f}km @ ~{cobble_speed:.0f}km/h → {cobble_min:.0f}min{grade_str}{wind_str}",
                "nutrition": fuel_note,
            })

            current_time += timedelta(minutes=cobble_min)
            current_km = ev["exit_km"]
            elapsed_riding_min += cobble_min

            # Drink continues on cobbles
            fluid_consumed = cobble_min / 60 * DRINK_RATE_ML_H
            fluid_total += fluid_consumed
            carbs_drink += fluid_consumed / BIDON_ML * BIDON_CARBS

        elif ev["type"] == "food":
            total_stop_min += FOOD_STOP_MIN

            # Refill bidons (fluid/carbs counted when consumed via sipping)
            bidon_sets += 1
            # Eat a Clif bar + whatever the station has
            bar_count += 1
            carbs_bars += CLIF_CARBS
            carbs_station += 30  # station food (banana, etc.)

            timeline.append({
                "time": format_time(current_time),
                "km": current_km,
                "event": f"RAVITO — {ev['name']}",
                "note": f"~{FOOD_STOP_MIN}min stop",
                "nutrition": f"Refill 2x 900ml Beta Fuel bidons (160g). Eat CLIF #{bar_count} + station food.",
            })
            current_time += timedelta(minutes=FOOD_STOP_MIN)

    # Travel remaining distance to finish
    remaining_km = 146.7 - current_km
    if remaining_km > 0.1:
        speed = ROAD_SPEED * FATIGUE_FACTOR
        travel_min = remaining_km / speed * 60
        current_time += timedelta(minutes=travel_min)
        total_road_km += remaining_km
        total_road_min += travel_min
        elapsed_riding_min += travel_min
        fluid_consumed = travel_min / 60 * DRINK_RATE_ML_H
        fluid_total += fluid_consumed
        carbs_drink += fluid_consumed / BIDON_ML * BIDON_CARBS

    finish_time = current_time
    timeline.append({
        "time": format_time(finish_time),
        "km": 146.7,
        "event": "FINISH — Roubaix Vélodrome",
        "note": "",
        "nutrition": "",
    })

    # ─────────── PRINT PLAN ───────────
    total_elapsed = (finish_time - START_TIME).total_seconds() / 60

    print("=" * 90)
    print("  PARIS-ROUBAIX CHALLENGE 2026 — 145km RACE PLAN")
    print(f"  Departure: {format_time(START_TIME)} | Estimated finish: {format_time(finish_time)}")
    print(f"  Total time: {total_elapsed:.0f}min ({total_elapsed/60:.1f}h)")
    print("=" * 90)

    print(f"\n{'TIME':>5} {'KM':>6}  {'EVENT':<42} {'NOTE'}")
    print("─" * 90)
    for t in timeline:
        line = f"{t['time']:>5} {t['km']:>5.1f}k  {t['event']:<42} {t['note']}"
        if t["nutrition"]:
            line += f"\n{'':>14}{'🥤 ' + t['nutrition']}"
        print(line)
    print("─" * 90)

    # ─── Compute comparison: ideal vs elevation vs elevation+wind ───
    def simple_time(dist_km, base_speed, gradient=0.0, wind_adj=0.0, fatigued=False):
        s = base_speed
        if gradient != 0:
            s = adjust_speed_for_gradient(s, gradient)
        s += wind_adj
        if fatigued:
            s *= FATIGUE_FACTOR
        return dist_km / max(12, s) * 60

    ideal_min = 0
    elev_min = 0
    full_min = 0  # = total_road_min + total_cobble_min (already computed)

    # Also build per-5km wind segments for the map
    wind_segments = []
    for km_start in range(0, 147, 5):
        km_end = min(km_start + 5, 146.7)
        if km_end <= km_start:
            continue
        gradient = get_gradient(elevation_profile, km_start, km_end)
        rider_brg = get_bearing(elevation_profile, km_start, km_end)
        # Use average wind speed for the race
        avg_wind = (WIND["speed_kmh_morning"] + WIND["speed_kmh_afternoon"]) / 2
        hw, w_adj = get_wind_effect(elevation_profile, km_start, km_end, WIND["direction_deg"], avg_wind)
        fatigued = km_start >= FATIGUE_THRESHOLD_KM
        gap = km_end - km_start

        t_ideal = simple_time(gap, ROAD_SPEED, fatigued=fatigued)
        t_elev = simple_time(gap, ROAD_SPEED, gradient=gradient, fatigued=fatigued)
        t_full = simple_time(gap, ROAD_SPEED, gradient=gradient, wind_adj=w_adj, fatigued=fatigued)

        ideal_min += t_ideal
        elev_min += t_elev

        lat = interpolate_profile(elevation_profile, (km_start + km_end) / 2, 2)
        lon = interpolate_profile(elevation_profile, (km_start + km_end) / 2, 3)
        wind_segments.append({
            "km_start": km_start,
            "km_end": round(km_end, 1),
            "bearing": round(rider_brg),
            "headwind": round(hw, 1),
            "wind_adj_kmh": round(w_adj, 1),
            "gradient": round(gradient, 2),
            "time_ideal": round(t_ideal, 1),
            "time_elev": round(t_elev, 1),
            "time_full": round(t_full, 1),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
        })

    ideal_total = ideal_min + total_stop_min + START_DELAY_MIN
    elev_total = elev_min + total_stop_min + START_DELAY_MIN

    # Summary stats
    print(f"""
{'=' * 90}
  PACING COMPARISON
{'=' * 90}
  {'':>30} {'Ideal':>10} {'+ Elevation':>12} {'+ Elev + Wind':>14}
  {'Road time:':>30} {ideal_min:.0f}min      {elev_min:.0f}min        {total_road_min + total_cobble_min:.0f}min
  {'+ stops + delay:':>30} {ideal_total:.0f}min      {elev_total:.0f}min        {total_elapsed:.0f}min
  {'Finish:':>30} {format_time(START_TIME + timedelta(minutes=ideal_total)):>10} {format_time(START_TIME + timedelta(minutes=elev_total)):>12} {format_time(finish_time):>14}

  Wind impact: {total_elapsed - elev_total:+.0f}min vs flat ({WIND['summary']})
  Elevation impact: {elev_total - ideal_total:+.0f}min vs ideal (+{total_ascent:.0f}m climbing)

{'=' * 90}
  PACING SUMMARY
{'=' * 90}
  Road:        {total_road_km:.0f}km in {total_road_min:.0f}min ({total_road_km/total_road_min*60:.1f} km/h avg)
  Cobblestones:{total_cobble_km:.0f}km in {total_cobble_min:.0f}min ({total_cobble_km/total_cobble_min*60:.1f} km/h avg)
  Food stops:  {total_stop_min:.0f}min ({len(FOOD_STATIONS)} stations × {FOOD_STOP_MIN}min)
  Start delay: {START_DELAY_MIN}min
  Total:       {146.7:.0f}km in {total_elapsed:.0f}min ({total_elapsed/60:.1f}h)
  Overall avg: {146.7/(total_elapsed/60):.1f} km/h (elapsed)

{'=' * 90}
  NUTRITION PLAN — SiS Beta Fuel + Clif Bars
{'=' * 90}
  Target: ~80g carbs/hour, ~750ml fluid/hour (drink-first, minimal gels)

  Products:
    • SiS Beta Fuel drink mix: 80g carbs per 900ml bidon
    • SiS Beta Fuel gel: 40g carbs per gel
    • Clif Bar: ~43g carbs per bar

  Before start:
    • Breakfast 2-3h before (oatmeal, banana, coffee)
    • 2x 900ml Beta Fuel bidons ready (160g carbs)
    • Pre-start gel 15min before (40g carbs)

  On the bike:
    • DRINK IS KING — sip Beta Fuel steadily (~67g carbs/h from drink alone)
    • 3 gels max on the bike: before each 5★ sector (Arenberg, Mons, Arbre)
    • Clif bars at food stations only — eat while stopped
    • If stomach feels off, skip the gel. The drink is enough.

  Estimated totals:
    • Beta Fuel gels: {gel_count} ({carbs_gels:.0f}g carbs)
    • Clif bars: {bar_count} ({carbs_bars:.0f}g carbs)
    • Beta Fuel drink: {fluid_total/1000:.1f}L consumed ({carbs_drink:.0f}g carbs)
    • Station food: ~{carbs_station:.0f}g carbs
    • Bidon refills: {bidon_sets} sets (2x 900ml each)
    • TOTAL CARBS: ~{carbs_gels+carbs_bars+carbs_drink+carbs_station:.0f}g (~{(carbs_gels+carbs_bars+carbs_drink+carbs_station)/(total_elapsed/60):.0f}g/hour)
    • TOTAL FLUID: ~{fluid_total/1000:.1f}L (~{fluid_total/(total_elapsed/60):.0f}ml/hour)

  Bidon strategy (2x 900ml = 1.8L per set):
    • Start: 2x Beta Fuel bidons (1.8L, 160g carbs)
    • Ravito 1 (km 32): refill both — ~1.5h into race
    • Ravito 2 (km 81): refill both — ~3.5h into race
    • Ravito 3 (km 114): refill both — LAST CHANCE!
    • km 114→147 (33km, ~1.5h): 1.8L should last to finish

  SHOPPING LIST / WHAT TO PACK:
    • 4x SiS Beta Fuel gel (1 pre-start + 3 on bike. 1 spare)
    • 3x Clif Bar (1 per food station)
    • 8x SiS Beta Fuel drink sachets (1 per bidon × 2 bidons × 4 fills)
      → pre-mix 2 bidons at home, bring 6 sachets in ravito bag
    • Ravito bag: 6 Beta Fuel sachets + 2 spare Clif bars + 1 spare gel

{'=' * 90}
  SECTOR NOTES
{'=' * 90}
  S19 ***** Trouée d'Arenberg (2.3km)
       Forest trench. Deep, rough, cambered pavé — ride the crown or
       right gutter. Gaps between stones swallow wheels. Don't overcook
       the entry on adrenaline. Full commitment, no braking.

  S18 ***   Wallers à Hélesmes (1.4km)
       Recovery sector after Arenberg. Stay in smoother tire tracks on
       the right side. Regroup here.

  S17 ****  Hornaing à Wandignies (3.7km)
       LONGEST sector. War of attrition — pace it like a TT, not a
       sprint. Uneven surface, random deep gaps. Left side often smoother.

  S16 ***   Warlaing à Brillon (2.4km)
       Bumpy but rideable. Good place to eat/drink before the next block.

  S15 ****  Tilloy à Sars-et-Rosières (2.4km)
       Fast entry then progressively rougher, with an uphill kicker
       mid-sector. Stay on the crown. Shift down early for the rise.

  S14 ***   Beuvry-la-Forêt à Orchies (1.4km) — Right after Ravito 2.
       Straight, good sight lines. Settle into rhythm.
  S13 ***   Orchies (1.7km) — Urban pavé, some turns to watch for.
       Don't get stuck behind slower riders on narrow sections.

  S12 ****  Auchy-lez-Orchies à Bersée (2.7km)
       Long, exposed, often windy. Deep joints between stones. Camber
       pushes you toward the gutter — fight to hold center-left.

  S11 ***** Mons-en-Pévèle (3km)
       THE hardest sector. Starts with a sharp rise, then rolling terrain
       on savage pavé. Hill mid-sector is where it hurts most. Stay
       seated on climbs for traction, stand only at the top. Mud-prone
       when wet. Go in well-fueled. All-out effort.

  S10 **    Mérignies à Avelin (0.7km) — Gift sector. Spin, drink, eat.
  S9  ***   Pont-Thibault à Ennevelin (1.4km) — Watch for potholes on entry.
  S8  **    Templeuve Moulin de Vertain (0.5km) — Sprint through.
  S7  ***   Cysoing à Bourghelles (0.9km) — Watch the left-hand bend
       mid-sector, gravel collects on the outside.
  S6  ***   Bourghelles à Wannehain (0.8km) — Keep legs turning,
       Camphin is coming.

  S5  ****  Camphin-en-Pévèle (1.8km)
       THE FINALE STARTS. Narrow, twisting, deceptively hard. Sharp left
       turn mid-sector catches people. Rise at the end stings tired legs.
       Commit — Carrefour de l'Arbre is next.

  S4  ***** Carrefour de l'Arbre (2.1km)
       Where Paris-Roubaix is won. Fast entry then progressively more
       violent. Crown is pronounced — stay on top or get bounced into
       the gutter. Final 500m is the roughest. Empty the tank.

  S3  **    Gruson (1.1km) — Tame after Carrefour. Coast and recover.
  S2  **    Willems à Hem (1.4km) — Last real cobbles. Stay focused —
       tired legs make crashes happen on easy sectors.

  S1  *     Roubaix (0.3km)
       300m of smooth-ish stones into the Vélodrome. Soak it in.

{'=' * 90}
  KEY MOMENTS
{'=' * 90}
  km 32  — Ravito 1: First refuel. Don't rush, eat properly.
  km 51  — S19 Arenberg: FIRST big sector. Stay loose, ride the crown.
  km 64  — S17 Hornaing: 3.7km — longest sector. Don't blow up.
  km 81  — Ravito 2: Halfway refuel. Eat well — long stretch ahead.
  km 98  — S11 Mons-en-Pévèle: 3km of hell with climbing. THE test.
  km 100 — Fatigue kicks in. Focus on cadence and hydration.
  km 114 — Ravito 3: LAST food stop. Fill everything. Check kit.
  km 125 — S5 Camphin: The finale begins. 7 sectors in 21km.
  km 128 — S4 Carrefour de l'Arbre: All or nothing. Commit.
  km 138 — S2 Willems à Hem: Last cobbles before the Vélodrome.
  km 146 — S1 Roubaix: 300m into the Vélodrome. SAVOUR IT.
""")


    # Export timeline as JSON for the HTML map
    export = {
        "start_time": format_time(START_TIME),
        "finish_time": format_time(finish_time),
        "total_hours": round(total_elapsed / 60, 1),
        "timeline": timeline,
        "nutrition": {
            "gels": gel_count,
            "bars": bar_count,
            "carbs_total": round(carbs_gels + carbs_bars + carbs_drink + carbs_station),
            "carbs_per_hour": round((carbs_gels + carbs_bars + carbs_drink + carbs_station) / (total_elapsed / 60)),
            "fluid_liters": round(fluid_total / 1000, 1),
        },
        "wind": WIND,
        "wind_segments": wind_segments,
        "elevation": f"+{total_ascent:.0f}m",
    }
    with open("race_plan.json", "w") as f:
        json.dump(export, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Timeline exported to race_plan.json")


if __name__ == "__main__":
    main()
