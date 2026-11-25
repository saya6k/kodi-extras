#!/bin/sh
# Builds the OSMC (Vero V) package into packages/threadbridge/out.
# Run it in the image built from this directory's Dockerfile:
#
#   docker build -t threadbridge-armhf packages/threadbridge
#   docker run --rm -v "$PWD":/work -w /work threadbridge-armhf packages/threadbridge/build.sh
set -eu
cd "$(dirname "$0")"

version=0.1.0
out=out
. ./otbr-options

fetch_otbr
# shellcheck disable=SC2086
cmake -S "$OTBR_SRC" -B build/armhf -GNinja -DCMAKE_TOOLCHAIN_FILE="$PWD/armhf.cmake" $OTBR_OPTIONS
cmake --build build/armhf --target otbr-agent ot-ctl

stage=$(mktemp -d)
cp -R deb "$stage/deb"
find "$stage" -name .DS_Store -delete
sed -i "s/@VERSION@/$version/" "$stage/deb/DEBIAN/control"
sed -i "s/@OTBR_TAG@/$OTBR_TAG/" "$stage/deb/DEBIAN/control"
install -D -m 755 build/armhf/src/agent/otbr-agent "$stage/deb/usr/sbin/otbr-agent"
install -D -m 755 build/armhf/third_party/openthread/repo/src/posix/ot-ctl "$stage/deb/usr/sbin/ot-ctl"
arm-linux-gnueabihf-strip "$stage/deb/usr/sbin/otbr-agent" "$stage/deb/usr/sbin/ot-ctl"

"$stage/deb/usr/sbin/otbr-agent" --version

rm -rf "$out"
mkdir -p "$out"
dpkg-deb --root-owner-group --build "$stage/deb" "$out/threadbridge_${version}_armhf.deb"
rm -rf "$stage"
ls -l "$out"
