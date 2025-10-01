#!/usr/bin/env bash

podman run -i --rm --mount type=bind,src=../,dst=/root/sdv_lab docker.io/ubuntu:22.04 <<EOF

apt update
apt install -y git python3-pip sudo clang wget rsync curl
pip install rust-just


rm /root/.bashrc
touch /root/.bashrc
cd /root/sdv_lab
cd carla-setup
just make-carla

EOF

