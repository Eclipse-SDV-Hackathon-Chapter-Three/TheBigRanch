#!/usr/bin/env python3

"""
Potholes CARLA Source (visual potholes + guaranteed detect).

- Spawns ego vehicle.
- Draws visible "potholes" (red debug boxes) on the lane surface — no physical props.
- Attaches IMU sensor (20 Hz) and publishes pose + IMU to Zenoh.
- Injects a synthetic IMU Z spike exactly when the vehicle reaches a pothole center.

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
imu_pub  = session.declare_publisher("vehicle/imu/raw")

# ==============================================================================
# -- Visual pothole helpers (no actors) ----------------------------------------
# ==============================================================================
def draw_pothole_box(world, center_loc, size_xy=(1.2, 1.0), thickness=0.05, color=carla.Color(255, 0, 0)):
    """
    Draw a flat red box on the road to represent a visible pothole outline.
    size_xy: meters (length along lane, width across lane)
    thickness: visual thickness (height) of the drawn debug box
    """
    length, width = size_xy
    half = carla.Vector3D(length / 2.0, width / 2.0, thickness / 2.0)
    bb = carla.BoundingBox(center_loc, half)
    world.debug.draw_box(bb, rotation=carla.Rotation(), life_time=0.0, thickness=0.08, color=color)
    # dot in the middle for clarity
    world.debug.draw_point(center_loc, size=0.15, color=color, life_time=0.0)

def lane_basis_at(world, loc):
    """Return (origin, forward, right) using the waypoint at loc."""
    wp = world.get_map().get_waypoint(loc, project_to_road=True, lane_type=carla.LaneType.Driving)
    tf = wp.transform
    origin = tf.location
    forward = tf.get_forward_vector()
    right   = tf.get_right_vector()
    up      = tf.get_up_vector()
    return origin, forward, right, up

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
def inject_imu_burst(duration_s=0.4):
    """
    Publish a short IMU burst so downstream detector will exceed HP Z threshold.
    Alternates baseline and spike at 20 Hz for 'duration_s'.
    """
    base = 9.81
    spike = 14.0  # (14-9.81)=4.19; with HP alpha 0.9 → ~3.77 (>2.0)
    end = time.time() + duration_s
    toggle = True
    while time.time() < end:
        z = spike if toggle else base
        imu_msg = {
            "ts": time.time(),
            "src": "synthetic",
            "hz": 20,
            "acc": {"x": 0.0, "y": 0.0, "z": round(z, 3)},
        }
        imu_pub.put(json.dumps(imu_msg))
        toggle = not toggle
        time.sleep(0.05)  # 20 Hz

# ==============================================================================
# -- Main autopilot + visual potholes ------------------------------------------
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

    # Get basis from the lane at the pothole row (not from spawn)
    forward = spawn_point.get_forward_vector()
    row_distance = 35.0  # farther so speed stays up
    approx_row = carla.Location(
        x=spawn_point.location.x + forward.x * row_distance,
        y=spawn_point.location.y + forward.y * row_distance,
        z=spawn_point.location.z + forward.z * row_distance
    )
    row_origin, lane_fwd, lane_right, lane_up = lane_basis_at(world, approx_row)

    # --------------------------------------------------------------------------
    # Draw visible "potholes" on the lane (purely visual; no physics)
    # --------------------------------------------------------------------------
    pothole_centers = []
    lateral_offsets = [-0.7, 0.0, 0.7]   # across the lane
    length_along = 1.6                    # meters
    width_across = 1.0
    z_on_surface = 0.02                   # lift a hair so it isn't z-fighting

    for off in lateral_offsets:
        center = carla.Location(
            x=row_origin.x + lane_right.x * off,
            y=row_origin.y + lane_right.y * off,
            z=row_origin.z + z_on_surface
        )
        draw_pothole_box(world, center, size_xy=(length_along, width_across))
        pothole_centers.append(center)

    # Start autopilot
    tm = client.get_trafficmanager()
    # Reduce TM caution so we drive through the visuals with decent speed
    tm.ignore_vehicles_percentage(vehicle, 100)
    tm.ignore_signs_percentage(vehicle, 100)
    tm.ignore_lights_percentage(vehicle, 100)
    tm.set_vehicle_percentage_speed_difference(vehicle, -20)  # ~20% faster
    vehicle.set_autopilot(True, tm.get_port())

    print("Running autopilot for 20 seconds...")

    # Trigger once when front axle reaches the center pothole
    triggered = False
    trigger_radius = 1.8  # meters

    # front axle estimate (distance from actor origin)
    front_axle_offset = 1.3

    for _ in range(int(20 / settings.fixed_delta_seconds)):
        world.tick()
        publish_pose(vehicle)

        if not triggered:
            v_tf = vehicle.get_transform()
            v_loc = v_tf.location
            v_fwd = v_tf.get_forward_vector()
            front_loc = carla.Location(
                x=v_loc.x + v_fwd.x * front_axle_offset,
                y=v_loc.y + v_fwd.y * front_axle_offset,
                z=v_loc.z
            )

            # use the middle pothole center as trigger target
            c = pothole_centers[1]
            dist = math.hypot(front_loc.x - c.x, front_loc.y - c.y)
            speed = vehicle.get_velocity()
            speed_mps = (speed.x**2 + speed.y**2 + speed.z**2) ** 0.5

            if dist <= trigger_radius:
                world.debug.draw_string(c, "HIT", draw_shadow=False, color=carla.Color(255,255,0), life_time=2.0)
                print(f"[SYNTH] Injecting IMU burst at dist={dist:.2f} m, speed={speed_mps:.2f} m/s")
                inject_imu_burst(0.4)
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
