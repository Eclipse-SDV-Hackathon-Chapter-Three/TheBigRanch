# fake_publisher.py
import time
import json
import math
import zenoh
from zenoh import Encoding

POSE_TOPIC = "vehicle/pose"
IMU_TOPIC = "vehicle/imu/raw"

def main():
    with zenoh.open(zenoh.Config()) as session:
        pose_pub = session.declare_publisher(POSE_TOPIC, encoding=Encoding.APPLICATION_JSON)
        imu_pub = session.declare_publisher(IMU_TOPIC, encoding=Encoding.APPLICATION_JSON)

        t = 0
        while True:
            ts = time.time()

            # Fake pose: car moves along X axis, speed 12.3 m/s
            pose = {
                "ts": ts,
                "x": 123.45 + t,
                "y": 67.89,
                "yaw": 0.0,
                "speed_mps": 12.3
            }
            pose_pub.put(json.dumps(pose))
            print("📡 Published pose", pose)

            # Fake IMU: z acceleration alternates between normal (9.8) and a spike (12)
            acc_z = 9.8 if t % 5 else 13.0
            imu = {
                "ts": ts + 0.01,
                "src": "carla",
                "hz": 100,
                "acc": { "x": 0.2, "y": 0.0, "z": acc_z }
            }
            imu_pub.put(json.dumps(imu))
            print("📡 Published imu", imu)

            time.sleep(0.1)
            t += 1

if __name__ == "__main__":
    main()
