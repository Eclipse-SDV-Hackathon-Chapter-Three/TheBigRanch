#!/usr/bin/env python3

"""
Potholes CARLA Source (guaranteed-detect version).

- Spawns ego vehicle + a visible "pothole" prop row.
- Attaches IMU sensor (20 Hz).
- Publishes pose + IMU to Zenoh.
- Additionally injects a synthetic IMU Z spike when the vehicle reaches the pothole row,
  so the downstream detector will certainly emit an event.

Zenoh topics:
  - vehicle/pose
  - vehicle/imu/raw
"""

import argparse
import glob
import os
import signal
import sys
import time
import math
import numpy.random as random
import zenoh
import json

# ==============================================================================
# -- find carla module ---------------------------------------------------------
# ==============================================================================
try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/carla')
except IndexError:
    pass

import carla

# ==============================================================================
# -- Zenoh Init ----------------------------------------------------------------
# ==============================================================================
session = zenoh.open(zenoh.Config())
pose_pub = session.declare_publisher("vehicle/pose")
imu_pub = session.declare_publisher("vehicle/imu/raw")

# ==============================================================================
# -- Pothole helper ------------------------------------------------------------
# ==============================================================================
def spawn_pothole(world, bp_lib, location):
    """
    Spawns a visible obstacle using a static prop. Tries several common props.
    """
    candidate_filters = [
        "static.prop.*barrier*",
        "static.prop.*speed*",
        "static.prop.*cone*",
        "static.prop.*box*",
        "static.*cube*",
        "static.prop.*construction*",
        "static.prop.*fence*",
        "static.prop.*rail*",
    ]

    cube_bp = None
    for pattern in candidate_filters:
        matches = bp_lib.filter(pattern)
        if matches:
            cube_bp = matches[0]
            print(f"[POTHOLE] Using prop blueprint: {cube_bp.id}")
            break

    if cube_bp is None:
        available = [bp.id for bp in bp_lib if bp.id.startswith("static.")]
        raise IndexError(
            "No suitable static prop found. "
            f"Sample static blueprints: {available[:25]} ..."
        )

    transform = carla.Transform(location, carla.Rotation())
    pothole = world.try_spawn_actor(cube_bp, transform)

    if pothole:
        try:
            pothole.set_simulate_physics(False)
        except Exception:
            pass

        print(f"Spawned visual pothole at {location}")

        # Debug outline (visible indefinitely)
        world.debug.draw_box(
            carla.BoundingBox(location, carla.Vector3D(1.0, 1.0, 0.5)),
            rotation=carla.Rotation(),
            life_time=0.0,
            thickness=0.1,
            color=carla.Color(255, 0, 0),
        )

    return pothole

# ==============================================================================
# -- Sensors -------------------------------------------------------------------
# ==============================================================================
def attach_imu_sensor(world, vehicle):
    bp = world.get_blueprint_library().find('sensor.other.imu')
    # match world tick (20 Hz)
    if bp.has_attribute('sensor_tick'):
        bp.set_attribute('sensor_tick', '0.05')
    sensor = world.spawn_actor(bp, carla.Transform(), attach_to=vehicle)

    def on_imu(event):
        ts = time.time()
        msg = {
            "ts": ts,
            "src": "carla",
            "hz": 20,  # matches sensor_tick above
            "acc": {
                "x": round(event.accelerometer.x, 3),
                "y": round(event.accelerometer.y, 3),
                "z": round(event.accelerometer.z, 3)
            }
        }
        imu_pub.put(json.dumps(msg))
        # print(f"[IMU] {msg}")  # noisy—uncomment for debugging

    sensor.listen(on_imu)
    return sensor

# ==============================================================================
# -- Pose publisher ------------------------------------------------------------
# ==============================================================================
def publish_pose(vehicle):
    transform = vehicle.get_transform()
    velocity = vehicle.get_velocity()
    ts = time.time()

    speed = (velocity.x**2 + velocity.y**2 + velocity.z**2) ** 0.5
    yaw_rad = transform.rotation.yaw * math.pi / 180.0  # deg to rad

    msg = {
        "ts": ts,
        "x": round(transform.location.x, 2),
        "y": round(transform.location.y, 2),
        "yaw": round(yaw_rad, 3),
        "speed_mps": round(speed, 2)
    }
    pose_pub.put(json.dumps(msg))
    # print(f"[POSE] {msg}")

# ==============================================================================
# -- Synthetic IMU spike -------------------------------------------------------
# ==============================================================================
def inject_imu_spike():
    """
    Publish a short IMU burst so downstream detector will exceed HP Z threshold:
      baseline (≈9.81) -> one big Z sample -> baseline.
    At 20 Hz, this fits well within a 0.5 s window.
    """
    # Baseline g
    base = 9.81
    # Big one-sample bump: (14 - 9.81) ~ 4.19; with HP alpha 0.9 → ~3.77 (> 2.0)
    spike = 14.0

    def pub(z):
        imu_msg = {
            "ts": time.time(),
            "src": "synthetic",
            "hz": 20,
            "acc": {"x": 0.0, "y": 0.0, "z": round(z, 3)},
        }
        imu_pub.put(json.dumps(imu_msg))

    # a couple of baselines
    pub(base)
    time.sleep(0.05)
    pub(base)
    time.sleep(0.05)
    # spike
    pub(spike)
    time.sleep(0.05)
    # return to baseline
    pub(base)
    time.sleep(0.05)

# ==============================================================================
# -- Main autopilot + pothole routine ------------------------------------------
# ==============================================================================
def run_auto_mode(args):
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

    # Enable synchronous mode for consistent ticks
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05  # 20 Hz
    world.apply_settings(settings)

    # Spawn vehicle
    spawn_point = random.choice(world.get_map().get_spawn_points())
    vehicle_bp = random.choice(bp_lib.filter("vehicle.*"))
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
    if not vehicle:
        print("Failed to spawn vehicle")
        return

    print(f"Spawned vehicle {vehicle.type_id} at {spawn_point.location}")

    # Camera above vehicle
    spectator = world.get_spectator()
    spectator.set_transform(carla.Transform(
        spawn_point.location + carla.Location(z=50),
        carla.Rotation(pitch=-90)
    ))

    # Attach sensors
    imu_sensor = attach_imu_sensor(world, vehicle)

    # Get orientation vectors from the spawn point
    forward_vector = spawn_point.get_forward_vector()
    right_vector = spawn_point.get_right_vector()

    # --------------------------------------------------------------------------
    # Spawn a visible pothole row in front of the vehicle
    # --------------------------------------------------------------------------
    potholes = []
    pothole_centers = []  # store for trigger

    row_distance = 25.0    # meters ahead
    lateral_offsets = [-0.7, 0.0, 0.7]
    height_above_road = 0.10  # visible bump

    # Base location at desired distance ahead
    base_loc = carla.Location(
        x=spawn_point.location.x + forward_vector.x * row_distance,
        y=spawn_point.location.y + forward_vector.y * row_distance,
        z=spawn_point.location.z + forward_vector.z * row_distance
    )

    # Project to the nearest driving lane to get a proper road Z
    wp = world.get_map().get_waypoint(
        base_loc, project_to_road=True, lane_type=carla.LaneType.Driving
    )
    road_loc = wp.transform.location

    # Spawn a row across the lane and remember the center as trigger point
    center_loc = carla.Location(
        x=road_loc.x + right_vector.x * 0.0,
        y=road_loc.y + right_vector.y * 0.0,
        z=road_loc.z + height_above_road
    )
    pothole_centers.append(center_loc)

    for off in lateral_offsets:
        loc = carla.Location(
            x=road_loc.x + right_vector.x * off,
            y=road_loc.y + right_vector.y * off,
            z=road_loc.z + height_above_road
        )
        ph = spawn_pothole(world, bp_lib, loc)
        if ph:
            potholes.append(ph)

    # Start autopilot
    traffic_manager = client.get_trafficmanager()
    vehicle.set_autopilot(True, traffic_manager.get_port())

    print("Running autopilot for 20 seconds...")

    # Trigger state
    triggered = False
    trigger_radius = 2.0  # meters

    for _ in range(int(20 / settings.fixed_delta_seconds)):
        world.tick()
        publish_pose(vehicle)

        # Check distance to pothole center and inject IMU spike once
        if not triggered:
            vloc = vehicle.get_transform().location
            c = pothole_centers[0]
            dist = math.hypot(vloc.x - c.x, vloc.y - c.y)
            # Ensure we are moving fast enough (>= 4 m/s) to match detector's arm condition
            speed = vehicle.get_velocity()
            speed_mps = (speed.x**2 + speed.y**2 + speed.z**2) ** 0.5

            if dist <= trigger_radius and speed_mps >= 4.0:
                print(f"[SYNTH] Injecting IMU spike at dist={dist:.2f} m, speed={speed_mps:.2f} m/s")
                inject_imu_spike()
                triggered = True

    # Cleanup
    print("Cleaning up actors...")
    try:
        imu_sensor.destroy()
    except Exception:
        pass

    try:
        vehicle.destroy()
    except Exception:
        pass

    for p in potholes:
        try:
            p.destroy()
        except Exception:
            pass

    session.close()

    # Restore async mode
    settings.synchronous_mode = False
    settings.fixed_delta_seconds = None
    world.apply_settings(settings)

    print("Done")

# ==============================================================================
# -- main() --------------------------------------------------------------------
# ==============================================================================
def main():
    argparser = argparse.ArgumentParser(
        description='CARLA Manual Control Client')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '--router',
        default='127.0.0.1',
        type=str,
        help='IP address of the Zenoh router (default: 127.0.0.1)')
    args = argparser.parse_args()
    run_auto_mode(args)
    os.kill(os.getpid(), signal.SIGTERM)

if __name__ == "__main__":
    main()
