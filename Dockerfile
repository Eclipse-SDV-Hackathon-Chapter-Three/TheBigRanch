FROM ubuntu:22.04

# --- Install system dependencies and curl ---
RUN apt-get update && apt-get install -y \
    curl \
    bash \
    ca-certificates \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    python3-dev \
    libffi-dev \
    libssl-dev \
    libxerces-c-dev \
    && rm -rf /var/lib/apt/lists/*


# --- Add deadsnakes PPA and install Python 3.7 + pip ---
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.7 python3.7-distutils && \
    curl -sS  https://bootstrap.pypa.io/pip/3.7/get-pip.py  | python3.7

# --- Install Ankaios (server + agent) ---
RUN curl -sfL https://github.com/eclipse-ankaios/ankaios/releases/download/v0.6.0/install.sh | \
    INSTALL_ANK_SERVER_RUST_LOG=debug INSTALL_ANK_AGENT_RUST_LOG=info bash -s -- -t both

# copy src code to docker
COPY python /home/app/python
COPY requirements.txt /home/app/python

RUN pip install -r /home/app/python/requirements.txt

# --- Add pip and ank to PATH ---
ENV PATH="/root/.local/bin:$PATH"

# --- Expose Ankaios port ---
EXPOSE 25551

# copy workload to container
COPY big-ranch.yaml /root/workload.yaml

# --- Run the Ankaios server by default ---
CMD ["ank-server"]

#runs workload
COPY ankaios/entrypoint.sh /root/entrypoint.sh
RUN chmod +x /root/entrypoint.sh
