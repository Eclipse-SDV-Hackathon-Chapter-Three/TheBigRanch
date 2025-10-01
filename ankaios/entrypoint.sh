#!/bin/bash
set -e

# Start ank-server in the background
ank-server &

# Save ank-server PID
ANK_PID=$!

# Wait for ank-server to be ready (adjust sleep or implement health check)
sleep 5

# Apply workloads (adjust path as needed)
ankaios workload apply -f /root/workload.yaml

# Wait on ank-server to keep container alive
wait $ANK_PID
