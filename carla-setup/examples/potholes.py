#!/usr/bin/env python3

"""
Unified CARLA control script.

Modes:
  --mode manual   : Start manual keyboard control (with Zenoh, HUD, sensors).
  --mode auto     : Spawn a vehicle + potholes, put vehicle on autopilot, run 20s.

Usage:
  python3 carla_control.py --mode manual
  python3 carla_control.py --mode auto
"""

import argparse
import glob
import os
import signal
import sys
import time
import numpy.random as random
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

# Add PythonAPI for release mode
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/carla')
except IndexError:
    pass

import carla

# ==============================================================================
# -- Import your manual control classes ----------------------------------------
# ==============================================================================
# here you would import World, KeyboardControl, HUD, etc. from your existing script
# to keep this file shorter, assume you `from manual_control import game_loop`
# where `game_loop(args)` is your existing function.

# For now, stub:
# def game_loop(args):
#     print(">>> Running manual control (stub). Replace with your existing code.")
#     time.sleep(5)

# ==============================================================================
# -- Pothole helper ------------------------------------------------------------
# ==============================================================================

def spawn_pothole(world, bp_lib, location, scale=(2.0, 2.0, 0.2)):
    """Spawn a pothole by sinking a cube below the ground surface"""
    cube_bp = bp_lib.find("static.prop.cube")
    cube_bp.set_attribute("scale", f"{scale[0]},{scale[1]},{scale[2]}")
    transform = carla.Transform(location, carla.Rotation())
    pothole = world.try_spawn_actor(cube_bp, transform)
    if pothole:
        pothole.set_simulate_physics(False)
        print(f"Spawned pothole at {location}")
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
        print(f"[COLLISION] with {other} | intensity={intensity:.2f}")

    sensor.listen(on_collision)
    return sensor


def attach_imu_sensor(world, vehicle):
    blueprint = world.get_blueprint_library().find('sensor.other.imu')
    sensor = world.spawn_actor(blueprint, carla.Transform(), attach_to=vehicle)

    def on_imu(event):
        accel = event.accelerometer
        gyro = event.gyroscope
        print(f"[IMU] accel=({accel.x:.2f},{accel.y:.2f},{accel.z:.2f}) "
              f"gyro=({gyro.x:.2f},{gyro.y:.2f},{gyro.z:.2f})")

    sensor.listen(on_imu)
    return sensor


# ==============================================================================
# -- Main autopilot + pothole routine ------------------------------------------
# ==============================================================================

def run_auto_mode():
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
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
    vehicle.set_autopilot(True)

    print("🚗 Running autopilot for 20 seconds...")
    time.sleep(20)

    # Cleanup
    print("🧹 Cleaning up actors...")
    collision_sensor.destroy()
    imu_sensor.destroy()
    vehicle.destroy()
    for p in potholes:
        p.destroy()

    print("✅ Done.")

# ==============================================================================
# -- main() --------------------------------------------------------------------
# ==============================================================================

def main():
    run_auto_mode()
    argparser = argparse.ArgumentParser(
        description='CARLA Manual Control Client')
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='debug',
        help='print debug information')
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
    # ensure clean exit
    os.kill(os.getpid(), signal.SIGTERM)


if __name__ == "__main__":
    main()
