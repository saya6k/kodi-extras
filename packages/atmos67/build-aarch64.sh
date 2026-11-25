#!/bin/sh
# Builds the static 64-bit atmos67 into packages/atmos67/out, to try on the
# Vero V in place of the packaged 32-bit /usr/bin/atmos67 (its kernel is
# arm64 under the armhf userland). Run it on an arm64 Linux host, in the image
# built from Dockerfile.aarch64, with the atmos67 repository mounted at /atmos67:
#
#   docker build -t atmos67-aarch64 -f packages/atmos67/Dockerfile.aarch64 packages/atmos67
#   docker run --rm -v "$PWD":/work -v ~/Projects/atmos67:/atmos67:ro -w /work atmos67-aarch64 packages/atmos67/build-aarch64.sh
set -eu
cd "$(dirname "$0")"

version=0.1.0
target=aarch64-unknown-linux-musl
out=out
. ./atmos67-source

fetch_atmos67
export CARGO_TARGET_DIR="$PWD/build/target" CARGO_HOME="${CARGO_HOME:-$PWD/build/cargo-home}"
(cd "$ATMOS67_SRC" && cargo test --release --target "$target" && cargo build --release --target "$target")

mkdir -p "$out"
install -m 755 "$CARGO_TARGET_DIR/$target/release/atmos67" "$out/atmos67-$version-aarch64"
strip "$out/atmos67-$version-aarch64"
file "$out/atmos67-$version-aarch64"
ls -l "$out"
