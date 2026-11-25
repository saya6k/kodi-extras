#!/bin/sh
# Builds the threadbridge package for ARCH (armhf, the default, for OSMC on
# the Vero V; or arm64) into packages/threadbridge/out. Run it in the image
# built from this directory's Dockerfile:
#
#   docker build -t threadbridge-build packages/threadbridge
#   docker run --rm -v "$PWD":/work -w /work threadbridge-build packages/threadbridge/build.sh [ARCH]
set -eu
cd "$(dirname "$0")"

version=0.1.0
arch=${1:-armhf}
out=out
case "$arch" in
    armhf) triplet=arm-linux-gnueabihf ;;
    arm64) triplet=aarch64-linux-gnu ;;
    *) echo "usage: $0 [armhf|arm64]" >&2; exit 2 ;;
esac
. ./otbr-options

# A cross build unless the build machine is ARCH already.
toolchain=
[ "$(dpkg --print-architecture)" = "$arch" ] || toolchain="-DCMAKE_TOOLCHAIN_FILE=$PWD/$arch.cmake"

fetch_otbr
# shellcheck disable=SC2086
cmake -S "$OTBR_SRC" -B "build/$arch" -GNinja $toolchain $OTBR_OPTIONS
cmake --build "build/$arch" --target otbr-agent ot-ctl

stage=$(mktemp -d)
cp -R deb "$stage/deb"
find "$stage" -name .DS_Store -delete
sed -i -e "s/@VERSION@/$version/" -e "s/@ARCH@/$arch/" -e "s/@OTBR_TAG@/$OTBR_TAG/" "$stage/deb/DEBIAN/control"
install -D -m 755 "build/$arch/src/agent/otbr-agent" "$stage/deb/usr/sbin/otbr-agent"
install -D -m 755 "build/$arch/third_party/openthread/repo/src/posix/ot-ctl" "$stage/deb/usr/sbin/ot-ctl"
"$triplet-strip" "$stage/deb/usr/sbin/otbr-agent" "$stage/deb/usr/sbin/ot-ctl"

# Runs under qemu when the build machine is not ARCH.
QEMU_LD_PREFIX=/usr/$triplet "$stage/deb/usr/sbin/otbr-agent" --version

mkdir -p "$out"
rm -f "$out"/threadbridge_*_"$arch".deb
dpkg-deb --root-owner-group --build "$stage/deb" "$out/threadbridge_${version}_${arch}.deb"
rm -rf "$stage"
ls -l "$out"
