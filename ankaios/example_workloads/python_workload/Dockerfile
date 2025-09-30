# -------------------------
# Stage 1: Python build
# -------------------------
FROM python:3.12-slim-bookworm as python-builder

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py ./
COPY . ./
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    curl \
    bash \
    ca-certificates \
    podman \
    jq \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sfL https://github.com/eclipse-ankaios/ankaios/releases/download/v0.6.0/install.sh | INSTALL_ANK_SERVER_RUST_LOG=debug INSTALL_ANK_AGENT_RUST_LOG=info bash -s -- -t both

ENV PATH="/root/.local/bin:$PATH"

# Configure podman for rootless operation
RUN echo 'unqualified-search-registries = ["docker.io"]' > /etc/containers/registries.conf && \
    echo '[containers]' > /etc/containers/containers.conf && \
    echo 'cgroup_manager = "cgroupfs"' >> /etc/containers/containers.conf

COPY hpc_variant/ankaios/state.yaml /ankaios/state.yaml
COPY hpc_variant/samples/ankaios_provider/test_ankaios_provider.sh /ankaios/test_ankaios_provider.sh
COPY hpc_variant/samples/ankaios_provider/target.json /ankaios/target.json

RUN chmod +x /ankaios/test_ankaios_provider.sh

EXPOSE 25551

CMD ["sh", "-c", "ank-server & ank-agent & sleep 5 && ank apply /ankaios/state.yaml & wait"]
