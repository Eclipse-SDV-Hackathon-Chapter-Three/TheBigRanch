import sys
import time
import math
import asyncio
import zenoh


def position_listener(sample):
    print()

def imu_listener(sample):
    # apply rule to check severity of pothole
    print()

async def main():
    # Open Zenoh session
    print("[Subscriber] Opening Zenoh session...")
    session = zenoh.open({})

    # Subscribe to a key expression
    # vehicle position topic
    vehicle_pose_topic = 'vehicle/pose'
    # raw IMU info
    vehicle_imu_raw_topic = 'vehicle/imu/raw'
    print(f"[Subscriber] Subscribing to: {vehicle_imu_raw_topic} and {vehicle_pose_topic}")
    session.declare_subscriber(vehicle_pose_topic, position_listener)
    session.declare_subscriber(vehicle_imu_raw_topic, imu_listener)

    # Keep the subscriber running
    try:
        print("[Subscriber] Listening for data. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Subscriber] Shutting down.")
    finally:
        session.close()

if __name__ == '__main__':
   loop = asyncio.get_event_loop()
   loop.run_until_complete(main())