#!/usr/bin/env python3
"""Paris-Roubaix Challenge 2026 — FIT Course File Generator.

Reads the official PRC26 145km GPX course and produces a Garmin FIT course file
with course points for every cobblestone sector entry/exit and food station.
"""

import math
import os
from datetime import datetime, timezone

import gpxpy

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.course_message import CourseMessage
from fit_tool.profile.messages.course_point_message import CoursePointMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.profile_type import (
    CoursePoint,
    Event,
    EventType,
    FileType,
    Manufacturer,
    Sport,
)

# ---------------------------------------------------------------------------
# Sector metadata — 19 sectors on the PRC26 145 km challenge route
# Coordinates: (start_lat, start_lon, end_lat, end_lon)
# Manually extracted from Strava segment pages while authenticated.
# These sectors don't change year to year.
# ---------------------------------------------------------------------------
SECTORS = [
    {"sector": 19, "stars": 5, "short": "ARNBG",  "name": "Trouée d'Arenberg",          "coords": (50.388479, 3.423820, 50.405427, 3.406225)},
    {"sector": 18, "stars": 3, "short": "WALLR",  "name": "Wallers à Hélesmes",          "coords": (50.379665, 3.387784, 50.389505, 3.372786)},
    {"sector": 17, "stars": 4, "short": "HORNNG", "name": "Hornaing à Wandignies",       "coords": (50.370205, 3.326557, 50.393722, 3.315589)},
    {"sector": 16, "stars": 3, "short": "WRLNG",  "name": "Warlaing à Brillon",          "coords": (50.411643, 3.321497, 50.429557, 3.325050)},
    {"sector": 15, "stars": 4, "short": "TILOY",  "name": "Tilloy à Sars-et-Rosières",   "coords": (50.433516, 3.316895, 50.450272, 3.325009)},
    {"sector": 14, "stars": 3, "short": "BVRY",   "name": "Beuvry-la-Forêt à Orchies",   "coords": (50.458310, 3.274014, 50.464779, 3.258408)},
    {"sector": 13, "stars": 3, "short": "ORCHS",  "name": "Orchies",                     "coords": (50.473988, 3.223910, 50.483471, 3.228931)},
    {"sector": 12, "stars": 4, "short": "AUCHY",  "name": "Auchy-lez-Orchies à Bersée",  "coords": (50.485313, 3.186002, 50.482979, 3.155993)},
    {"sector": 11, "stars": 5, "short": "MONS",   "name": "Mons-en-Pévèle",             "coords": (50.492604, 3.131167, 50.487045, 3.103557)},
    {"sector": 10, "stars": 2, "short": "MRGNS",  "name": "Mérignies à Avelin",          "coords": (50.512310, 3.104770, 50.517544, 3.101427)},
    {"sector":  9, "stars": 3, "short": "ENNVL",  "name": "Pont-Thibault à Ennevelin",   "coords": (50.533830, 3.109309, 50.537399, 3.125505)},
    {"sector":  8, "stars": 2, "short": "TMPLV",  "name": "Templeuve (Moulin de Vertain)","coords": (50.536295, 3.176941, 50.540938, 3.179466)},
    {"sector":  7, "stars": 3, "short": "CYSNG",  "name": "Cysoing à Bourghelles",       "coords": (50.569819, 3.222976, 50.570959, 3.235972)},
    {"sector":  6, "stars": 3, "short": "BRGH",   "name": "Bourghelles à Wannehain",     "coords": (50.572314, 3.241689, 50.571169, 3.250963)},
    {"sector":  5, "stars": 4, "short": "CMPHN",  "name": "Camphin-en-Pévèle",           "coords": (50.585903, 3.271825, 50.590054, 3.254930)},
    {"sector":  4, "stars": 5, "short": "ARBRE",  "name": "Carrefour de l'Arbre",        "coords": (50.593972, 3.249387, 50.589344, 3.229373)},
    {"sector":  3, "stars": 2, "short": "GRUSN",  "name": "Gruson",                      "coords": (50.590565, 3.228874, 50.593074, 3.214159)},
    {"sector":  2, "stars": 2, "short": "HEM",    "name": "Willems à Hem",               "coords": (50.635045, 3.215565, 50.643243, 3.205274)},
    {"sector":  1, "stars": 1, "short": "RUBX",   "name": "Pavé Roubaix",                "coords": (50.677449, 3.199110, 50.679373, 3.201790)},
]

GPX_FILE = "prc26-145kmvf.gpx"
FIT_FILE = "prc26-145km-sectors.fit"
MATCH_THRESHOLD_M = 200  # max distance for sector endpoint matching

# FIT course point types not in fit_tool's enum (Profile 21.60)
# but supported by modern Garmin devices (Profile 21.89+)
ENERGY_GEL = 32    # gel icon in "Up Ahead"
SPORTS_DRINK = 33  # drink icon in "Up Ahead"

# Nutrition plan: gels before 5-star sectors, Clif + bidon refill at ravitos
GEL_SECTORS = {19: "GEL pre-ARNBG", 11: "GEL pre-MONS", 4: "GEL pre-ARBRE"}  # max distance in meters for a "good" match


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Return distance in meters between two GPS coordinates."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))



# ---------------------------------------------------------------------------
# GPX parsing
# ---------------------------------------------------------------------------
def parse_gpx(path):
    with open(path) as f:
        gpx = gpxpy.parse(f)

    trackpoints = []
    for pt in gpx.tracks[0].segments[0].points:
        trackpoints.append({
            "lat": pt.latitude,
            "lon": pt.longitude,
            "ele": pt.elevation or 0.0,
            "time": pt.time,
        })

    waypoints = []
    for wp in gpx.waypoints:
        waypoints.append({
            "lat": wp.latitude,
            "lon": wp.longitude,
            "name": wp.name or "Waypoint",
        })

    return trackpoints, waypoints


# ---------------------------------------------------------------------------
# Cumulative distance along GPX
# ---------------------------------------------------------------------------
def compute_cumulative_distances(trackpoints):
    dists = [0.0]
    for i in range(1, len(trackpoints)):
        d = haversine(
            trackpoints[i - 1]["lat"], trackpoints[i - 1]["lon"],
            trackpoints[i]["lat"], trackpoints[i]["lon"],
        )
        dists.append(dists[-1] + d)
    return dists


# ---------------------------------------------------------------------------
# Find nearest GPX trackpoint to a given coordinate
# ---------------------------------------------------------------------------
def nearest_trackpoint(lat, lon, trackpoints):
    """Return (index, distance_m) of the nearest trackpoint."""
    best_idx, best_dist = 0, float("inf")
    for i, tp in enumerate(trackpoints):
        d = haversine(lat, lon, tp["lat"], tp["lon"])
        if d < best_dist:
            best_idx, best_dist = i, d
    return best_idx, best_dist


# ---------------------------------------------------------------------------
# Match sector start/end coordinates to nearest GPX trackpoints
# ---------------------------------------------------------------------------
def match_sector(coords_tuple, trackpoints, min_idx=0):
    """Find entry and exit GPX indices from (start_lat, start_lon, end_lat, end_lon).

    min_idx: only search trackpoints at or after this index (ensures monotonic ordering
    on loop courses where start/finish overlap).
    """
    slat, slon, elat, elon = coords_tuple
    # Search only from min_idx onward
    subset = trackpoints[min_idx:]
    ei, ed = nearest_trackpoint(slat, slon, subset)
    xi, xd = nearest_trackpoint(elat, elon, subset)
    ei += min_idx
    xi += min_idx
    return {
        "entry_gpx_idx": ei,
        "entry_dist_m": ed,
        "exit_gpx_idx": xi,
        "exit_dist_m": xd,
    }


# ---------------------------------------------------------------------------
# Build sector course-point name
# ---------------------------------------------------------------------------
def sector_entry_name(sector_num, stars, short_name):
    # Format: {sector}-{N}*-{ABBR}  e.g. "19-5*-ARNBG", "6-3*-BRGH"
    # All ASCII to avoid UTF-8 multi-byte truncation on Garmin display
    return f"{sector_num}-{stars}*-{short_name}"


def sector_exit_name(sector_num):
    return f"END S{sector_num}"


# ---------------------------------------------------------------------------
# Build the FIT file
# ---------------------------------------------------------------------------
def build_fit(trackpoints, cum_dists, course_points_data, speed_schedule=None):
    """
    course_points_data: list of dicts with keys:
        gpx_idx, name, cp_type (CoursePoint enum)
    sorted by gpx_idx.

    speed_schedule: optional list of (from_km, to_km, speed_kmh) tuples.
        If provided, timestamps are computed from the schedule so the
        Virtual Partner paces to the race plan. If None, uses GPX timestamps.
    """
    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    # --- FileIdMessage ---
    file_id = FileIdMessage()
    file_id.type = FileType.COURSE
    file_id.manufacturer = Manufacturer.DEVELOPMENT.value
    file_id.product = 0
    file_id.serial_number = 0x12345678
    file_id.time_created = round(datetime.now(timezone.utc).timestamp() * 1000)
    builder.add(file_id)

    # --- CourseMessage with capabilities ---
    course = CourseMessage()
    course.course_name = "PRC26-145km"
    course.sport = Sport.CYCLING
    # PROCESSED=1 | VALID=2 | TIME=4 | DISTANCE=8 | POSITION=16 = 31
    # TIME flag is required for Virtual Partner ahead/behind on Edge
    course.capabilities = 31
    builder.add(course)

    # --- Compute timestamps ---
    # Use race plan speed schedule for Virtual Partner pacing,
    # or fall back to GPX timestamps
    if speed_schedule:
        # Build a speed lookup: for each km, what's the target speed
        def speed_at_km(km):
            for from_km, to_km, spd in speed_schedule:
                if from_km <= km < to_km:
                    return spd
            return speed_schedule[-1][2]  # last segment speed

        # Start time: race day 8:00 AM
        start_ts = round(datetime(2026, 4, 11, 8, 0, 0).timestamp() * 1000)
        timestamps_ms = [start_ts]
        for i in range(1, len(trackpoints)):
            km = cum_dists[i] / 1000
            delta_m = cum_dists[i] - cum_dists[i - 1]
            spd_ms = speed_at_km(km) / 3.6  # km/h to m/s
            delta_s = delta_m / max(0.1, spd_ms)
            timestamps_ms.append(timestamps_ms[-1] + round(delta_s * 1000))
    else:
        timestamps_ms = []
        for i in range(len(trackpoints)):
            t = trackpoints[i]["time"]
            timestamps_ms.append(round(t.timestamp() * 1000))

    start_ts = timestamps_ms[0]
    end_ts = timestamps_ms[-1]

    # --- Event: timer start ---
    ev_start = EventMessage()
    ev_start.event = Event.TIMER
    ev_start.event_type = EventType.START
    ev_start.timestamp = start_ts
    builder.add(ev_start)

    # --- RecordMessages (all trackpoints) ---
    records = []
    for i, tp in enumerate(trackpoints):
        rec = RecordMessage()
        rec.position_lat = tp["lat"]
        rec.position_long = tp["lon"]
        rec.altitude = tp["ele"]
        rec.distance = cum_dists[i]
        rec.timestamp = timestamps_ms[i]
        records.append(rec)
    builder.add_all(records)

    # --- CoursePointMessages ---
    for cp in course_points_data:
        idx = cp["gpx_idx"]
        msg = CoursePointMessage()
        msg.timestamp = timestamps_ms[idx]
        msg.position_lat = trackpoints[idx]["lat"]
        msg.position_long = trackpoints[idx]["lon"]
        msg.distance = cum_dists[idx]
        msg.type = cp["cp_type"]
        msg.course_point_name = cp["name"]
        builder.add(msg)

    # --- Event: timer stop ---
    ev_stop = EventMessage()
    ev_stop.event = Event.TIMER
    ev_stop.event_type = EventType.STOP_ALL
    ev_stop.timestamp = end_ts
    builder.add(ev_stop)

    # --- LapMessage ---
    elapsed_s = (end_ts - start_ts) / 1000.0
    lap = LapMessage()
    lap.timestamp = end_ts
    lap.start_time = start_ts
    lap.total_elapsed_time = elapsed_s
    lap.total_timer_time = elapsed_s
    lap.start_position_lat = trackpoints[0]["lat"]
    lap.start_position_long = trackpoints[0]["lon"]
    lap.end_position_lat = trackpoints[-1]["lat"]
    lap.end_position_long = trackpoints[-1]["lon"]
    lap.total_distance = cum_dists[-1]
    builder.add(lap)

    return builder.build()


# ---------------------------------------------------------------------------
# Verify with garmin_fit_sdk
# ---------------------------------------------------------------------------
def verify_fit(path):
    try:
        from garmin_fit_sdk import Decoder, Stream
    except ImportError:
        print("\n⚠  garmin_fit_sdk not installed — skipping verification")
        return

    stream = Stream.from_file(path)
    decoder = Decoder(stream)
    messages, errors = decoder.read()

    if errors:
        print(f"\n✗ Decode errors: {errors}")
        return

    print(f"\n{'─' * 70}")
    print("FIT VERIFICATION — Decoded course points:")
    print(f"{'─' * 70}")
    print(f"{'Type':<8} {'Name':<20} {'Dist (km)':>10} {'Lat':>12} {'Lon':>12}")
    print(f"{'─' * 70}")

    prev_dist = -1
    ok = True
    count = 0
    for msg in messages.get("course_point_mesgs", []):
        name = msg.get("name", "?")
        dist = msg.get("distance", 0)
        lat = msg.get("position_lat", 0)
        lon = msg.get("position_long", 0)
        cp_type = msg.get("type", "?")

        dist_km = dist / 1000 if dist else 0
        print(f"{str(cp_type):<8} {name:<20} {dist_km:>10.2f} {lat:>12.6f} {lon:>12.6f}")

        if dist is not None and dist < prev_dist:
            print(f"  ⚠  Distance decreased! {prev_dist:.0f} → {dist:.0f}")
            ok = False
        prev_dist = dist or prev_dist
        count += 1

    print(f"{'─' * 70}")
    print(f"Total course points: {count}")
    n_records = len(messages.get("record_mesgs", []))
    print(f"Total record messages: {n_records}")
    if ok:
        print("✓ Distances are monotonically increasing")
    else:
        print("✗ Distance ordering issue detected")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # 1. Parse GPX
    print("Parsing GPX...")
    trackpoints, waypoints = parse_gpx(GPX_FILE)
    print(f"  {len(trackpoints)} trackpoints, {len(waypoints)} waypoints")

    # 2. Cumulative distances
    print("Computing cumulative distances...")
    cum_dists = compute_cumulative_distances(trackpoints)
    print(f"  Total distance: {cum_dists[-1] / 1000:.2f} km")

    # 3. Match sectors to GPX
    print("\nMatching sectors to GPX track...")
    print(f"{'S#':>3} {'Name':<30} {'Entry km':>9} {'Exit km':>9} {'Δ entry':>8} {'Δ exit':>8} {'Note'}")
    print("─" * 100)

    course_points = []
    prev_exit_idx = 0  # enforce monotonic ordering on loop courses
    for sec in SECTORS:
        m = match_sector(sec["coords"], trackpoints, min_idx=prev_exit_idx)
        entry_km = cum_dists[m["entry_gpx_idx"]] / 1000
        exit_km = cum_dists[m["exit_gpx_idx"]] / 1000
        note = ""
        if m["entry_dist_m"] > 200 or m["exit_dist_m"] > 200:
            note += " ⚠ FAR"

        # Ensure entry comes before exit on the course
        if m["entry_gpx_idx"] > m["exit_gpx_idx"]:
            m["entry_gpx_idx"], m["exit_gpx_idx"] = m["exit_gpx_idx"], m["entry_gpx_idx"]
            m["entry_dist_m"], m["exit_dist_m"] = m["exit_dist_m"], m["entry_dist_m"]
            note += " (reversed)"
            entry_km = cum_dists[m["entry_gpx_idx"]] / 1000
            exit_km = cum_dists[m["exit_gpx_idx"]] / 1000

        print(
            f"S{sec['sector']:>2} {sec['name']:<30} {entry_km:>8.2f}k {exit_km:>8.2f}k "
            f"{m['entry_dist_m']:>7.0f}m {m['exit_dist_m']:>7.0f}m  {note}"
        )

        # Gel reminder ~500m before 5-star sector entries
        if sec["sector"] in GEL_SECTORS:
            gel_idx = max(0, m["entry_gpx_idx"] - 6)  # ~500m back (~80m per trackpoint)
            gel_km = cum_dists[gel_idx] / 1000
            print(f"  {'':>2} + GEL at {gel_km:.2f}k ({GEL_SECTORS[sec['sector']]})")
            course_points.append({
                "gpx_idx": gel_idx,
                "name": GEL_SECTORS[sec["sector"]],
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

    # 5. Food stations from GPX waypoints + nutrition reminders
    print(f"\n{'─' * 70}")
    print("Food stations + nutrition reminders:")
    for i, wp in enumerate(waypoints, 1):
        idx, dist = nearest_trackpoint(wp["lat"], wp["lon"], trackpoints)
        km = cum_dists[idx] / 1000

        # Bidon refill reminder ~1km before ravito
        refill_idx = max(0, idx - 13)  # ~1km back
        refill_km = cum_dists[refill_idx] / 1000
        print(f"  {refill_km:.1f}k  REFILL bidons")
        course_points.append({
            "gpx_idx": refill_idx,
            "name": f"REFILL bidons",
            "cp_type": SPORTS_DRINK,
        })

        # Food station marker
        print(f"  {km:.1f}k  RAVITO {i}: {wp['name']} (match: {dist:.0f}m)")
        course_points.append({
            "gpx_idx": idx,
            "name": f"RAVITO {i}",
            "cp_type": CoursePoint.FOOD,
        })

        # Clif bar reminder at the station
        course_points.append({
            "gpx_idx": idx,
            "name": f"CLIF #{i}",
            "cp_type": ENERGY_GEL,
        })

    # Sort all course points by position on course
    course_points.sort(key=lambda cp: cp["gpx_idx"])

    print(f"\nTotal course points: {len(course_points)}")

    # 6. Build speed schedule for Virtual Partner pacing
    # Uses the same speed model as race_plan.py: road=22 km/h, cobbles by difficulty,
    # fatigue after km 100, food station stops modeled as very slow sections
    ROAD_SPEED = 22.0
    COBBLE_SPEED = {5: 18.0, 4: 19.5, 3: 21.0, 2: 22.0, 1: 23.0}
    FATIGUE_KM = 100
    FATIGUE_FACTOR = 0.93
    FOOD_STOP_SPEED = 2.0  # ~walking pace to model the stop time in timestamps

    # Build sector lookup: km ranges for each sector
    sector_ranges = {}
    for sec in SECTORS:
        for cp in course_points:
            if cp["name"] == sector_entry_name(sec["sector"], sec["stars"], sec["short"]):
                entry_km = cum_dists[cp["gpx_idx"]] / 1000
            if cp["name"] == sector_exit_name(sec["sector"]):
                exit_km = cum_dists[cp["gpx_idx"]] / 1000
                sector_ranges[sec["sector"]] = (entry_km, exit_km, sec["stars"])

    # Food station km positions (approximate)
    food_kms = []
    for wp in waypoints:
        idx, _ = nearest_trackpoint(wp["lat"], wp["lon"], trackpoints)
        food_kms.append(cum_dists[idx] / 1000)

    # Build schedule: list of (from_km, to_km, speed_kmh)
    speed_schedule = []
    total_km = cum_dists[-1] / 1000
    km = 0.0
    step = 0.5  # 500m granularity

    while km < total_km:
        km_end = min(km + step, total_km)
        km_mid = (km + km_end) / 2

        # Check if we're in a food station zone (~200m around station)
        in_food = any(abs(km_mid - fk) < 0.2 for fk in food_kms)

        # Check if we're on cobbles
        in_sector = None
        for snum, (s_entry, s_exit, stars) in sector_ranges.items():
            if s_entry <= km_mid <= s_exit:
                in_sector = stars
                break

        if in_food:
            spd = FOOD_STOP_SPEED
        elif in_sector:
            spd = COBBLE_SPEED[in_sector]
        else:
            spd = ROAD_SPEED

        if km_mid >= FATIGUE_KM and not in_food:
            spd *= FATIGUE_FACTOR

        speed_schedule.append((km, km_end, spd))
        km = km_end

    vp_total_s = sum((to_km - from_km) * 1000 / (spd / 3.6) for from_km, to_km, spd in speed_schedule)
    print(f"\nVirtual Partner schedule: {len(speed_schedule)} segments, {vp_total_s/3600:.1f}h total")

    # 7. Build FIT file
    print(f"Building FIT file...")
    fit_file = build_fit(trackpoints, cum_dists, course_points, speed_schedule=speed_schedule)
    fit_file.to_file(FIT_FILE)
    print(f"✓ Written to {FIT_FILE}")

    # 7. Verify
    verify_fit(FIT_FILE)


if __name__ == "__main__":
    main()
