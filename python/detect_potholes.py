import asyncio
import json
import argparse
import threading

import zenoh

from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Dict, Any, Optional, Deque, Tuple

import numpy as np
import math, time, uuid

# -----------------------------------
#  Config + Data Classes
# -----------------------------------
CONFIG = {
    "imu_window_s": 1.0,
    "imu_sample_rate_hz": 100,
    "jerk_threshold_g": 0.7,
    "z_accel_threshold_g": 0.6,
    "min_speed_m_s": 5.0,
    "merge_time_s": 1.0,
    "grid_cell_m": 5.0,
    "severity_map": [(0.7, "LOW"), (1.5, "MEDIUM"), (2.5, "HIGH")],
    "vehicle_id": "sim-vehicle-01",
}
G = 9.80665  # m/s²

main_loop = asyncio.new_event_loop()
threading.Thread(target=main_loop.run_forever, daemon=True).start()


@dataclass
class Pose:
    timestamp: float
    x: float
    y: float
    z: float
    heading: float
    speed: float


@dataclass
class IMU:
    timestamp: float
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float


# -----------------------------------
#  Publisher Abstractions
# -----------------------------------
class Publisher:
    async def publish(self, topic: str, message: Dict[str, Any]):
        raise NotImplementedError


class PrintPublisher(Publisher):
    async def publish(self, topic: str, message: Dict[str, Any]):
        print(f"[PUBLISH] topic={topic} message={message}")


class ZenohPublisher(Publisher):
    def __init__(self, session: zenoh.Session):
        self.session = session

    async def publish(self, topic: str, message: Dict[str, Any]):
        data = json.dumps(message).encode("utf-8")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.session.put(topic, data))


# -----------------------------------
#  Detector Service
# -----------------------------------
class DetectorService:
    def __init__(self, publisher: Publisher, config: Dict = None):
        self.pub = publisher
        self.cfg = {**CONFIG, **(config or {})}
        max_samples = int(self.cfg["imu_window_s"] * self.cfg["imu_sample_rate_hz"]) + 10
        self.imu_buffer: Deque[IMU] = deque(maxlen=max_samples)
        self.last_pose: Optional[Pose] = None
        self.last_event_time: Optional[float] = None
        self.last_event_cell: Optional[Tuple[int, int]] = None
        self.grid_counts = defaultdict(int)

    async def handle_pose(self, msg: Dict[str, Any]):
        pose = Pose(**msg)
        print(pose)
        self.last_pose = pose
        await self._attempt_detection()

    async def handle_imu(self, msg: Dict[str, Any]):
        imu = IMU(**msg)
        print(imu)
        self.imu_buffer.append(imu)
        if len(self.imu_buffer) >= 3:
            await self._attempt_detection()

    async def _attempt_detection(self):
        if len(self.imu_buffer) < 3 or not self.last_pose:
            return

        # Extract time and z-acceleration from IMU buffer
        ts = np.array([imu.timestamp for imu in self.imu_buffer], dtype=float)
        az = np.array([imu.az for imu in self.imu_buffer], dtype=float)

        # Compute jerk (derivative of acceleration wrt time)
        jerk = np.gradient(az, ts) / G
        az_g = az / G

        if (np.any(np.abs(jerk) > self.cfg["jerk_threshold_g"]) or
                np.any(np.abs(az_g) > self.cfg["z_accel_threshold_g"])):
            peak_g = float(np.max(np.abs(jerk)))
            severity = self._classify_severity(peak_g)
            metrics = {
                "peak_jerk_g": peak_g,
                "peak_accel_g": float(np.max(np.abs(az_g)))
            }

            event = self._build_event(
                timestamp=ts[-1],
                vehicle_id=self.cfg["vehicle_id"],
                pose=self.last_pose,
                severity=severity,
                metrics=metrics
            )

            # ✅ Publish pothole event
            await self.pub.publish("vehicle/events/pothole", event)

            # ✅ Publish HMI alert
            alert = {
                "type": "pothole",
                "severity": severity,
                "location": {
                    "x": self.last_pose.x,
                    "y": self.last_pose.y,
                    "z": self.last_pose.z,
                },
                "vehicle_id": self.cfg["vehicle_id"],
                "timestamp": ts[-1],
            }
            await self.pub.publish("hmi/alert", alert)

            # Update grid counts
            cell = self._grid_cell(self.last_pose.x, self.last_pose.y)
            self.grid_counts[cell] += 1

    def _classify_severity(self, peak_g: float) -> str:
        for threshold, level in self.cfg["severity_map"]:
            if peak_g < threshold:
                return level
        return self.cfg["severity_map"][-1][1]

    def _grid_cell(self, x: float, y: float) -> Tuple[int, int]:
        cell_size = self.cfg["grid_cell_m"]
        return (int(math.floor(x / cell_size)), int(math.floor(y / cell_size)))

    def _build_event(self, timestamp: float, vehicle_id: str, pose: Pose, severity: str, metrics: Dict[str, Any]) -> \
    Dict[str, Any]:
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": float(timestamp),
            "vehicle_id": vehicle_id,
            "location": {"x": float(pose.x), "y": float(pose.y), "z": float(pose.z)},
            "severity": severity,
            "metrics": metrics,
        }


# -----------------------------------
#  Simulation Mode
# -----------------------------------
async def simulate_streams(detector: DetectorService, duration_s: float = 10.0):
    imu_hz = detector.cfg["imu_sample_rate_hz"]
    pose_hz = 10
    t0 = time.time()
    sim_t = 0.0
    last_pose_emit = 0.0
    x = 0.0
    speed = 12.0
    rng = np.random.default_rng(12345)
    pothole_times = [3.2, 6.1]
    pothole_duration_s = 0.1

    while sim_t < duration_s:
        now = t0 + sim_t
        az = rng.normal(0.0, 0.2) * G
        ax, ay = 0.0, 0.0
        for pt in pothole_times:
            if abs(sim_t - pt) < pothole_duration_s:
                az += 4.0 * G * math.exp(-((sim_t - pt) ** 2) / (2 * (0.02 ** 2)))
                ax += 0.5 * G
        imu_msg = {"timestamp": now, "ax": ax, "ay": ay, "az": az, "gx": 0.0, "gy": 0.0, "gz": 0.0}
        await detector.handle_imu(imu_msg)
        if sim_t - last_pose_emit >= 1.0 / pose_hz:
            x += speed * (sim_t - last_pose_emit)
            pose_msg = {"timestamp": now, "x": x, "y": 0.0, "z": 0.0, "heading": 0.0, "speed": speed}
            await detector.handle_pose(pose_msg)
            last_pose_emit = sim_t
        await asyncio.sleep(1.0 / imu_hz)
        sim_t = time.time() - t0


# -----------------------------------
#  Zenoh Mode
# -----------------------------------
def start_subscriptions(session: zenoh.Session, detector: DetectorService):
    def imu_listener(sample):
        try:
            msg = json.loads(sample.payload.to_bytes())
            # thread-safe submission to the loop running in the other thread
            asyncio.run_coroutine_threadsafe(detector.handle_imu(msg), main_loop)
        except Exception as e:
            print("IMU handler error:", e)

    def pose_listener(sample):
        try:
            msg = json.loads(sample.payload.to_bytes())
            # thread-safe submission to the loop running in the other thread
            asyncio.run_coroutine_threadsafe(detector.handle_pose(msg), main_loop)
        except Exception as e:
            print("POSE handler error:", e)

    session.declare_subscriber("vehicle/imu/raw", imu_listener)
    session.declare_subscriber("vehicle/pose", pose_listener)


# -----------------------------------
#  Main
# -----------------------------------
async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["sim", "zenoh"], default="sim",
                        help="Run in simulation mode or Zenoh mode")
    args = parser.parse_args()

    if args.mode == "sim":
        print("Running in SIMULATION mode")
        publisher = PrintPublisher()
        detector = DetectorService(publisher)
        await simulate_streams(detector, duration_s=8.0)

    elif args.mode == "zenoh":
        print("Running in ZENOH mode (listening to CARLA)")
        conf = zenoh.Config()
        session = zenoh.open(conf)
        publisher = ZenohPublisher(session)
        detector = DetectorService(publisher)
        start_subscriptions(session, detector)
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            session.close()


if __name__ == "__main__":
    asyncio.run(main())
