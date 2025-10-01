import json
import sys
import time
import math
import zenoh


# tiny state
state = {
    "last_imu_ts": 0.0,
    "prev_acc_z": None,
    "last_event_ts": 0.0,
    "last_pose": {"speed_mps": 0.0, "x": 0.0, "y": 0.0}
}


#changable variables
MIN_SPEED = 4.0          # m/s (~14 km/h)
DELTA_Z_TH = 2.5         # m/s^2 change between consecutive samples
DEBOUNCE_S = 1.5         # seconds between events
#-------------------

def severity_from_delta(dz):
    if dz > 4.0: return "HIGH"
    if dz > 3.0: return "MED"
    return "LOW"

def position_listener(sample):
    try:
        data = json.loads(sample.payload.decode("utf-8"))
        state["last_pose"] = data
    except Exception as e:
        print(f"[listener] pose parse err: {e}")

def imu_listener(sample):
    try:
        data = json.loads(sample.payload.decode("utf-8"))
        ts = float(data.get("ts", time.time()))
        acc = data.get("acc", {})
        acc_z = float(acc.get("z", 0.0))
        speed = float(state["last_pose"].get("speed_mps", 0.0))

        prev = state["prev_acc_z"]
        state["prev_acc_z"] = acc_z

        ## On the first IMU sample theres no previous acc_z to compare against
        if prev is None:
            return

        ## In theory potholes will cause a sharp change so a big dz (Delta-z acceleration, calculates the absolute change in vertical acceleration)
        dz = abs(acc_z - prev)
        now = ts

        ''' Little help from our 5th member ChatGPT on doing these calculations '''
        if speed >= MIN_SPEED and dz >= DELTA_Z_TH and (now - state["last_event_ts"]) >= DEBOUNCE_S:
            sev = severity_from_delta(dz)
            x = state["last_pose"].get("x", 0.0)
            y = state["last_pose"].get("y", 0.0)
            print(f"[POTHOLE] {sev} at ({x:.1f},{y:.1f}) | variation_acc_z={dz:.2f} m/s2 speed={speed:.1f} m/s")
            state["last_event_ts"] = now

    except Exception as e:
        print(f"[listener] imu parse err: {e}")

def main():
    # Open Zenoh session
    print("[Listener] Opening Zenoh session...")
    session = zenoh.open({})

    POSE_TOPIC = 'vehicle/pose' #Vehicle Position info
    IMU_TOPIC = 'vehicle/imu/raw' #Raw IMU
    print(f"[Subscriber] Subscribing to: {IMU_TOPIC} and {POSE_TOPIC}")
    session.declare_subscriber(POSE_TOPIC, position_listener)
    session.declare_subscriber(IMU_TOPIC, imu_listener)

    # Keep the subscriber running
    try:
        print("[Listener] Listening for data. Press Ctrl+C to stop")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Listener] Shutting down")
    finally:
        session.close()

if __name__ == '__main__':
   main()