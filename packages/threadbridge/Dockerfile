# Cross-build environment for OSMC on the Vero V: Debian bullseye with a
# 32-bit armhf userland. Building on bullseye keeps the binaries' glibc
# requirement at the version OSMC ships.
FROM debian:bullseye@sha256:6f519a81440354a85eb592c5f32109ab80605f6b892455983a6f618bf87fabe9

# bullseye's mirrors are moving to the archive and serve indexes whose files
# are gone; the snapshot the image was made from has both, and stays put.
RUN sed -i -e '/^deb /d' -e 's/^# deb /deb /' /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update && apt-get install -y --no-install-recommends \
        crossbuild-essential-armhf cmake ninja-build git ca-certificates pkg-config \
        qemu-user-static python3 \
    && rm -rf /var/lib/apt/lists/*

ENV QEMU_LD_PREFIX=/usr/arm-linux-gnueabihf
