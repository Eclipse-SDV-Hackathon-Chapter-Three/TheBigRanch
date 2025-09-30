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
imu_pub = session.declare_publisher("vehicle/imu/raw")
pothole_pub = session.declare_publisher("detect/pothole/event")

# ==============================================================================
# -- Pothole helper ------------------------------------------------------------
# ==============================================================================
def spawn_pothole(world, bp_lib, location, scale=(2.0, 2.0, 0.2)):
    # Spawn a cube prop for physics bump
    cube_bp = bp_lib.find("static.prop.cube")
    cube_bp.set_attribute("scale", f"{scale[0]},{scale[1]},{scale[2]}")
    transform = carla.Transform(location, carla.Rotation())
    pothole = world.try_spawn_actor(cube_bp, transform)

    if pothole:
        pothole.set_simulate_physics(False)
        print(f"Spawned pothole at {location}")

        # Draw debug outline (half-size extents!)
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
def attach_collision_sensor(world, vehicle):
    blueprint = world.get_blueprint_library().find('sensor.other.collision')
    sensor = world.spawn_actor(blueprint, carla.Transform(), attach_to=vehicle)

    def on_collision(event):
        other = event.other_actor.type_id
        impulse = event.normal_impulse
        intensity = (impulse.x**2 + impulse.y**2 + impulse.z**2) ** 0.5

        msg = {
            "frame": event.frame,
            "other_actor": other,
            "intensity": round(intensity, 2),
            "location": {
                "x": event.transform.location.x,
                "y": event.transform.location.y,
                "z": event.transform.location.z
            }
        }

        print(f"[COLLISION] {msg}")
        pothole_pub.put(json.dumps(msg))   # Publish to Zenoh

    sensor.listen(on_collision)
    return sensor


def attach_imu_sensor(world, vehicle):
    blueprint = world.get_blueprint_library().find('sensor.other.imu')
    sensor = world.spawn_actor(blueprint, carla.Transform(), attach_to=vehicle)

    def on_imu(event):
        msg = {
            "accel": [round(event.accelerometer.x, 3),
                      round(event.accelerometer.y, 3),
                      round(event.accelerometer.z, 3)],
            "gyro": [round(event.gyroscope.x, 3),
                     round(event.gyroscope.y, 3),
                     round(event.gyroscope.z, 3)],
            "compass": round(event.compass, 3)
        }

        print(f"[IMU] {msg}")
        imu_pub.put(json.dumps(msg))   # Publish to Zenoh

    sensor.listen(on_imu)
    return sensor

# ==============================================================================
# -- Main autopilot + pothole routine ------------------------------------------
# ==============================================================================
def run_auto_mode(args):
    client = carla.Client(args.host, args.port)
    client.set_timeout(2000.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

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
    collision_sensor = attach_collision_sensor(world, vehicle)
    imu_sensor = attach_imu_sensor(world, vehicle)

    # Spawn potholes ahead
    potholes = []
    for i in range(5):
        loc = carla.Location(
            x=spawn_point.location.x + (i+1)*10.0,
            y=spawn_point.location.y,
            z=spawn_point.location.z - 0.2   # sink below road surface
        )
        pothole = spawn_pothole(world, bp_lib, loc)
        if pothole:
            potholes.append(pothole)

    # Start autopilot
    traffic_manager = client.get_trafficmanager()
    vehicle.set_autopilot(True, traffic_manager.get_port())

    print("🚗 Running autopilot for 20 seconds...")
    time.sleep(20)

    # Cleanup
    print("🧹 Cleaning up actors...")
    collision_sensor.destroy()
    imu_sensor.destroy()
    vehicle.destroy()
    session.close()
    for p in potholes:
        p.destroy()

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

