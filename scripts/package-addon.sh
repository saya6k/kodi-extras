#!/bin/sh
# Zips a Kodi add-on from addons/ for installing from a zip file.
#
#   scripts/package-addon.sh script.service.threadbridge   # → dist/<id>-<version>.zip
set -eu
cd "$(dirname "$0")/.."

id=${1:?usage: $0 ADDON_ID}
[ -f "addons/$id/addon.xml" ] || { echo "no add-on addons/$id" >&2; exit 1; }
version=$(sed -n 's/.*<addon [^>]*version="\([^"]*\)".*/\1/p' "addons/$id/addon.xml")

mkdir -p dist
zip=$PWD/dist/$id-$version.zip
rm -f "$zip"
(cd addons && zip -qr "$zip" "$id" -x '*/__pycache__/*' '*.pyc' '*/.DS_Store' '*/.gitkeep')
echo "$zip"
