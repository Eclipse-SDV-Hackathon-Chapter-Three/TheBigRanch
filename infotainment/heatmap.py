import json
import streamlit as st
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import zenoh
from streamlit_autorefresh import st_autorefresh

# Topics
POSE_TOPIC = "vehicle/pose"
IMU_TOPIC = "vehicle/imu/raw"
POTHOLE_TOPIC = "detect/pothole/event"
ALERT_TOPIC = "hmi/alert"

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
    """Start zenoh subscribers once, store state in st.session_state"""
    if "zenoh_state" not in st.session_state:
        st.session_state["zenoh_state"] = {
            "vehicle_pose": {},
            "imu": {},
            "potholes": [],
            "alerts": []
        }

    state = st.session_state["zenoh_state"]

    def pose_cb(sample): state["vehicle_pose"] = safe_json_decode(sample.payload)
    def imu_cb(sample): state["imu"] = safe_json_decode(sample.payload)
    def pothole_cb(sample):
        event = safe_json_decode(sample.payload)
        if "ERROR" not in event:
            if event.get("lat") is not None and event.get("lon") is not None:
                state["potholes"].append(event)
    def alert_cb(sample):
        alert = safe_json_decode(sample.payload)
        if "ERROR" not in alert:
            state["alerts"].append(alert)

    if "zenoh_session" not in st.session_state:
        session = zenoh.open(zenoh.Config())
        session.declare_subscriber(POSE_TOPIC, pose_cb)
        session.declare_subscriber(IMU_TOPIC, imu_cb)
        session.declare_subscriber(POTHOLE_TOPIC, pothole_cb)
        session.declare_subscriber(ALERT_TOPIC, alert_cb)
        st.session_state["zenoh_session"] = session


# -----------------
# UI
# -----------------
st.set_page_config(page_title="ADAS Heatmap", layout="wide")
st.title("🚗 ADAS Infotainment Dashboard")

# Initialize Zenoh
init_zenoh()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📡 Vehicle Pose")
    st.json(st.session_state["zenoh_state"]["vehicle_pose"])

    st.subheader("📡 IMU Data")
    st.json(st.session_state["zenoh_state"]["imu"])

    st.subheader("⚠️ Alerts")
    alerts = st.session_state["zenoh_state"]["alerts"]
    if alerts:
        for a in alerts[-5:]:
            st.warning(f"{a['title']}: {a['msg']} ({a['level']})")
    else:
        st.info("No alerts yet")

with col2:
    st.subheader("🔥 Pothole Heatmap (Lisbon)")

    # build base map only once
    if "map" not in st.session_state:
        st.session_state["map"] = folium.Map(location=[38.7169, -9.1390], zoom_start=15)

    # fresh heatmap layer each rerun
    m = folium.Map(location=[38.7169, -9.1390], zoom_start=15)

    potholes = st.session_state["zenoh_state"]["potholes"]
    heat_data = [
        [p["lat"], p["lon"], 1 if p["severity"] == "LOW" else 3]
        for p in potholes
        if p.get("lat") is not None and p.get("lon") is not None
    ]

    if heat_data:
        HeatMap(heat_data).add_to(m)

    st_folium(m, width=800, height=600, key="heatmap")

# -----------------
# Auto-refresh every 2s (keeps state in memory)
# -----------------
st_autorefresh(interval=2000, key="refresh")

