#!/usr/bin/env python3
"""PRC26 Race FIT Generator — physics-based pacing via plan_ride().

Replaces the hand-rolled speed tables in race_plan.py with validated
physics from bike_power_model. Generates:
  1. Course FIT with Virtual Partner pacing at plan_ride() speeds
  2. Power Guide FIT (messages 352/353) for Garmin Power Guide feature
  3. Race timeline with per-sector predictions
"""

import math
import os
import sys

# Add bike_power_model to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fit-power-guide", "src"))

from bike_power_model.intervals_icu import IntervalsICU
from bike_power_model.model import CourseWaypoint, RaceConditions, RiderProfile
from bike_power_model.pipeline import plan_ride
from bike_power_model.writer import write_fit

# ---------------------------------------------------------------------------
# Course & sector data
# ---------------------------------------------------------------------------

GPX_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prc26-145kmvf.gpx")

# Sector positions on the 145km course (from generate_fit.py matching)
SECTORS = [
    {"sector": 19, "stars": 5, "short": "ARNBG",  "name": "Trouée d'Arenberg",          "km": (51.3, 53.6)},
    {"sector": 18, "stars": 3, "short": "WALLR",  "name": "Wallers à Hélesmes",          "km": (57.5, 58.9)},
    {"sector": 17, "stars": 4, "short": "HORNNG", "name": "Hornaing à Wandignies",       "km": (64.1, 67.8)},
    {"sector": 16, "stars": 3, "short": "WRLNG",  "name": "Warlaing à Brillon",          "km": (71.6, 74.0)},
    {"sector": 15, "stars": 4, "short": "TILOY",  "name": "Tilloy à Sars-et-Rosières",   "km": (75.0, 77.4)},
    {"sector": 14, "stars": 3, "short": "BVRY",   "name": "Beuvry-la-Forêt à Orchies",   "km": (81.9, 83.3)},
    {"sector": 13, "stars": 3, "short": "ORCHS",  "name": "Orchies",                     "km": (86.8, 88.6)},
    {"sector": 12, "stars": 4, "short": "AUCHY",  "name": "Auchy-lez-Orchies à Bersée",  "km": (92.9, 95.4)},
    {"sector": 11, "stars": 5, "short": "MONS",   "name": "Mons-en-Pévèle",              "km": (98.3, 101.3)},
    {"sector": 10, "stars": 2, "short": "MRGNS",  "name": "Mérignies à Avelin",          "km": (104.4, 105.0)},
    {"sector":  9, "stars": 3, "short": "ENNVL",  "name": "Pont-Thibault à Ennevelin",   "km": (107.7, 109.1)},
    {"sector":  8, "stars": 2, "short": "TMPLV",  "name": "Templeuve (Moulin de Vertain)","km": (113.8, 114.3)},
    {"sector":  7, "stars": 3, "short": "CYSNG",  "name": "Cysoing à Bourghelles",       "km": (120.2, 121.1)},
    {"sector":  6, "stars": 3, "short": "BRGH",   "name": "Bourghelles à Wannehain",     "km": (121.5, 122.3)},
    {"sector":  5, "stars": 4, "short": "CMPHN",  "name": "Camphin-en-Pévèle",           "km": (125.6, 127.4)},
    {"sector":  4, "stars": 5, "short": "ARBRE",  "name": "Carrefour de l'Arbre",        "km": (128.3, 130.3)},
    {"sector":  3, "stars": 2, "short": "GRUSN",  "name": "Gruson",                      "km": (130.5, 131.6)},
    {"sector":  2, "stars": 2, "short": "HEM",    "name": "Willems à Hem",               "km": (138.3, 139.7)},
    {"sector":  1, "stars": 1, "short": "RUBX",   "name": "Pavé Roubaix",                "km": (146.2, 146.2)},
]

FOOD_STATIONS = [
    {"name": "Saméon", "km": 32.0},
    {"name": "Beuvry-la-Forêt", "km": 80.7},
    {"name": "Templeuve", "km": 113.5},
]

# Gels before 5-star sectors
GEL_SECTORS = {19: "GEL pre-ARNBG", 11: "GEL pre-MONS", 4: "GEL pre-ARBRE"}

# Star rating → cobble surface type.
# Downgraded one level vs road tires: 40mm gravel tires absorb more vibration,
# so the effective Crr penalty is lower than for road tires on cobbles.
STAR_TO_SURFACE = {
    5: "cobbles_rough",     # Crr=0.014 (road tire: severe=0.020)
    4: "cobbles_moderate",  # Crr=0.011 (road tire: rough=0.014)
    3: "cobbles_good",      # Crr=0.008 (road tire: moderate=0.011)
    2: "cobbles_good",      # Crr=0.008
    1: "cobbles_good",      # Crr=0.008
}


# ---------------------------------------------------------------------------
# Weather — Open-Meteo forecast fetched 2026-04-10 evening for 2026-04-11
# ---------------------------------------------------------------------------
# Race window 08:00-14:00:
#   Morning (08-10): SSE 150-160°, 18-19 km/h, dry, 13→17°C
#   Midday (10-12): S→SSW shift 180-216°, 20-22 km/h, 17→14°C
#   Afternoon (12-14): WSW 247-269°, 20-25 km/h, 11-14°C, dry
#   Strong wind all day, shifting from SE to W through the race.
#   Late cobble sectors (km 120+) face westerly 25 km/h.
#
# Using race-window average (8h-14h):
WEATHER = {
    "wind_dir_deg": 214,       # SSW average across race window
    "wind_speed_kmh": 20,      # 18-25 km/h sustained, avg 20
    "temperature_c": 14,       # average
    "humidity_pct": 70,        # higher than yesterday's forecast
    "terrain_roughness": 0.35, # open farmland, low hedgerows
    "wet": False,              # dry all day, no rain in forecast
}


def build_surface_zones():
    """Map cobble sectors to surface zones by km position."""
    zones = []
    for sec in SECTORS:
        from_km, to_km = sec["km"]
        surface = STAR_TO_SURFACE[sec["stars"]]
        zones.append((from_km, to_km, surface))
    return zones


def build_pacing_zones():
    """Course-specific pacing strategy.

    Calibrated from PRC 2025 data: Sam naturally pushes harder on cobbles
    (adrenaline + need power to maintain speed on rough surfaces).
    Road sections between sectors are recovery.
    """
    # Strategic pacing only — no cobble-specific boosts needed.
    # The surface-aware optimizer naturally allocates more power to
    # high-Crr sectors (each extra watt saves ~1.5x more time on cobbles).
    return [
        (0, 51, 0.88),       # pre-cobbles: conserve legs
        (131, 147, 1.05),    # finale to Roubaix: push if legs allow
    ]


def build_waypoints():
    """Build course waypoints for Garmin 'Up Ahead' alerts."""
    wps = []

    # Food stations
    for fs in FOOD_STATIONS:
        # Bidon refill reminder 1km before
        wps.append(CourseWaypoint(km=fs["km"] - 1.0, type="drink", name=f"REFILL bidons"))
        # Food station
        wps.append(CourseWaypoint(km=fs["km"], type="food", name=f"RAVITO {fs['name'][:20]}"))

    # Sector entry/exit + gel reminders
    for sec in SECTORS:
        from_km, to_km = sec["km"]
        # Gel reminder 0.5km before 5-star sectors
        if sec["sector"] in GEL_SECTORS:
            wps.append(CourseWaypoint(km=from_km - 0.5, type="gel", name=GEL_SECTORS[sec["sector"]]))
        # Sector entry
        name = f"{sec['sector']}-{'*'*sec['stars']}-{sec['short']}"
        wps.append(CourseWaypoint(km=from_km, type="danger", name=name[:32]))
        # Sector exit
        wps.append(CourseWaypoint(km=to_km, type="generic", name=f"END S{sec['sector']}"))

    wps.sort(key=lambda w: w.km)
    return wps


def fetch_season_pdc():
    """Fetch this season's power-duration curve from intervals.icu."""
    # Load API key from config
    env_file = os.path.expanduser("~/.config/bike-power-model/.env")
    api_key = None
    if os.path.isfile(env_file):
        for line in open(env_file):
            line = line.strip()
            if line.startswith("INTERVALS_ICU_API_KEY="):
                api_key = line.split("=", 1)[1].strip("'\"")
    if not api_key:
        api_key = os.environ.get("INTERVALS_ICU_API_KEY")
    if not api_key:
        print("⚠  No intervals.icu API key found. Using default W' model.")
        return None

    client = IntervalsICU(api_key=api_key, athlete_id="0")
    pdc = client.power_curve(sport="Ride", period="s0")
    print(f"  PDC: CP={pdc.cp}W, W'={pdc.w_prime}J, FTP={pdc.ftp}W")
    print(f"  5s={pdc.power_at_duration(5)}W, 1min={pdc.power_at_duration(60)}W, "
          f"5min={pdc.power_at_duration(300)}W, 20min={pdc.power_at_duration(1200)}W")
    return pdc


def build_speed_schedule(result):
    """Convert plan_ride() splits to a speed schedule for Virtual Partner.

    Returns list of (from_km, to_km, speed_kmh) tuples.
    """
    schedule = []
    cum_km = 0.0
    for s in result.splits:
        dist_km = s.distance_m / 1000
        schedule.append((cum_km, cum_km + dist_km, s.speed_kmh))
        cum_km += dist_km
    return schedule


def print_race_timeline(result, start_hour=8, start_min=0):
    """Print a race timeline with sector predictions."""
    from datetime import datetime, timedelta

    start_time = datetime(2026, 4, 11, start_hour, start_min, 0)
    cum_time_s = 0.0
    cum_dist_m = 0.0

    # Build sector lookup
    sector_lookup = {}
    for sec in SECTORS:
        sector_lookup[(sec["km"][0], sec["km"][1])] = sec

    # Build food station lookup
    food_lookup = {fs["km"]: fs for fs in FOOD_STATIONS}

    print(f"\n{'='*80}")
    print(f"PRC26 Race Timeline — plan_ride() physics-based prediction")
    print(f"{'='*80}")
    wbal_hdr = "W'bal"
    print(f"{'Time':>6} {'Km':>6} {'Event':<35} {'Speed':>6} {'Power':>6} {wbal_hdr:>6}")
    print(f"{'─'*80}")

    # Start
    print(f"{start_time.strftime('%H:%M'):>6} {'0.0':>6} {'START — Roubaix':<35}")

    # Track sector times
    sector_times = {}
    in_sector = None
    sector_start_time = 0.0

    for s in result.splits:
        split_start_km = cum_dist_m / 1000
        split_end_km = (cum_dist_m + s.distance_m) / 1000
        split_mid_km = (split_start_km + split_end_km) / 2

        # Check if entering a sector
        for (from_km, to_km), sec in sector_lookup.items():
            if from_km <= split_mid_km < to_km and in_sector != sec["sector"]:
                in_sector = sec["sector"]
                sector_start_time = cum_time_s
                current_time = start_time + timedelta(seconds=cum_time_s)
                stars = "*" * sec["stars"]
                label = f"S{sec['sector']} {stars} {sec['name'][:25]}"
                print(f"{current_time.strftime('%H:%M'):>6} {split_start_km:>6.1f} {label:<35} "
                      f"{s.speed_kmh:>5.1f}k {s.power_watts:>5.0f}W "
                      f"{s.w_prime_balance_j/1000:>5.1f}k")
                break

        # Check if exiting a sector
        if in_sector:
            sec_data = next((sc for sc in SECTORS if sc["sector"] == in_sector), None)
            if sec_data and split_end_km > sec_data["km"][1]:
                sector_duration = cum_time_s + s.duration_s - sector_start_time
                sector_dist = sec_data["km"][1] - sec_data["km"][0]
                sector_speed = sector_dist / (sector_duration / 3600) if sector_duration > 0 else 0
                sector_times[in_sector] = {
                    "duration_s": sector_duration,
                    "speed_kmh": sector_speed,
                }
                in_sector = None

        # Check food stations (within 0.5km)
        for food_km, fs in food_lookup.items():
            if abs(split_mid_km - food_km) < 0.5:
                current_time = start_time + timedelta(seconds=cum_time_s)
                print(f"{current_time.strftime('%H:%M'):>6} {food_km:>6.1f} {'RAVITO — ' + fs['name']:<35}")
                food_lookup.pop(food_km)
                break

        cum_time_s += s.duration_s
        cum_dist_m += s.distance_m

    # Finish
    finish_time = start_time + timedelta(seconds=cum_time_s)
    total_km = cum_dist_m / 1000
    print(f"{'─'*80}")
    print(f"{finish_time.strftime('%H:%M'):>6} {total_km:>6.1f} {'FINISH — Roubaix':<35}")

    # Summary
    hours = cum_time_s / 3600
    print(f"\n{'─'*80}")
    print(f"Total time:  {int(hours)}h {int((hours % 1) * 60):02d}m ({cum_time_s:.0f}s)")
    print(f"Distance:    {total_km:.1f} km")
    print(f"Avg speed:   {result.avg_speed_kmh:.1f} km/h")
    print(f"Avg power:   {result.avg_power_watts:.0f} W ({result.avg_power_watts/result.rider_ftp*100:.0f}% FTP)")
    print(f"IF:          {result.avg_power_watts/result.rider_ftp:.2f}")

    # Sector summary
    if sector_times:
        print(f"\n{'─'*80}")
        print(f"Sector speeds:")
        for sec in SECTORS:
            if sec["sector"] in sector_times:
                st = sector_times[sec["sector"]]
                stars = "*" * sec["stars"]
                print(f"  S{sec['sector']:>2} {stars:<5} {sec['short']:<8} "
                      f"{st['speed_kmh']:>5.1f} km/h  ({st['duration_s']/60:>4.1f} min)")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("PRC26 Race FIT Generator — physics-based plan_ride()")
    print("=" * 60)

    # 1. Fetch season PDC
    print("\n1. Fetching season power-duration curve...")
    pdc = fetch_season_pdc()

    # 2. Build rider profile
    print("\n2. Setting up rider profile...")
    rider = RiderProfile(
        ftp=287,
        rider_mass_kg=100,
        bike_mass_kg=14,
        cda=0.53,           # casual position, gravel bike
        crr=0.007,           # calibrated from real rides (gravel tires on road)
        goal_effort=0.65,
        w_prime=pdc.w_prime if pdc else 14107,
        power_curve=pdc,
        draft="solo",        # sportive, not drafting
        fatigue="endurance",
    )
    target_power = rider.ftp * (0.33 + rider.goal_effort * 0.43)
    print(f"  FTP={rider.ftp}W, mass={rider.rider_mass_kg}+{rider.bike_mass_kg}kg")
    print(f"  CdA={rider.cda}, Crr={rider.crr}")
    print(f"  Goal effort={rider.goal_effort} → target ~{target_power:.0f}W ({target_power/rider.ftp*100:.0f}% FTP)")
    print(f"  Fatigue={rider.fatigue}, Pacing={rider.pacing}")
    print(f"  W'={rider.w_prime}J")

    # 3. Build race conditions
    print("\n3. Setting up race conditions...")
    conditions = RaceConditions(
        wind_speed_kmh=WEATHER["wind_speed_kmh"],
        wind_dir_deg=WEATHER["wind_dir_deg"],
        terrain_roughness=WEATHER["terrain_roughness"],
        temperature_c=WEATHER["temperature_c"],
        humidity_pct=WEATHER["humidity_pct"],
        wet=WEATHER["wet"],
        surface_zones=build_surface_zones(),
        pacing_zones=build_pacing_zones(),
    )
    print(f"  Wind: {WEATHER['wind_speed_kmh']}km/h from {WEATHER['wind_dir_deg']}° (SE)")
    print(f"  Temp: {WEATHER['temperature_c']}°C, Humidity: {WEATHER['humidity_pct']}%")
    print(f"  Surface zones: {len(conditions.surface_zones)} cobble sectors")
    print(f"  Pacing zones: pre-cobbles 0.90, gauntlet 1.00, finale 1.05")
    if WEATHER["wet"]:
        print(f"  ⚠ WET conditions — increased Crr")

    # 4. Build waypoints
    print("\n4. Building course waypoints...")
    waypoints = build_waypoints()
    print(f"  {len(waypoints)} waypoints (sectors, food, gels)")

    # 5. Run plan_ride()
    print("\n5. Running plan_ride()...")
    result = plan_ride(
        course_path=GPX_FILE,
        rider=rider,
        conditions=conditions,
        waypoints=waypoints,
        correct_elevation=False,  # GPX has DEM-corrected elevation
    )
    print(f"  ✓ {len(result.splits)} splits computed")
    print(f"  Total: {result.total_time_s/3600:.1f}h, {result.total_distance_m/1000:.1f}km, "
          f"{result.avg_speed_kmh:.1f} km/h, {result.avg_power_watts:.0f}W")

    # 6. Print race timeline
    print_race_timeline(result)

    # 7. Generate Power Guide FIT
    print(f"\n{'─'*80}")
    print("Generating FIT files...")
    guide = result.to_power_guide(name="PRC26-145km")
    power_guide_path = "prc26-power-guide.fit"
    write_fit(guide, power_guide_path, waypoints=waypoints)
    print(f"  ✓ Power Guide FIT: {power_guide_path}")

    # 8. Generate Course FIT with VP pacing from plan_ride() speeds
    speed_schedule = build_speed_schedule(result)
    print(f"  Speed schedule: {len(speed_schedule)} segments for Virtual Partner")

    # Use the existing generate_fit.py infrastructure for the course FIT
    from generate_fit import (
        GPX_FILE as GF_GPX,
        SECTORS as GF_SECTORS,
        GEL_SECTORS as GF_GEL_SECTORS,
        build_fit,
        compute_cumulative_distances,
        match_sector,
        nearest_trackpoint,
        parse_gpx,
        sector_entry_name,
        sector_exit_name,
        verify_fit,
    )
    from fit_tool.profile.profile_type import CoursePoint

    ENERGY_GEL = 32
    SPORTS_DRINK = 33

    trackpoints, gpx_waypoints = parse_gpx(GF_GPX)
    cum_dists = compute_cumulative_distances(trackpoints)
    print(f"  Course: {cum_dists[-1]/1000:.1f}km, {len(trackpoints)} trackpoints")

    # Build course points (same logic as generate_fit.py)
    course_points = []
    prev_exit_idx = 0
    for sec in GF_SECTORS:
        m = match_sector(sec["coords"], trackpoints, min_idx=prev_exit_idx)
        if m["entry_gpx_idx"] > m["exit_gpx_idx"]:
            m["entry_gpx_idx"], m["exit_gpx_idx"] = m["exit_gpx_idx"], m["entry_gpx_idx"]

        if sec["sector"] in GF_GEL_SECTORS:
            gel_idx = max(0, m["entry_gpx_idx"] - 6)
            course_points.append({
                "gpx_idx": gel_idx,
                "name": GF_GEL_SECTORS[sec["sector"]],
                "cp_type": ENERGY_GEL,
            })

        course_points.append({
            "gpx_idx": m["entry_gpx_idx"],
            "name": sector_entry_name(sec["sector"], sec["stars"], sec["short"]),
            "cp_type": CoursePoint.DANGER,
        })
        course_points.append({
            "gpx_idx": m["exit_gpx_idx"],
            "name": sector_exit_name(sec["sector"]),
            "cp_type": CoursePoint.GENERIC,
        })
        prev_exit_idx = m["exit_gpx_idx"]

    # Food stations
    for wp in gpx_waypoints:
        idx, dist = nearest_trackpoint(wp["lat"], wp["lon"], trackpoints)
        refill_idx = max(0, idx - 13)
        course_points.append({"gpx_idx": refill_idx, "name": "REFILL bidons", "cp_type": SPORTS_DRINK})
        course_points.append({"gpx_idx": idx, "name": f"RAVITO {wp['name'][:20]}", "cp_type": CoursePoint.FOOD})

    course_points.sort(key=lambda cp: cp["gpx_idx"])

    # Build course FIT with plan_ride() speed schedule
    course_fit_path = "prc26-145km-planride.fit"
    fit_file = build_fit(trackpoints, cum_dists, course_points, speed_schedule=speed_schedule)
    fit_file.to_file(course_fit_path)
    print(f"  ✓ Course FIT (VP pacing): {course_fit_path}")

    verify_fit(course_fit_path)

    print(f"\n{'='*80}")
    print(f"Done! Load {course_fit_path} on your Garmin Edge.")
    print(f"Virtual Partner paces at plan_ride() physics ({result.avg_speed_kmh:.1f} km/h avg).")
    print(f"Power Guide available in {power_guide_path}.")


if __name__ == "__main__":
    main()
