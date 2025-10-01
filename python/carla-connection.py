import sys
import time
import math
import zenoh

# Add CARLA egg to PYTHONPATH
# Replace with your actual path to carla-<version>.egg if needed
try:
    sys.path.append('path/to/carla-<version>.egg')  # Only if not installed via pip
    import carla
except ImportError:
    print("CARLA egg not found. Please update the sys.path line.")
    sys.exit(1)

def get_speed(velocity):
    """Calculate speed in m/s from velocity vector"""
    return math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)

def main():
    try:
        # Connect to CARLA server
        client = carla.Client("localhost", 2000)
        client.set_timeout(5.0)

        world = client.get_world()

        # Get all vehicles
        vehicles = world.get_actors().filter('vehicle.*')
        if not vehicles:
            print("No vehicles found in the simulation.")
            return

        # Pick the first vehicle
        vehicle = vehicles[0]
        print(f"Tracking vehicle: ID {vehicle.id}, Type {vehicle.type_id}\n")

        # Poll info every 0.5 seconds
        while True:
            session = zenoh.open({})

            # vehicle position topic
            vehicle_pose_topic = 'vehicle/pose'

            # raw IMU info
            vehicle_imu_raw_topic = 'vehicle/imu/raw'

            transform = vehicle.get_transform()
            velocity = vehicle.get_velocity()

            location = transform.location
            rotation = transform.rotation
            speed = get_speed(velocity)

            # Validate this if
            if (rotation.yaw < -2.0):
                # sends data to topics
                session.put(vehicle_pose_topic, location)
                session.put(vehicle_imu_raw_topic, rotation)

            print(f"Location: (X={location.x:.2f}, Y={location.y:.2f}, Z={location.z:.2f})")
            print(f"Rotation: (Pitch={rotation.pitch:.2f}, Yaw={rotation.yaw:.2f}, Roll={rotation.roll:.2f})")
            print(f"Speed: {speed:.2f} m/s")
            print("-" * 40)

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nExiting gracefully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
