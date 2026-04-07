# Paris-Roubaix FIT Course File Generator

## Goal
Build a Python script that takes my Paris-Roubaix Challenge 2026 GPX course file and produces a Garmin FIT course file with course points for every cobblestone sector entry and exit. The FIT file will be sideloaded to a Garmin Edge 1050 via USB into `/Garmin/NewFiles/`.

## Context
- The Edge 1050 generates turn-by-turn navigation from its onboard maps (Turn Guidance), so the FIT file does NOT need navigation course points — only custom sector markers.
- Course points in the FIT file trigger "Up Ahead" alerts and populate the Course Points list screen on the device.
- The `fit-tool` Python library (`pip install fit-tool`) can create FIT course files with `CoursePointMessage`. See https://pypi.org/project/fit-tool/ for the full example of building a course from GPX.
- The `gpxpy` library parses GPX files.
- The `geopy` library calculates distances.

## Input files
- `prc26-145kmvf.gpx` — my course GPX file (already in this directory)

## Strava segment IDs for cobblestone sectors
Extract start/end GPS coordinates from these Strava segments (manually, from the segment pages while authenticated).

Segments (in riding order on the 145km course):
1. https://www.strava.com/segments/7006059
2. https://www.strava.com/segments/7008330
3. https://www.strava.com/segments/614988
4. https://www.strava.com/segments/28984000
5. https://www.strava.com/segments/28984049
6. https://www.strava.com/segments/643002
7. https://www.strava.com/segments/20573915
8. https://www.strava.com/segments/643004
9. https://www.strava.com/segments/643006
10. https://www.strava.com/segments/7009284
11. https://www.strava.com/segments/7009482
12. https://www.strava.com/segments/643035
13. https://www.strava.com/segments/11775673
14. https://www.strava.com/segments/7010133
15. https://www.strava.com/segments/7010204
16. https://www.strava.com/segments/7010241
17. https://www.strava.com/segments/1541699
18. https://www.strava.com/segments/9202428

## Course point naming convention
- Sector entry: `S{number}★{stars} {short_name}` — example: `S19★★★★★ ARNBG`
- Sector exit: `END S{number}`
- Keep names under 15 characters (Edge display limit)
- Use `CoursePoint.DANGER` (type=5) for sector entry
- Use `CoursePoint.GENERIC` (type=0) for sector exit

## Algorithm
1. Parse the GPX file to extract all trackpoints with lat/lon/elevation
2. For each Strava segment, get start and end GPS coordinates
3. For each sector coordinate, find the NEAREST trackpoint on the GPX course (haversine distance)
4. Calculate cumulative distance along the course for each trackpoint
5. Create the FIT file with:
   - FileIdMessage (type=COURSE)
   - CourseMessage (name="PRC26-145km", sport=CYCLING)
   - EventMessage (timer start)
   - All RecordMessages from GPX trackpoints (position_lat, position_long, altitude, timestamp, distance)
   - CoursePointMessage for each sector IN and OUT (with proper timestamp, position, distance, type, name)
   - EventMessage (timer stop)
   - LapMessage
6. Coordinates in FIT are in semicircles: `int(degrees * (2**31 / 180))`
7. Timestamps: use a synthetic start time (e.g., 2026-04-11T08:00:00Z) and increment based on a constant speed assumption
8. Distance field in CoursePointMessage: cumulative distance in METERS from course start

## Sector coordinates
The Paris-Roubaix sectors don't change year to year. Hardcode known start/end coordinates for each sector. The key is matching each sector's start/end to the nearest point on my specific GPX track.

## Output
- `prc26-145km-sectors.fit` — ready to copy to Garmin Edge 1050
- Print a summary table showing: sector number, name, stars, distance from start, matched GPX trackpoint index

## Testing
- After generating the FIT file, decode it back using `garmin_fit_sdk` (Decoder) to verify all course points are present and distances are increasing
- Print all decoded course points with their names, positions, and distances

## Important notes
- The FIT file must have monotonically increasing timestamps and distances
- CoursePointMessages should be interleaved with RecordMessages at the correct positions (by timestamp)
- The `fit-tool` library's `FitFileBuilder` with `auto_define=True` handles definition messages automatically
- Test with a small subset first (e.g., just 2 sectors) before doing all 18

