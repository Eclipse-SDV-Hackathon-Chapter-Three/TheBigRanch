# Python scripts using CARLA Client API

## zenoh_vehicle.py

A **utility class library** for vehicle control abstraction and integration:

- CarlaUtils: Provides helper functions for clamping vehicle control values (throttle, steering, brake)
- ZenohVehicle: A wrapper class that bridges PID control with CARLA vehicle commands
- Zenoh integration: Subscribes to actuation commands and publishes vehicle status (brake, speed)
- Control conversion: Converts single actuation value (-1.0 to 1.0) into separate throttle/brake commands
- Library component: Designed to be imported and used by other vehicle control applications

## automatic_control_zenoh.py

An **autonomous vehicle control system** identical to the previous version:

- AI agents: Implements autonomous driving with Basic, Behavior, and Constant Velocity agents
- Zenoh publishing: Publishes vehicle speed data to `ego_vehicle/speed` topic
- Path planning: Automatically navigates between random destinations
- Loop mode: Continuously sets new targets after reaching destinations
- Fully autonomous: No manual input required

## manual_control_zenoh.py

A **manual vehicle control interface** identical to the previous version:

- Interactive control: Keyboard/mouse control using pygame (WASD keys)
- Zenoh publishing: Publishes manual control inputs (throttle, steering, brake) to Zenoh topics
- Zenoh subscribing: Listens for cruise control engagement commands
- Visual interface: Provides HUD with telemetry, camera views, and sensor data
- Manual driving: Human operator directly controls the ego vehicle
