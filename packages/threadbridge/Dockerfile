# Build environment for the threadbridge packages: Debian bullseye, so the
# binaries need no newer glibc than OSMC on the Vero V (armhf) ships, and run
# on later Debian-based arm64 systems too. Builds armhf and arm64 natively or
# across, whichever the build machine is.
FROM debian:bullseye@sha256:6f519a81440354a85eb592c5f32109ab80605f6b892455983a6f618bf87fabe9

# bullseye's mirrors are moving to the archive and serve indexes whose files
# are gone; the snapshot the image was made from has both, and stays put.
# On an arm64 machine the native compiler builds arm64; elsewhere it takes a
# cross compiler.
RUN sed -i -e '/^deb /d' -e 's/^# deb /deb /' /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && if [ "$(dpkg --print-architecture)" = arm64 ]; then arm64=build-essential; else arm64=crossbuild-essential-arm64; fi \
    && apt-get install -y --no-install-recommends \
        crossbuild-essential-armhf "$arm64" cmake ninja-build git ca-certificates pkg-config \
        qemu-user-static python3 \
    && rm -rf /var/lib/apt/lists/*
