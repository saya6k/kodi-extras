#!/bin/sh
# Builds the OSMC (Vero V) package and the Kodi add-on into packages/atmos67/out.
# Run it in the image built from this directory's Dockerfile, with the atmos67
# repository mounted at /atmos67 (atmos67-source):
#
#   docker build -t atmos67-armhf packages/atmos67
#   docker run --rm -v "$PWD":/work -v ~/Projects/atmos67:/atmos67:ro -w /work atmos67-armhf packages/atmos67/build.sh
#
# The tests run the armhf binary, so the kernel needs qemu registered for
# 32-bit ARM (Docker Desktop has it; elsewhere
# `docker run --privileged --rm tonistiigi/binfmt --install arm`).
set -eu
cd "$(dirname "$0")"

version=0.1.0
target=armv7-unknown-linux-gnueabihf
out=out
. ./atmos67-source

fetch_atmos67
export CARGO_TARGET_DIR="$PWD/build/target" CARGO_HOME="${CARGO_HOME:-$PWD/build/cargo-home}"
(cd "$ATMOS67_SRC" && cargo test --release --target "$target" && cargo build --release --target "$target")

# Assembled off the bind mount, where sed -i fails.
stage=$(mktemp -d)
cp -R deb "$stage/deb"
cp -R ../../addons/service.atmos67 "$stage/service.atmos67"
find "$stage" -name .DS_Store -delete
find "$stage" -name __pycache__ -prune -exec rm -rf {} +
sed -i "s/@VERSION@/$version/" "$stage/deb/DEBIAN/control"

install -D -m 755 "$CARGO_TARGET_DIR/$target/release/atmos67" "$stage/deb/usr/bin/atmos67"
arm-linux-gnueabihf-strip "$stage/deb/usr/bin/atmos67"
mkdir -p "$out"
rm -f "$out"/atmos67_*_armhf.deb "$out"/service.atmos67-*.zip
dpkg-deb --root-owner-group --build "$stage/deb" "$out/atmos67_${version}_armhf.deb"
(cd "$stage" && zip -qr service.zip service.atmos67)
cp "$stage/service.zip" "$out/service.atmos67-$version.zip"
rm -rf "$stage"
ls -l "$out"
