#!/usr/bin/env python3
import json
import math
import time
import threading
from collections import deque
from typing import Optional, Dict

import zenoh
from zenoh import Encoding

# --------- Topics ----------
POSE_TOPIC = "vehicle/pose"
IMU_TOPIC = "vehicle/imu/raw"
POTHOLE_TOPIC = "detect/pothole/event"
ALERT_TOPIC = "hmi/alert"

# --------- Tunables ----------
ACC_Z_HP_ALPHA = 0.9
ACC_SPIKE_THRESHOLD = 2.0      # g spike threshold
MIN_SPEED_MPS = 4.0
WINDOW_SEC = 0.5
REFRACTORY_SEC = 1.5           # min time between events
MERGE_DIST_M = 5.0             # potholes within 5m = same
SEVERITY_HIGH = 3.5

# --------- State ----------
latest_pose: Dict = {}
imu_buf = deque()
last_event_ts = 0.0
last_event_xy = None
lock = threading.Lock()

# --------- Utils ----------
def zbytes_to_json(sample_payload):
    text = sample_payload.to_string()
    obj = json.loads(text)
    if isinstance(obj, str):
        obj = json.loads(obj)
    return obj

class HighPass:
    def __init__(self, alpha: float):
        self.alpha = alpha
        self.last_in = None
        self.last_hp = 0.0

    def step(self, x: float) -> float:
        if self.last_in is None:
            self.last_in = x
            self.last_hp = 0.0
            return 0.0
        hp = self.alpha * (self.last_hp + x - self.last_in)
        self.last_in = x
        self.last_hp = hp
        return hp

hp_z = HighPass(ACC_Z_HP_ALPHA)

def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def should_merge(prev_xy, new_xy) -> bool:
    if prev_xy is None or new_xy is None:
        return False
    plat, plon = prev_xy
    nlat, nlon = new_xy
    return haversine(plat, plon, nlat, nlon) <= MERGE_DIST_M

# --------- Callbacks ----------
def pose_cb(sample):
    """Convert Carla x/y (meters) to lat/lon once."""
    global latest_pose
    try:
        msg = zbytes_to_json(sample.payload)

        # Anchor: Graça / Alfama in Lisbon
        base_lat, base_lon = 38.711046, -9.138637

        # Conversion factors: meters → degrees at Lisbon latitude
        M_PER_DEG_LAT = 1.0 / 111111.0      # ~0.000009°
        M_PER_DEG_LON = 1.0 / 88000.0       # ~0.000011° at 38.7°N

        x_m = float(msg.get("x", 0.0))  # east-west (meters)
        y_m = float(msg.get("y", 0.0))  # north-south (meters)

        # Apply proper scaling
        lat = base_lat + y_m * M_PER_DEG_LAT
        lon = base_lon + x_m * M_PER_DEG_LON

        msg_converted = {
            "ts": msg.get("ts", time.time()),
            "lat": lat,
            "lon": lon,
            "yaw": msg.get("yaw", 0.0),
            "speed_mps": msg.get("speed_mps", 0.0)
        }

        with lock:
            latest_pose = msg_converted
    except Exception as e:
        print("POSE parse error:", e)

def imu_cb(sample):
    try:
        msg = zbytes_to_json(sample.payload)
        ts = msg.get("ts", time.time())
        acc = msg.get("acc", {})
        az = float(acc.get("z", 0.0))

        az_hp = hp_z.step(az)

        with lock:
            imu_buf.append((ts, az_hp))
            cut = ts - WINDOW_SEC
            while imu_buf and imu_buf[0][0] < cut:
                imu_buf.popleft()
    except Exception as e:
        print("IMU parse error:", e)

def current_speed_and_pos() -> Optional[Dict]:
    with lock:
        if not latest_pose:
            return None
        return latest_pose

def severity_from_spike(spike: float) -> str:
    return "HIGH" if abs(spike) >= SEVERITY_HIGH else "LOW"

# --------- Detection Loop ----------# --------- Detection Loop ----------
def detection_loop(session):
    global last_event_ts, last_event_xy

    pothole_pub = session.declare_publisher(POTHOLE_TOPIC, encoding=Encoding.APPLICATION_JSON)
    alert_pub = session.declare_publisher(ALERT_TOPIC, encoding=Encoding.APPLICATION_JSON)

    print("ADAS detection loop started…")
    while True:
        time.sleep(0.05)

        pose = current_speed_and_pos()
        if not pose:
            continue

        lat, lon = pose["lat"], pose["lon"]
        speed = pose["speed_mps"]
        if speed < MIN_SPEED_MPS:
            continue

        with lock:
            if not imu_buf:
                continue
            spikes = [abs(s[1]) for s in imu_buf]
            max_spike = max(spikes) if spikes else 0.0
            ts_latest = imu_buf[-1][0]

        # only trigger if above threshold
        if max_spike < ACC_SPIKE_THRESHOLD:
            continue

        # refractory & merge check
        if (ts_latest - last_event_ts) < REFRACTORY_SEC and sh


# --------- Main ----------
def main():
    zconf = zenoh.Config()
    with zenoh.open(zconf) as session:
        session.declare_subscriber(POSE_TOPIC, pose_cb)
        session.declare_subscriber(IMU_TOPIC, imu_cb)

        t = threading.Thread(target=detection_loop, args=(session,), daemon=True)
        t.start()

        print("ADAS node running. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("Shutting down ADAS node…")

if __name__ == "__main__":
    main()
