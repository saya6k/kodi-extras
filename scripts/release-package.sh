#!/bin/sh
# Publishes a package's built .deb files as the GitHub release
# <package>-v<version>, made if missing, replacing files of the same name.
# Build first (see the package's docs); the version is build.sh's.
#
#   scripts/release-package.sh threadbridge
set -eu
cd "$(dirname "$0")/.."

package=${1:?usage: $0 PACKAGE}
[ -f "packages/$package/build.sh" ] || { echo "no package packages/$package" >&2; exit 1; }
version=$(sed -n 's/^version=//p' "packages/$package/build.sh")
tag=$package-v$version

set -- packages/"$package"/out/"${package}_${version}"_*.deb
[ -e "$1" ] || { echo "no packages/$package/out/${package}_${version}_*.deb; build it first" >&2; exit 1; }

if ! gh release view "$tag" >/dev/null 2>&1; then
    gh release create "$tag" --target main --title "$package $version" \
        --notes "OSMC (Vero V) and Debian packages of $package $version. Install with \`sudo apt install ./<file>.deb\`; see docs/$package.md."
fi
gh release upload "$tag" "$@" --clobber
gh release view "$tag" --json url,assets --jq '.url, (.assets[].name)'
