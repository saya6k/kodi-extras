# A native build of otbr-agent and a simulated RCP behind a pty, to run the
# package's scripts and the add-on's REST client against a real agent.
FROM debian:bullseye@sha256:6f519a81440354a85eb592c5f32109ab80605f6b892455983a6f618bf87fabe9

RUN sed -i -e '/^deb /d' -e 's/^# deb /deb /' /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build git ca-certificates pkg-config \
        iproute2 iptables ipset kmod procps socat python3 \
    && rm -rf /var/lib/apt/lists/*
