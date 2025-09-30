#!/usr/bin/env python3

"""
Potholes CARLA Source.

- Spawns ego vehicle + potholes.
- Attaches collision + IMU sensors.
- Publishes events and raw data to Zenoh.

Zenoh topics:
  - vehicle/imu/raw
  - detect/pothole/event
"""

import argparse
import glob
import os
import signal
import sys
import time
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
def spawn_pothole(world, bp_lib, location, scale=(2.0, 2.0, 0.2)):
    cube_bp = bp_lib.find("static.prop.cube")
    cube_bp.set_attribute("scale", f"{scale[0]},{scale[1]},{scale[2]}")
    transform = carla.Transform(location, carla.Rotation())
    pothole = world.try_spawn_actor(cube_bp, transform)

    if pothole:
        pothole.set_simulate_physics(False)
        print(f"Spawned pothole at {location}")

        # Debug outline
        world.debug.draw_box(
            carla.BoundingBox(location,
                              carla.Vector3D(scale[0]/2, scale[1]/2, scale[2]/2)),
            rotation=carla.Rotation(),
            life_time=0.0,
            thickness=0.1,
            color=carla.Color(255, 0, 0)
        )

    return pothole

# ==============================================================================
# -- Sensors -------------------------------------------------------------------
# ==============================================================================
def attach_imu_sensor(world, vehicle):
    blueprint = world.get_blueprint_library().find('sensor.other.imu')
    sensor = world.spawn_actor(blueprint, carla.Transform(), attach_to=vehicle)

    def on_imu(event):
        ts = time.time()
        msg = {
            "ts": ts,
            "src": "carla",
            "hz": 100,  # adjust if your IMU runs at different rate
            "acc": {
                "x": round(event.accelerometer.x, 3),
                "y": round(event.accelerometer.y, 3),
                "z": round(event.accelerometer.z, 3)
            }
        }
        imu_pub.put(json.dumps(msg))
        print(f"[IMU] {msg}")

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
    yaw_rad = transform.rotation.yaw * 3.14159265 / 180.0  # deg → rad

    msg = {
        "ts": ts,
        "x": round(transform.location.x, 2),
        "y": round(transform.location.y, 2),
        "yaw": round(yaw_rad, 3),
        "speed_mps": round(speed, 2)
    }
    pose_pub.put(json.dumps(msg))
    print(f"[POSE] {msg}")

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
        print("❌ Failed to spawn vehicle")
        return

    print(f"✅ Spawned vehicle {vehicle.type_id} at {spawn_point.location}")

    # Camera above vehicle
    spectator = world.get_spectator()
    spectator.set_transform(carla.Transform(
        spawn_point.location + carla.Location(z=50),
        carla.Rotation(pitch=-90)
    ))

    # Attach sensors
    imu_sensor = attach_imu_sensor(world, vehicle)

    # Spawn potholes
    potholes = []
    for i in range(5):
        loc = carla.Location(
            x=spawn_point.location.x + (i+1)*10.0,
            y=spawn_point.location.y,
            z=spawn_point.location.z + 0.05   # slightly above road
        )
        pothole = spawn_pothole(world, bp_lib, loc)
        if pothole:
            potholes.append(pothole)

    # Start autopilot
    traffic_manager = client.get_trafficmanager()
    vehicle.set_autopilot(True, traffic_manager.get_port())

    print("🚗 Running autopilot for 20 seconds...")

    for _ in range(int(20 / settings.fixed_delta_seconds)):
        world.tick()
        publish_pose(vehicle)

    # Cleanup
    print("🧹 Cleaning up actors...")
    imu_sensor.destroy()
    vehicle.destroy()
    for p in potholes:
        p.destroy()

    session.close()

    # Restore async mode
    settings.synchronous_mode = False
    settings.fixed_delta_seconds = None
    world.apply_settings(settings)

    print("✅ Done.")

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
    args = argparser.parse_args()
    run_auto_mode(args)
    os.kill(os.getpid(), signal.SIGTERM)

if __name__ == "__main__":
    main()

