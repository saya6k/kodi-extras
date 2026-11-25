# Cross-build environment for OSMC on the Vero V: Debian bullseye with a
# 32-bit armhf userland. Building on bullseye keeps the binary's glibc
# requirement at the version OSMC ships.
FROM rust:1.95-bullseye

# bullseye-security has left the mirrors; the release archive is enough to build.
RUN sed -i '/security/d' /etc/apt/sources.list \
    && dpkg --add-architecture armhf && apt-get update && apt-get install -y --no-install-recommends \
        crossbuild-essential-armhf clang libclang-dev pkg-config qemu-user-static zip python3 \
    && rm -rf /var/lib/apt/lists/* \
    && rustup target add armv7-unknown-linux-gnueabihf

# The toolchain atmos67's rust-toolchain.toml pins (keep the two equal); the image's own
# Rust stays for its bullseye base.
ARG RUST_TOOLCHAIN=1.100.0
RUN rustup toolchain install ${RUST_TOOLCHAIN} --profile minimal -c clippy -t armv7-unknown-linux-gnueabihf

# A static libavcodec with only the decoders atmos67 uses, and libswresample
# for PCM that is not at 48 kHz, so the package does not depend on the
# FFmpeg version of the installed system.
ARG FFMPEG_VERSION=8.0
RUN curl -fsSL https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz | tar xJ -C /tmp \
    && cd /tmp/ffmpeg-${FFMPEG_VERSION} \
    && ./configure --prefix=/opt/ffmpeg-armhf \
        --enable-cross-compile --cross-prefix=arm-linux-gnueabihf- --arch=armv7-a --target-os=linux \
        --enable-static --disable-shared --enable-pic \
        --disable-everything --disable-programs --disable-doc --disable-network \
        --disable-avdevice --disable-avfilter --disable-swscale \
        --enable-decoder=ac3,eac3,dca \
    && make -j"$(nproc)" install \
    && rm -rf /tmp/ffmpeg-${FFMPEG_VERSION} \
    # ffmpeg-sys-next's Vulkan binding stub only compiles for 64-bit targets;
    # without this header it leaves the unused Vulkan bindings out.
    && rm /opt/ffmpeg-armhf/include/libavutil/hwcontext_vulkan.h

ENV PKG_CONFIG_ALLOW_CROSS=1 \
    PKG_CONFIG_ALL_STATIC=1 \
    PKG_CONFIG_PATH=/opt/ffmpeg-armhf/lib/pkgconfig \
    CARGO_TARGET_ARMV7_UNKNOWN_LINUX_GNUEABIHF_LINKER=arm-linux-gnueabihf-gcc \
    QEMU_LD_PREFIX=/usr/arm-linux-gnueabihf \
    BINDGEN_EXTRA_CLANG_ARGS_armv7_unknown_linux_gnueabihf="--sysroot=/usr/arm-linux-gnueabihf -I/usr/arm-linux-gnueabihf/include"
WORKDIR /work
