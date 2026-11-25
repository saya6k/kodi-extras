#!/bin/sh
# Writes the package's copyright file: the license of each component built
# into otbr-agent and ot-ctl, taken from the source the package is built
# from, so the notices always match the code.
#
#   copyright.sh OTBR_SRC OUTPUT
set -eu
src=$1
ot=$src/third_party/openthread/repo
mbedtls=$ot/third_party/mbedtls/repo
here=$(dirname "$0")

section() {
    printf '\n%s\n%s\n\n' "$1" "$(printf '%s' "$1" | sed 's/./=/g')"
}

# The leading comment of each TCPlp file from FreeBSD, once per distinct
# text: those files keep their own copyright lines and conditions.
tcplp_notices() {
    find "$ot/third_party/tcplp/bsdtcp" -name '*.[ch]' | sort | while read -r file; do
        awk 'NR == 1 && !/^\/\*/ { exit } { print } /\*\// { exit }' "$file"
        printf '\036'
    done | awk 'BEGIN { RS = "\036" } NF && !seen[$0]++ { print; print "" }'
}

{
    echo "threadbridge: otbr-agent and ot-ctl from ot-br-posix, packaged by kodi-extras."
    echo "Each component below keeps its own license."

    section "threadbridge packaging (scripts, service, configuration): MIT"
    cat "$here/../../LICENSE"

    section "ot-br-posix: BSD-3-Clause"
    cat "$src/LICENSE"

    section "OpenThread: BSD-3-Clause"
    cat "$ot/LICENSE"

    section "TCPlp (part of OpenThread): BSD-3-Clause and BSD-style licenses of the FreeBSD files"
    sed -n '/^## License/,$p' "$ot/third_party/tcplp/README.md"
    echo
    tcplp_notices

    section "Mbed TLS, with p256-m and Everest: Apache-2.0 (chosen of Apache-2.0 OR GPL-2.0-or-later)"
    echo "Everest (3rdparty/everest): Copyright (c) INRIA and Microsoft Corporation, Apache-2.0."
    echo "p256-m (3rdparty/p256-m): Copyright Manuel Pégourié-Gonnard, Apache-2.0 OR GPL-2.0-or-later."
    echo
    cat "$mbedtls/LICENSE"

    section "cJSON: MIT"
    cat "$src/third_party/cJSON/repo/LICENSE"

    section "cpp-httplib: MIT"
    cat "$src/third_party/cpp-httplib/repo/LICENSE"
} > "$2"
