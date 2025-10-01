#!/usr/bin/env python3
import json
import time
import zenoh
from zenoh import Encoding

POSE_TOPIC = "vehicle/pose"
IMU_TOPIC = "vehicle/imu/raw"

# Road length = 2000 m
ROAD_LENGTH_M = 2000
CAR_SPEED = 12.3  # m/s (~44 km/h)
STEP = 1.0        # seconds per tick

# Pothole distances along the route (in meters)
POTHOLE_POSITIONS = [500, 1000, 1500]

def main():
    with zenoh.open(zenoh.Config()) as session:
        pose_pub = session.declare_publisher(POSE_TOPIC, encoding=Encoding.APPLICATION_JSON)
        imu_pub = session.declare_publisher(IMU_TOPIC, encoding=Encoding.APPLICATION_JSON)

        pos_x = 0.0
        ts = time.time()

        while pos_x <= ROAD_LENGTH_M:
            ts = time.time()

            # Car pose (drives east along lon, lat fixed)
            base_lat, base_lon = 38.71165701061101, -9.138637
            M_PER_DEG_LON = 1.0 / 88000.0

            lat = base_lat
            lon = base_lon + pos_x * M_PER_DEG_LON

            pose = {
                "ts": ts,
                "x": pos_x,
                "y": 0.0,
                "lat": lat,
                "lon": lon,
                "yaw": 0.0,
                "speed_mps": CAR_SPEED,
            }
            pose_pub.put(json.dumps(pose))
            print("📡 Published pose", pose)

            # IMU with spike if near pothole
            if any(abs(pos_x - p) < CAR_SPEED for p in POTHOLE_POSITIONS):
                acc_z = 13.0  # simulate spike at pothole
            else:
                acc_z = 9.8

            imu = {
                "ts": ts + 0.01,
                "src": "carla-sim",
                "hz": 100,
                "acc": {"x": 0.2, "y": 0.0, "z": acc_z},
            }
            imu_pub.put(json.dumps(imu))
            print("📡 Published imu", imu)

            time.sleep(STEP)
            pos_x += CAR_SPEED * STEP

        print("✅ Simulation finished: car reached end of 2 km road")

if __name__ == "__main__":
    main()
