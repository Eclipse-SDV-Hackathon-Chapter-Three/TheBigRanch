#!/usr/bin/env python3
import json
import time
import sqlite3
import streamlit as st
import pydeck as pdk
import zenoh
from streamlit_autorefresh import st_autorefresh

DB_PATH = "adas.db"

# Same anchor & scale as the ADAS node
ANCHOR_LAT = 38.711046
ANCHOR_LON = -9.138637
METERS_TO_DEGREES = 1e-5

# -----------------
# DB Setup
# -----------------
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")

    cur.execute("""CREATE TABLE IF NOT EXISTS pose (
        ts REAL, lat REAL, lon REAL, yaw REAL, speed_mps REAL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS imu (
        ts REAL, ax REAL, ay REAL, az REAL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS potholes (
        ts REAL, lat REAL, lon REAL, severity TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS alerts (
        ts REAL, level TEXT, title TEXT, msg TEXT
    )""")

    # Clear once per Streamlit session (handy in dev)
    if "db_cleared" not in st.session_state:
        for table in ["pose", "imu", "potholes", "alerts"]:
            cur.execute(f"DELETE FROM {table}")
        conn.commit()
        st.session_state["db_cleared"] = True

    return conn

conn = init_db()

# -----------------
# Helpers
# -----------------
def safe_json_decode(payload):
    try:
        obj = json.loads(payload.to_string())
        if isinstance(obj, str):
            obj = json.loads(obj)
        return obj
    except Exception as e:
        return {"ERROR": {"message": str(e)}}

def init_zenoh():
    if "zenoh_inited" in st.session_state:
        return
    st.session_state["zenoh_inited"] = True

    def pose_cb(sample):
        msg = safe_json_decode(sample.payload)
        if "ERROR" in msg:
            return

        lat = msg.get("lat")
        lon = msg.get("lon")

        if lat is None or lon is None:
            # fallback to convert x/y from CARLA world coords
            x_m = float(msg.get("x", 0.0))
            y_m = float(msg.get("y", 0.0))

            base_lat, base_lon = 38.711046, -9.138637
            M_PER_DEG_LAT = 1.0 / 111111.0
            M_PER_DEG_LON = 1.0 / 88000.0

            lat = base_lat + y_m * M_PER_DEG_LAT
            lon = base_lon + x_m * M_PER_DEG_LON

        # ensure numeric
        lat = float(lat)
        lon = float(lon)

        c = sqlite3.connect(DB_PATH)
        c.execute(
            "INSERT INTO pose (ts, lat, lon, yaw, speed_mps) VALUES (?, ?, ?, ?, ?)",
            (
                float(msg.get("ts", time.time())),
                lat,
                lon,
                float(msg.get("yaw", 0.0)),
                float(msg.get("speed_mps", 0.0)),
            ),
        )
        c.commit()
        c.close()


    def imu_cb(sample):
        msg = safe_json_decode(sample.payload)
        if "ERROR" in msg:
            return
        acc = msg.get("acc", {})
        c = sqlite3.connect(DB_PATH)
        c.execute(
            "INSERT INTO imu (ts, ax, ay, az) VALUES (?, ?, ?, ?)",
            (
                float(msg.get("ts", time.time())),
                float(acc.get("x", 0.0)),
                float(acc.get("y", 0.0)),
                float(acc.get("z", 0.0)),
            ),
        )
        c.commit()
        c.close()

    def pothole_cb(sample):
        msg = safe_json_decode(sample.payload)
        if "ERROR" in msg:
            return

        # potholes from ADAS are already in lat/lon → trust directly
        if "lat" not in msg or "lon" not in msg:
            return  # skip invalid pothole messages

        c = sqlite3.connect(DB_PATH)
        c.execute(
            "INSERT INTO potholes (ts, lat, lon, severity) VALUES (?, ?, ?, ?)",
            (
                float(msg.get("ts", time.time())),
                float(msg["lat"]),   # no conversion
                float(msg["lon"]),   # no conversion
                str(msg.get("severity", "LOW")),
            ),
        )
        c.commit()
        c.close()


    def alert_cb(sample):
        msg = safe_json_decode(sample.payload)
        if "ERROR" in msg:
            return
        c = sqlite3.connect(DB_PATH)
        c.execute(
            "INSERT INTO alerts (ts, level, title, msg) VALUES (?, ?, ?, ?)",
            (
                float(msg.get("ts", time.time())),
                str(msg.get("level", "")),
                str(msg.get("title", "")),
                str(msg.get("msg", "")),
            ),
        )
        c.commit()
        c.close()

    session = zenoh.open(zenoh.Config())
    session.declare_subscriber("vehicle/pose", pose_cb)
    session.declare_subscriber("vehicle/imu/raw", imu_cb)
    session.declare_subscriber("detect/pothole/event", pothole_cb)
    session.declare_subscriber("hmi/alert", alert_cb)
    st.session_state["zenoh_session"] = session

# -----------------
# UI
# -----------------
st.set_page_config(page_title="ADAS Heatmap (DB)", layout="wide")
st.title("🚗 ADAS Infotainment Dashboard with DB")

init_zenoh()
st_autorefresh(interval=2000, key="refresh_db_view")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📡 Vehicle Pose")
    pose_row = conn.execute(
        "SELECT ts, lat, lon, yaw, speed_mps FROM pose ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if pose_row:
        st.json({
            "ts": pose_row[0],
            "lat": pose_row[1],
            "lon": pose_row[2],
            "yaw": pose_row[3],
            "speed_mps": pose_row[4]
        })
    else:
        st.info("No pose yet")

    st.subheader("📡 IMU Data")
    imu_row = conn.execute(
        "SELECT ts, ax, ay, az FROM imu ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if imu_row:
        st.json({"ts": imu_row[0], "ax": imu_row[1], "ay": imu_row[2], "az": imu_row[3]})
    else:
        st.info("No IMU yet")

    st.subheader("⚠️ Alerts")
    alert_rows = conn.execute(
        "SELECT ts, level, title, msg FROM alerts ORDER BY ts DESC LIMIT 5"
    ).fetchall()
    if alert_rows:
        for a in alert_rows:
            st.warning(f"{a[2]}: {a[3]} ({a[1]})")
    else:
        st.info("No alerts yet")

with col2:
    st.subheader("🔥 Vehicle Path + Potholes")

    # Path points (already lat/lon)
    pose_rows = conn.execute(
        "SELECT lat, lon, speed_mps FROM pose ORDER BY ts DESC LIMIT 200"
    ).fetchall()
    path_points = [{"lon": lon, "lat": lat, "speed": float(v)} for (lat, lon, v) in reversed(pose_rows)]

    # Vehicle path segments
    segments = []
    for i in range(len(path_points) - 1):
        a, b = path_points[i], path_points[i + 1]
        # simple speed-based color
        red = int(min(255, a["speed"] * 10))
        green = 255 - red
        segments.append({
            "sourcePosition": [a["lon"], a["lat"]],
            "targetPosition": [b["lon"], b["lat"]],
            "color": [red, green, 0]
        })

    # Latest car position (safe fallback to anchor)
    if path_points:
        car_lat, car_lon = path_points[-1]["lat"], path_points[-1]["lon"]
    else:
        car_lat, car_lon = ANCHOR_LAT, ANCHOR_LON

    # Potholes (already lat/lon from ADAS)
    pothole_rows = conn.execute(
        "SELECT ts, lat, lon, severity FROM potholes ORDER BY ts DESC LIMIT 200"
    ).fetchall()
    pothole_data = []
    for ts, lat, lon, severity in pothole_rows:
        weight = 1 if severity == "LOW" else 3
        pothole_data.append({"lon": float(lon), "lat": float(lat), "weight": weight})

    # ✅ Fixed center on Lisbon anchor (static map)
    view_state = pdk.ViewState(
        latitude=ANCHOR_LAT,
        longitude=ANCHOR_LON,
        zoom=14   # zoom out a bit so you always see car + potholes
    )

    layers = []
    if segments:
        layers.append(pdk.Layer(
            "LineLayer",
            data=segments,
            get_source_position="sourcePosition",
            get_target_position="targetPosition",
            get_color="color",
            get_width=3
        ))

    car_icon = {
        "url": "https://cdn-icons-png.flaticon.com/512/61/61168.png",
        "width": 512,
        "height": 512,
        "anchorY": 512
    }
    layers.append(pdk.Layer(
        "IconLayer",
        data=[{"lat": car_lat, "lon": car_lon, "icon": car_icon}],
        get_icon="icon",
        get_size=4,
        size_scale=6,
        get_position="[lon, lat]"
    ))

    if pothole_data:
        layers.append(pdk.Layer(
            "HeatmapLayer",
            data=pothole_data,
            get_position="[lon, lat]",
            get_weight="weight",
            radiusPixels=40
        ))

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style="light",
        tooltip={"text": "Pothole\nLat: {lat}\nLon: {lon}"}
    )
    st.pydeck_chart(deck, use_container_width=True)

# -----------------
# Debug
# -----------------
st.subheader("🗄️ Debug DB contents")
with st.expander("Show counts"):
    counts = {}
    for table in ["pose", "imu", "potholes", "alerts"]:
        c = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        counts[table] = c
    st.write(counts)

with st.expander("Show recent rows"):
    st.write("Pose", conn.execute("SELECT * FROM pose ORDER BY ts DESC LIMIT 5").fetchall())
    st.write("IMU", conn.execute("SELECT * FROM imu ORDER BY ts DESC LIMIT 5").fetchall())
    st.write("Potholes", conn.execute("SELECT * FROM potholes ORDER BY ts DESC LIMIT 5").fetchall())
    st.write("Alerts", conn.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT 5").fetchall())
