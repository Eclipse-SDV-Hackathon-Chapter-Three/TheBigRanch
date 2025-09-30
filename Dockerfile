FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    curl \
    bash \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sfL https://github.com/eclipse-ankaios/ankaios/releases/download/v0.6.0/install.sh | INSTALL_ANK_SERVER_RUST_LOG=debug INSTALL_ANK_AGENT_RUST_LOG=info bash -s -- -t both

ENV PATH="/root/.local/bin:$PATH"

EXPOSE 25551

CMD ["ank-server"]