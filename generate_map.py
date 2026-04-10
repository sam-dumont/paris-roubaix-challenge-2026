#!/usr/bin/env python3
"""Generate an interactive HTML road book map of the PRC26 course."""

import json
import math
import os

import folium
import gpxpy

SECTORS = [
    {"sector": 19, "stars": 5, "short": "ARNBG",  "name": "Trouée d'Arenberg"},
    {"sector": 18, "stars": 3, "short": "WALLR",  "name": "Wallers à Hélesmes"},
    {"sector": 17, "stars": 4, "short": "HORNNG", "name": "Hornaing à Wandignies"},
    {"sector": 16, "stars": 3, "short": "WRLNG",  "name": "Warlaing à Brillon"},
    {"sector": 15, "stars": 4, "short": "TILOY",  "name": "Tilloy à Sars-et-Rosières"},
    {"sector": 14, "stars": 3, "short": "BVRY",   "name": "Beuvry-la-Forêt à Orchies"},
    {"sector": 13, "stars": 3, "short": "ORCHS",  "name": "Orchies"},
    {"sector": 12, "stars": 4, "short": "AUCHY",  "name": "Auchy-lez-Orchies à Bersée"},
    {"sector": 11, "stars": 5, "short": "MONS",   "name": "Mons-en-Pévèle"},
    {"sector": 10, "stars": 2, "short": "MRGNS",  "name": "Mérignies à Avelin"},
    {"sector":  9, "stars": 3, "short": "ENNVL",  "name": "Pont-Thibault à Ennevelin"},
    {"sector":  8, "stars": 2, "short": "TMPLV",  "name": "Templeuve (Moulin de Vertain)"},
    {"sector":  7, "stars": 3, "short": "CYSNG",  "name": "Cysoing à Bourghelles"},
    {"sector":  6, "stars": 3, "short": "BRGH",   "name": "Bourghelles à Wannehain"},
    {"sector":  5, "stars": 4, "short": "CMPHN",  "name": "Camphin-en-Pévèle"},
    {"sector":  4, "stars": 5, "short": "ARBRE",  "name": "Carrefour de l'Arbre"},
    {"sector":  3, "stars": 2, "short": "GRUSN",  "name": "Gruson"},
    {"sector":  2, "stars": 2, "short": "HEM",    "name": "Willems à Hem"},
    {"sector":  1, "stars": 1, "short": "RUBX",   "name": "Pavé Roubaix"},
]

SECTOR_NOTES = {
    19: "Forest trench. Ride the crown or right gutter. Gaps swallow wheels. Don't overcook entry. No braking.",
    18: "Recovery sector. Smoother tire tracks on right side. Regroup here.",
    17: "LONGEST sector (3.7km). Pace like a TT, not a sprint. Left side often smoother.",
    16: "Bumpy but rideable. Good place to drink before the next block.",
    15: "Fast entry, then rougher + uphill kicker mid-sector. Stay on crown. Shift down early.",
    14: "Straight, good sight lines. Settle into rhythm after Ravito 2.",
    13: "Urban pavé. Some turns — don't get stuck behind slower riders.",
    12: "Long, exposed, windy. Deep joints. Camber pushes to gutter — fight center-left.",
    11: "THE hardest. Sharp rise, rolling savage pavé. Stay seated on climbs for traction. All-out.",
    10: "Gift sector. Spin, drink, eat.",
    9: "Watch for potholes on entry. Straight, fast.",
    8: "Sprint through. Very short.",
    7: "Watch left-hand bend mid-sector — gravel on outside.",
    6: "Keep legs turning. Camphin is next.",
    5: "FINALE STARTS. Narrow, twisting. Sharp left catches people. Rise at end stings. Commit.",
    4: "WHERE IT'S WON. Crown is pronounced — stay on top. Final 500m roughest. Empty the tank.",
    3: "Tame after Carrefour. Coast and recover.",
    2: "Last real cobbles. Stay focused — tired legs cause crashes on easy sectors.",
    1: "300m into the Vélodrome. Soak it in.",
}

# Official PRC sector colors by difficulty (from the official table)
# 1★=yellow, 2★=light blue, 3★=orange, 4★=red, 5★=black
STAR_COLORS = {1: "#e6c619", 2: "#5bb8d4", 3: "#e67e22", 4: "#cc2200", 5: "#000000"}
GPX_FILE = "prc26-145kmvf.gpx"
PLAN_FILE = "race_plan.json"
MATCH_THRESHOLD_M = 100

# Sector start/end coordinates (same as generate_fit.py)
SECTOR_COORDS = {
    19: (50.388479, 3.423820, 50.405427, 3.406225),
    18: (50.379665, 3.387784, 50.389505, 3.372786),
    17: (50.370205, 3.326557, 50.393722, 3.315589),
    16: (50.411643, 3.321497, 50.429557, 3.325050),
    15: (50.433516, 3.316895, 50.450272, 3.325009),
    14: (50.458310, 3.274014, 50.464779, 3.258408),
    13: (50.473988, 3.223910, 50.483471, 3.228931),
    12: (50.485313, 3.186002, 50.482979, 3.155993),
    11: (50.492604, 3.131167, 50.487045, 3.103557),
    10: (50.512310, 3.104770, 50.517544, 3.101427),
     9: (50.533830, 3.109309, 50.537399, 3.125505),
     8: (50.536295, 3.176941, 50.540938, 3.179466),
     7: (50.569819, 3.222976, 50.570959, 3.235972),
     6: (50.572314, 3.241689, 50.571169, 3.250963),
     5: (50.585903, 3.271825, 50.590054, 3.254930),
     4: (50.593972, 3.249387, 50.589344, 3.229373),
     3: (50.590565, 3.228874, 50.593074, 3.214159),
     2: (50.635045, 3.215565, 50.643243, 3.205274),
     1: (50.677449, 3.199110, 50.679373, 3.201790),
}

SECTOR_POSITIONS = {
    19: (51.3, 53.6),  18: (57.5, 58.9),  17: (64.1, 67.8),
    16: (71.6, 74.0),  15: (75.0, 77.4),  14: (81.9, 83.3),
    13: (86.8, 88.6),  12: (92.9, 95.4),  11: (98.3, 101.3),
    10: (104.4, 105.0),  9: (107.7, 109.1),  8: (113.8, 114.3),
     7: (120.2, 121.1),  6: (121.5, 122.3),  5: (125.6, 127.4),
     4: (128.3, 130.3),  3: (130.5, 131.6),  2: (138.3, 139.7),
     1: (146.2, 146.2),
}

FOOD_STATIONS = [
    {"name": "Saméon", "km": 32.0},
    {"name": "Beuvry-la-Forêt", "km": 80.7},
    {"name": "Templeuve", "km": 113.5},
]


def haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_trackpoint(lat, lon, trackpoints):
    best_idx, best_dist = 0, float("inf")
    for i, tp in enumerate(trackpoints):
        d = haversine(lat, lon, tp[0], tp[1])
        if d < best_dist:
            best_idx, best_dist = i, d
    return best_idx, best_dist


def match_sector_coords(coords_tuple, trackpoints):
    """Match (start_lat, start_lon, end_lat, end_lon) to nearest GPX trackpoint indices."""
    slat, slon, elat, elon = coords_tuple
    ei, _ = nearest_trackpoint(slat, slon, trackpoints)
    xi, _ = nearest_trackpoint(elat, elon, trackpoints)
    if ei > xi:
        ei, xi = xi, ei
    return ei, xi


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    with open(GPX_FILE) as f:
        gpx = gpxpy.parse(f)
    trackpoints = [(pt.latitude, pt.longitude) for pt in gpx.tracks[0].segments[0].points]
    waypoints = [(wp.latitude, wp.longitude, wp.name) for wp in gpx.waypoints]

    # Load race plan timeline
    with open(PLAN_FILE) as f:
        plan = json.load(f)

    # Build timeline lookup by km (approximate)
    timeline_by_km = {}
    for t in plan["timeline"]:
        timeline_by_km[round(t["km"], 1)] = t

    # Map center
    lats = [tp[0] for tp in trackpoints]
    lons = [tp[1] for tp in trackpoints]
    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2

    m = folium.Map(location=[center_lat, center_lon], tiles=None, prefer_canvas=True)
    # Fit with paddingBottomRight to account for the elevation panel
    from branca.element import Element
    fit_js = Element(f"""
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            setTimeout(function() {{
                var map = Object.values(window).find(v => v instanceof L.Map);
                if (map) {{
                    map.fitBounds(
                        [[{min(lats)}, {min(lons)}], [{max(lats)}, {max(lons)}]],
                        {{paddingTopLeft: [10, 10], paddingBottomRight: [10, 130]}}
                    );
                }}
            }}, 100);
        }});
        </script>
    """)
    m.get_root().html.add_child(fit_js)

    folium.TileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attr="OSM", name="OpenStreetMap").add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Satellite").add_to(m)
    folium.TileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", attr="CartoDB", name="CartoDB Light").add_to(m)

    # Full route
    folium.PolyLine(locations=trackpoints, color="#2ecc40", weight=4, opacity=0.7, name="Course (145km)").add_to(m)

    # Sectors (match in order with monotonic constraint for loop courses)
    sector_group = folium.FeatureGroup(name="Cobblestone Sectors")
    prev_exit = 0
    for sec in SECTORS:
        snum = sec["sector"]
        if snum not in SECTOR_COORDS:
            continue
        slat, slon, elat, elon = SECTOR_COORDS[snum]
        subset = trackpoints[prev_exit:]
        ei, _ = nearest_trackpoint(slat, slon, subset)
        xi, _ = nearest_trackpoint(elat, elon, subset)
        entry_idx = ei + prev_exit
        exit_idx = xi + prev_exit
        if entry_idx > exit_idx:
            entry_idx, exit_idx = exit_idx, entry_idx
        prev_exit = exit_idx
        sector_track = trackpoints[entry_idx:exit_idx + 1]
        if len(sector_track) < 2:
            continue

        color = STAR_COLORS.get(sec["stars"], "#cc0000")
        stars_str = "★" * sec["stars"]
        snum = sec["sector"]
        note = SECTOR_NOTES.get(snum, "")

        # Find timeline entry for this sector
        time_str = ""
        nutrition_str = ""
        for t in plan["timeline"]:
            if f"S{snum} " in t.get("event", "") or f"S{snum}" == t.get("event", "").split(" ")[0]:
                time_str = t["time"]
                nutrition_str = t.get("nutrition", "")
                break

        folium.PolyLine(locations=sector_track, color=color, weight=8, opacity=0.9).add_to(sector_group)

        entry_lat, entry_lon = trackpoints[entry_idx]
        popup_html = f"""<div style="font-family: -apple-system, Arial; min-width: 220px;">
            <div style="background:{color}; color:white; padding:6px 10px; border-radius:6px 6px 0 0; font-weight:bold;">
                S{snum} {stars_str} — {sec['name']}
            </div>
            <div style="padding:8px 10px; font-size:13px; line-height:1.4;">
                <b>ETA: {time_str}</b><br>
                {f'<span style="color:#e65c00;">🥤 {nutrition_str}</span><br>' if nutrition_str else ''}
                <hr style="margin:6px 0; border:none; border-top:1px solid #ddd;">
                <i>{note}</i><br>
                Sector {snum} of the Paris-Roubaix Challenge
            </div>
        </div>"""

        folium.Marker(
            location=[entry_lat, entry_lon],
            icon=folium.DivIcon(
                html=f"""<div style="
                    background: {color}; color: white; font-weight: bold; font-size: 11px;
                    padding: 2px 6px; border-radius: 10px; white-space: nowrap;
                    border: 2px solid white; box-shadow: 0 1px 4px rgba(0,0,0,0.4);
                    font-family: -apple-system, Arial, sans-serif;
                ">S{snum} {stars_str}</div>""",
                icon_size=(None, None), icon_anchor=(0, 0),
            ),
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(sector_group)
    sector_group.add_to(m)

    # Wind impact overlay — color route by headwind/tailwind per 5km segment
    wind_group = folium.FeatureGroup(name="Wind Impact", show=False)
    wind_segments = plan.get("wind_segments", [])

    # Build proper cumulative distance for trackpoints (haversine)
    tp_cum_km = [0.0]
    for i in range(1, len(trackpoints)):
        d = haversine(trackpoints[i-1][0], trackpoints[i-1][1],
                      trackpoints[i][0], trackpoints[i][1])
        tp_cum_km.append(tp_cum_km[-1] + d / 1000)

    def km_to_idx(km):
        for i in range(1, len(tp_cum_km)):
            if tp_cum_km[i] >= km:
                return i
        return len(tp_cum_km) - 1

    for ws in wind_segments:
        km_s, km_e = ws["km_start"], ws["km_end"]
        idx_start = km_to_idx(km_s)
        idx_end = km_to_idx(km_e)

        seg_pts = trackpoints[idx_start:idx_end + 1]
        if len(seg_pts) < 2:
            continue

        hw = ws["headwind"]
        # Color: red = headwind, green = tailwind, grey = neutral
        if hw > 3:
            color = "#e74c3c"  # red headwind
            opacity = min(0.9, 0.4 + abs(hw) / 20)
        elif hw < -3:
            color = "#27ae60"  # green tailwind
            opacity = min(0.9, 0.4 + abs(hw) / 20)
        else:
            color = "#95a5a6"  # grey neutral
            opacity = 0.4

        time_diff = ws["time_full"] - ws["time_ideal"]
        popup = (f"<b>km {km_s}-{km_e}</b><br>"
                 f"Headwind: {hw:+.0f} km/h<br>"
                 f"Grade: {ws['gradient']:+.1f}%<br>"
                 f"Speed adj: {ws['wind_adj_kmh']:+.1f} km/h<br>"
                 f"Time vs ideal: {time_diff:+.1f}min")

        folium.PolyLine(
            locations=seg_pts, color=color, weight=10, opacity=opacity,
            popup=folium.Popup(popup, max_width=200),
        ).add_to(wind_group)

    # Wind direction arrows along the route every ~10km
    wind_info = plan.get("wind", {})
    if wind_info:
        wind_from_deg = wind_info.get("direction_deg", 135)
        # Arrow points WHERE wind goes (opposite of "from")
        arrow_rotation = (wind_from_deg + 180) % 360
        avg_speed = (wind_info.get("speed_kmh_morning", 12) + wind_info.get("speed_kmh_afternoon", 15)) / 2

        for km in range(10, 145, 20):
            idx = km_to_idx(km)
            lat, lon = trackpoints[idx]
            # Offset arrow perpendicular to route
            if 0 < idx < len(trackpoints) - 1:
                dlat = trackpoints[idx+1][0] - trackpoints[idx-1][0]
                dlon = trackpoints[idx+1][1] - trackpoints[idx-1][1]
                offset = 0.004
                norm = max(0.0001, (dlat**2 + dlon**2)**0.5)
                lat += -dlon / norm * offset
                lon += dlat / norm * offset

            folium.Marker(
                location=[lat, lon],
                icon=folium.DivIcon(
                    html=f"""<div style="
                        font-size: 14px;
                        color: #2980b9;
                        transform: rotate({arrow_rotation}deg);
                        width: 20px; height: 20px;
                        display: flex; align-items: center; justify-content: center;
                        background: rgba(255,255,255,0.8);
                        border-radius: 50%;
                        border: 1.5px solid #2980b9;
                    ">↑</div>""",
                    icon_size=(20, 20),
                    icon_anchor=(10, 10),
                ),
            ).add_to(wind_group)

        # Compact legend
        folium.Marker(
            location=[trackpoints[0][0] + 0.015, trackpoints[0][1] - 0.10],
            icon=folium.DivIcon(
                html=f"""<div style="
                    background:white; padding:4px 8px; border-radius:4px;
                    box-shadow:0 1px 3px rgba(0,0,0,0.2); font-size:10px;
                    font-family:-apple-system,Arial; white-space:nowrap;
                "><span style="font-size:13px;color:#2980b9;display:inline-block;transform:rotate({arrow_rotation}deg);">↑</span>
                <b>{wind_info.get('direction_label','')} {avg_speed:.0f}km/h</b>
                <span style="color:#e74c3c;">■</span>head
                <span style="color:#27ae60;">■</span>tail</div>""",
                icon_size=(None, None), icon_anchor=(0, 0),
            ),
        ).add_to(wind_group)

    wind_group.add_to(m)

    # Food stations
    food_group = folium.FeatureGroup(name="Food Stations")
    ravito_idx = 0
    for i, (wlat, wlon, wname) in enumerate(waypoints, 1):
        # Find timeline entry
        time_str = ""
        for t in plan["timeline"]:
            if "RAVITO" in t.get("event", "") and f"#{i}" not in t.get("event", ""):
                # Match by order
                pass
        # Simpler: find by km proximity
        for t in plan["timeline"]:
            if "RAVITO" in t.get("event", ""):
                ravito_idx += 1
                if ravito_idx == i:
                    time_str = t["time"]
                    break

        popup_html = f"""<div style="font-family: -apple-system, Arial; padding:8px;">
            <b>RAVITO {i} — {wname}</b><br>
            <b>ETA: {time_str}</b><br>
            ~12min stop<br>
            🥤 Refill 2x Beta Fuel bidons + Clif bar
        </div>"""
        folium.Marker(
            location=[wlat, wlon],
            icon=folium.Icon(color="green", icon="cutlery", prefix="fa"),
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(food_group)
    food_group.add_to(m)

    # Start/Finish
    folium.Marker(
        location=[trackpoints[0][0], trackpoints[0][1]],
        icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
        popup=f"<b>START / FINISH</b><br>Roubaix<br>Depart: {plan['start_time']}<br>Est. finish: {plan['finish_time']} ({plan['total_hours']}h)",
    ).add_to(m)

    # Road book panel — official PRC colors per difficulty
    # Official colors from the PRC sector table:
    #   1★: yellow  2★: light blue  3★: orange  4★: red  5★: black
    # Official PRC difficulty colors
    DIFF_COLORS = {
        1: ("#e6c619", "#000"),  # yellow
        2: ("#5bb8d4", "#fff"),  # light blue
        3: ("#e67e22", "#fff"),  # orange
        4: ("#cc2200", "#fff"),  # red
        5: ("#000000", "#fff"),  # black
    }

    roadbook_html = '<div style="font-family:-apple-system,Arial,sans-serif;font-size:12px;">'
    roadbook_html += f'<div style="background:#cc0000;color:white;padding:8px 12px;font-weight:bold;font-size:14px;">ROAD BOOK</div>'
    wind = plan.get("wind", {})
    wind_str = wind.get("summary", "") if wind else ""
    ele_str = plan.get("elevation", "")
    avg_pw = plan.get("avg_power_w", 0)
    avg_spd = plan.get("avg_speed_kmh", 0)
    if_val = plan.get("intensity_factor", 0)
    roadbook_html += f'<div style="padding:6px 12px;background:#f0f0f0;font-size:11px;line-height:1.6;">'
    roadbook_html += f'<b>{plan["start_time"]} → {plan["finish_time"]} ({plan["total_hours"]}h)</b><br>'
    roadbook_html += f'⚡ <b>{avg_pw}W</b> avg (IF {if_val}) · {avg_spd} km/h<br>'
    roadbook_html += f'{plan["nutrition"]["carbs_per_hour"]}g carbs/h · {plan["nutrition"]["fluid_liters"]}L fluid · {ele_str}<br>'
    if wind_str:
        roadbook_html += f'🌬 {wind_str}'
    roadbook_html += '</div>'

    for i, t in enumerate(plan["timeline"]):
        ev = t["event"]
        # Detect star count from event name for official coloring
        star_count = ev.count("★")
        is_sector = star_count > 0
        is_food = "RAVITO" in ev
        is_start_finish = "START" in ev or "FINISH" in ev

        if is_sector:
            bg_color, text_color = DIFF_COLORS.get(star_count, ("#fff", "#333"))
            # Use colored left border + light tinted background
            left_border = f"border-left:5px solid {bg_color};"
            bg = f"background:{'#fff8f0' if star_count <= 2 else '#fff0f0' if star_count <= 3 else '#ffe8e8' if star_count <= 4 else '#ffd0d0'};"
            ev_color = bg_color
        elif is_food:
            left_border = "border-left:5px solid #2ecc40;"
            bg = "background:#f0fff0;"
            ev_color = "#2ecc40"
        elif is_start_finish:
            left_border = "border-left:5px solid #cc0000;"
            bg = "background:#fff0f0;"
            ev_color = "#cc0000"
        else:
            left_border = ""
            bg = f"background:{'#fff' if i % 2 == 0 else '#f7f7f7'};"
            ev_color = "#333"

        roadbook_html += f'<div style="{bg}{left_border}padding:5px 10px;border-bottom:1px solid #eee;">'
        # Line 1: time + km + event name
        roadbook_html += f'<span style="color:#888;font-size:11px;font-weight:bold;margin-right:6px;">{t["time"]}</span>'
        roadbook_html += f'<span style="color:#aaa;font-size:10px;margin-right:6px;">{t["km"]:.0f}km</span>'
        roadbook_html += f'<span style="color:{ev_color};font-weight:bold;">{ev}</span>'
        # Difficulty bar for sectors (official PRC style)
        if is_sector:
            bar_bg, _ = DIFF_COLORS.get(star_count, ("#ccc", "#000"))
            bars = "".join(f'<span style="display:inline-block;width:8px;height:12px;background:{bar_bg};margin-right:1px;border-radius:1px;"></span>' for _ in range(star_count))
            roadbook_html += f' <span style="margin-left:4px;">{bars}</span>'
        # Line 2: note (with power highlighted)
        if t["note"]:
            note = t["note"]
            # Highlight the power value
            if "⚡" in note:
                note = note.replace("⚡", '<span style="color:#e63900;font-weight:bold;">⚡</span>')
            roadbook_html += f'<br><span style="font-size:10px;color:#666;">{note}</span>'
        # Line 3: nutrition
        if t.get("nutrition"):
            roadbook_html += f'<br><span style="font-size:10px;color:#e65c00;">🥤 {t["nutrition"]}</span>'
        roadbook_html += '</div>'

    # Collapsible generation info
    roadbook_html += '<details style="padding:8px 12px;background:#f0f0f0;font-size:10px;color:#888;">'
    roadbook_html += '<summary style="cursor:pointer;font-weight:bold;">How this was generated</summary>'
    roadbook_html += '<div style="margin-top:6px;line-height:1.5;">'
    roadbook_html += 'Physics model: <b>bike-power-model</b> plan_ride()<br>'
    roadbook_html += 'FTP=287W · CdA=0.53 · Crr=0.007 · Mass=114kg<br>'
    roadbook_html += 'Surface-aware optimizer (cobble Crr penalties)<br>'
    roadbook_html += f'Weather: Open-Meteo forecast (SSW {wind.get("speed_kmh_morning",20)}→{wind.get("speed_kmh_afternoon",22)}km/h)<br>'
    roadbook_html += 'Fatigue model: endurance (onset 1.5h)<br>'
    roadbook_html += f'Model validated on 112 rides (7.9% MAE)<br>'
    roadbook_html += '</div></details>'

    roadbook_html += '</div>'

    # Add as a floating panel
    from branca.element import MacroElement, Template
    panel = MacroElement()
    panel._template = Template(f"""
        {{% macro header(this, kwargs) %}}
        <style>
            .roadbook-panel {{
                position: fixed;
                top: 80px;
                left: 10px;
                z-index: 1000;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 12px rgba(0,0,0,0.3);
                max-height: 85vh;
                overflow-y: auto;
                width: 340px;
                display: none;
            }}
            .roadbook-toggle {{
                position: fixed;
                top: 80px;
                left: 10px;
                z-index: 1001;
                background: #cc0000;
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 6px;
                font-weight: bold;
                cursor: pointer;
                font-family: -apple-system, Arial;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                font-size: 13px;
            }}
            .roadbook-toggle:hover {{ background: #a00; }}
            .roadbook-close {{
                position: sticky;
                top: 0;
                background: #cc0000;
                text-align: right;
                padding: 2px 8px;
                z-index: 10;
            }}
            .roadbook-close button {{
                background: none;
                border: none;
                color: white;
                font-size: 20px;
                cursor: pointer;
                padding: 4px 8px;
            }}
        </style>
        {{% endmacro %}}
        {{% macro html(this, kwargs) %}}
        <button class="roadbook-toggle" id="rb-btn" onclick="
            document.getElementById('roadbook').style.display='block';
            this.style.display='none';
        ">📋 Road Book</button>
        <div id="roadbook" class="roadbook-panel">
            <div class="roadbook-close">
                <button onclick="
                    document.getElementById('roadbook').style.display='none';
                    document.getElementById('rb-btn').style.display='block';
                ">✕</button>
            </div>
            {roadbook_html}
        </div>
        {{% endmacro %}}
    """)
    m.get_root().add_child(panel)

    # ─── Elevation + Wind Profile (fixed bottom panel) ───
    # Sample elevation every 0.5km
    ele_samples = []
    sample_interval = 0.5
    next_km = 0
    for i in range(len(tp_cum_km)):
        if tp_cum_km[i] >= next_km:
            ele = gpx.tracks[0].segments[0].points[i].elevation or 0
            ele_samples.append((tp_cum_km[i], ele))
            next_km += sample_interval

    total_dist = tp_cum_km[-1]
    min_ele = min(e[1] for e in ele_samples) - 5
    max_ele = max(e[1] for e in ele_samples) + 10
    ele_range = max_ele - min_ele

    # SVG dimensions — wide and short
    svg_w = 1600
    svg_h = 132
    margin_l = 30
    margin_r = 10
    margin_t = 8
    margin_b = 36
    plot_w = svg_w - margin_l - margin_r
    plot_h = svg_h - margin_t - margin_b

    def km_to_x(km):
        return margin_l + (km / total_dist) * plot_w

    def ele_to_y(ele):
        return margin_t + plot_h - ((ele - min_ele) / ele_range) * plot_h

    # Build elevation path
    ele_points = " ".join(f"{km_to_x(km):.1f},{ele_to_y(ele):.1f}" for km, ele in ele_samples)
    ele_fill = f"{km_to_x(ele_samples[0][0]):.1f},{margin_t + plot_h} {ele_points} {km_to_x(ele_samples[-1][0]):.1f},{margin_t + plot_h}"

    svg = f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg" style="font-family:-apple-system,Arial,sans-serif;">'

    # Background
    svg += f'<rect x="0" y="0" width="{svg_w}" height="{svg_h}" fill="white" />'

    # Wind effect bars (behind elevation)
    wind_segs = plan.get("wind_segments", [])
    for ws in wind_segs:
        x1 = km_to_x(ws["km_start"])
        x2 = km_to_x(ws["km_end"])
        hw = ws["headwind"]
        if hw > 2:
            color = f"rgba(231,76,60,{min(0.35, abs(hw)/30):.2f})"
        elif hw < -2:
            color = f"rgba(39,174,96,{min(0.35, abs(hw)/30):.2f})"
        else:
            continue
        svg += f'<rect x="{x1:.0f}" y="{margin_t}" width="{x2-x1:.0f}" height="{plot_h}" fill="{color}" />'

    # Elevation fill
    svg += f'<polygon points="{ele_fill}" fill="#e8dcc8" stroke="none" opacity="0.8" />'
    svg += f'<polyline points="{ele_points}" fill="none" stroke="#8B7355" stroke-width="1.5" />'

    # Sector bands
    for sec in SECTORS:
        entry_km, exit_km = SECTOR_POSITIONS[sec["sector"]]
        x1 = km_to_x(entry_km)
        x2 = km_to_x(exit_km)
        color = STAR_COLORS.get(sec["stars"], "#888")
        # Draw sector as a thick bar at the bottom of the elevation area
        svg += f'<rect x="{x1:.0f}" y="{margin_t + plot_h - 8}" width="{max(3, x2-x1):.0f}" height="8" fill="{color}" rx="1" />'
        # Sector label (only for 4★ and 5★ to avoid clutter)
        if sec["stars"] >= 4:
            mid_x = (x1 + x2) / 2
            svg += f'<text x="{mid_x:.0f}" y="{margin_t + plot_h - 12}" font-size="8" fill="{color}" text-anchor="middle" font-weight="bold">S{sec["sector"]}</text>'

    # Food stations
    for fs in FOOD_STATIONS:
        x = km_to_x(fs["km"])
        svg += f'<line x1="{x:.0f}" y1="{margin_t}" x2="{x:.0f}" y2="{margin_t + plot_h}" stroke="#27ae60" stroke-width="1" stroke-dasharray="3 2" />'
        svg += f'<text x="{x:.0f}" y="{margin_t + 10}" font-size="8" fill="#27ae60" text-anchor="middle">R</text>'

    # Y-axis labels
    for ele in range(int(min_ele / 10) * 10, int(max_ele) + 10, 20):
        if ele < min_ele or ele > max_ele:
            continue
        y = ele_to_y(ele)
        svg += f'<text x="{margin_l - 3}" y="{y + 3:.0f}" font-size="9" fill="#888" text-anchor="end">{ele:.0f}m</text>'
        svg += f'<line x1="{margin_l}" y1="{y:.0f}" x2="{margin_l + plot_w}" y2="{y:.0f}" stroke="#eee" stroke-width="0.5" />'

    # X-axis labels
    for km in range(0, int(total_dist) + 1, 10):
        x = km_to_x(km)
        svg += f'<text x="{x:.0f}" y="{margin_t + plot_h + 15}" font-size="9" fill="#888" text-anchor="middle">{km}</text>'

    # Wind legend
    svg += f'<rect x="{margin_l}" y="{margin_t + plot_h + 20}" width="10" height="6" fill="rgba(231,76,60,0.3)" />'
    svg += f'<text x="{margin_l + 13}" y="{margin_t + plot_h + 26}" font-size="8" fill="#888">headwind</text>'
    svg += f'<rect x="{margin_l + 70}" y="{margin_t + plot_h + 20}" width="10" height="6" fill="rgba(39,174,96,0.3)" />'
    svg += f'<text x="{margin_l + 83}" y="{margin_t + plot_h + 26}" font-size="8" fill="#888">tailwind</text>'

    # Sector legend (official PRC colors)
    svg += f'<rect x="{margin_l + 145}" y="{margin_t + plot_h + 20}" width="10" height="6" fill="#000000" />'
    svg += f'<text x="{margin_l + 158}" y="{margin_t + plot_h + 26}" font-size="8" fill="#888">5★</text>'
    svg += f'<rect x="{margin_l + 175}" y="{margin_t + plot_h + 20}" width="10" height="6" fill="#cc2200" />'
    svg += f'<text x="{margin_l + 188}" y="{margin_t + plot_h + 26}" font-size="8" fill="#888">4★</text>'
    svg += f'<rect x="{margin_l + 205}" y="{margin_t + plot_h + 20}" width="10" height="6" fill="#e67e22" />'
    svg += f'<text x="{margin_l + 218}" y="{margin_t + plot_h + 26}" font-size="8" fill="#888">3★</text>'
    svg += f'<rect x="{margin_l + 235}" y="{margin_t + plot_h + 20}" width="10" height="6" fill="#5bb8d4" />'
    svg += f'<text x="{margin_l + 248}" y="{margin_t + plot_h + 26}" font-size="8" fill="#888">2★</text>'
    svg += f'<rect x="{margin_l + 265}" y="{margin_t + plot_h + 20}" width="10" height="6" fill="#e6c619" />'
    svg += f'<text x="{margin_l + 278}" y="{margin_t + plot_h + 26}" font-size="8" fill="#888">1★</text>'

    # Title
    wind_summary = plan.get("wind", {}).get("summary", "")
    svg += f'<text x="{svg_w - margin_r}" y="{margin_t + 10}" font-size="10" fill="#888" text-anchor="end">+{int(max_ele - min_ele)}m elev | {wind_summary}</text>'

    svg += '</svg>'

    # Add as fixed bottom panel
    ele_panel = MacroElement()
    ele_panel._template = Template(f"""
        {{% macro header(this, kwargs) %}}
        <style>
            .elevation-panel {{
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                z-index: 999;
                background: white;
                border-top: 1px solid #ccc;
                box-shadow: 0 -2px 6px rgba(0,0,0,0.1);
                padding: 0;
                height: 120px;
                overflow-x: auto;
                overflow-y: hidden;
                -webkit-overflow-scrolling: touch;
            }}
            .elevation-panel svg {{
                display: block;
            }}
            @media (max-width: 768px) {{
                .roadbook-panel {{ width: 85vw; max-width: 340px; }}
            }}
        </style>
        {{% endmacro %}}
        {{% macro html(this, kwargs) %}}
        <div class="elevation-panel">
            {svg}
        </div>
        {{% endmacro %}}
    """)
    m.get_root().add_child(ele_panel)

    folium.LayerControl(collapsed=False).add_to(m)

    out_path = "prc26_course_map.html"
    m.save(out_path)
    print(f"✓ Map saved to {out_path}")
    print(f"  Open: file://{os.path.abspath(out_path)}")
    print(f"  Size: {os.path.getsize(out_path) / 1024:.0f}KB")
    print(f"\n  To share: push to GitHub Pages, or use 'npx surge {out_path}'")


if __name__ == "__main__":
    main()
