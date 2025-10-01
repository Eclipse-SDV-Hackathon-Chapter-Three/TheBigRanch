#!/usr/bin/env python3
import carla
import random
import time

def spawn_pothole(world, bp_lib, location, scale=(2.0, 2.0, 0.08)):
    """
    Spawn a thin cube collider to simulate a pothole.
    """
    cube_bp = bp_lib.find("static.prop.cube")
    cube_bp.set_attribute("scale", f"{scale[0]},{scale[1]},{scale[2]}")

    transform = carla.Transform(location, carla.Rotation())
    pothole = world.try_spawn_actor(cube_bp, transform)
    if pothole:
        try:
            pothole.set_simulate_physics(True)
            pothole.set_enable_gravity(True)
        except:
            pass
        print(f"Spawned pothole at {location}")
    else:
        print("Failed to spawn pothole")
    return pothole

def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

    # Pick a random road spawn point for the vehicle
    spawn_point = random.choice(world.get_map().get_spawn_points())

    # Spawn the vehicle
    vehicle_bp = random.choice(bp_lib.filter("vehicle.*"))
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
    if vehicle is None:
        print("Failed to spawn vehicle")
        return
    print(f"Spawned vehicle {vehicle.type_id} at {spawn_point.location}")

    # Move spectator camera above vehicle
    spectator = world.get_spectator()
    spectator.set_transform(carla.Transform(
        spawn_point.location + carla.Location(z=50),
        carla.Rotation(pitch=-90)
    ))

    # Spawn potholes in front of the vehicle
    potholes = []
    for i in range(5):
        offset = (i + 1) * 10.0  # 10m apart
        loc = carla.Location(
            x=spawn_point.location.x + offset,
            y=spawn_point.location.y,
            z=spawn_point.location.z + 0.05
        )
        pothole = spawn_pothole(world, bp_lib, loc)
        if pothole:
            potholes.append(pothole)

    # Put vehicle on autopilot
    vehicle.set_autopilot(True)
    print("Simulation running for 20 seconds..")
    # Let simulation run
    time.sleep(20)

    # Cleanup
    print("Cleaning up...")
    vehicle.destroy()
    for p in potholes:
        p.destroy()
    print("Done.")

if __name__ == "__main__":
    main()
