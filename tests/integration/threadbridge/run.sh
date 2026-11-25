#!/bin/sh
# Runs in the image built from this directory's Dockerfile, privileged (TUN,
# netfilter) and with IPv6, with the repository at /work:
#
#   docker build -t threadbridge-test tests/integration/threadbridge
#   docker run --rm --privileged --sysctl net.ipv6.conf.all.disable_ipv6=0 -v "$PWD":/work threadbridge-test sh /work/tests/integration/threadbridge/run.sh
set -eu
cd /work/packages/threadbridge
. ./otbr-options

fetch_otbr
# shellcheck disable=SC2086
cmake -S "$OTBR_SRC" -B build/native -GNinja $OTBR_OPTIONS >/dev/null
cmake --build build/native --target otbr-agent ot-ctl
cmake -S "$OTBR_SRC/third_party/openthread/repo" -B build/sim-rcp -GNinja \
    -DOT_PLATFORM=simulation -DOT_COMPILE_WARNING_AS_ERROR=OFF \
    -DOT_FTD=OFF -DOT_MTD=OFF -DOT_RCP=ON -DOT_APP_CLI=OFF -DOT_APP_NCP=OFF -DOT_APP_RCP=ON >/dev/null
cmake --build build/sim-rcp --target ot-rcp

install -m 755 build/native/src/agent/otbr-agent build/native/third_party/openthread/repo/src/posix/ot-ctl /usr/sbin/
mkdir -p /usr/lib/threadbridge
install -m 755 deb/usr/lib/threadbridge/* /usr/lib/threadbridge/

# The simulated RCP where a USB dongle would be. The container's eth0 is the
# backbone.
socat PTY,link=/dev/ttyRCP0,raw,echo=0 EXEC:"$PWD/build/sim-rcp/examples/apps/ncp/ot-rcp 1" &
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -e /dev/ttyRCP0 ] && break; sleep 1; done
mkdir -p /dev/serial/by-id
ln -s /dev/ttyRCP0 /dev/serial/by-id/usb-simulated-rcp-if00

set -a
. deb/etc/threadbridge/threadbridge.conf
RADIO_BAUDRATE=115200
RADIO_FLOW_CONTROL=0
BACKBONE_IF=eth0
set +a
/usr/lib/threadbridge/threadbridge-run &
agent=$!

status=0
python3 /work/tests/integration/threadbridge/test_live.py -v || status=1

echo "--- firewall while running"
ip6tables -S OTBR_FORWARD_INGRESS || status=1
ipset list -n | grep -q otbr-ingress-allow-dst || status=1
iptables -t nat -S POSTROUTING | grep -q MASQUERADE || status=1
pgrep -a otbr-agent || status=1

kill "$agent"
wait "$agent" || true
/usr/lib/threadbridge/threadbridge-firewall stop
echo "--- firewall after stop"
if ip6tables -S OTBR_FORWARD_INGRESS 2>/dev/null || ipset list -n | grep -q otbr \
    || iptables -t nat -S POSTROUTING | grep -q MASQUERADE; then
    echo "rules left behind"
    status=1
fi
echo "status=$status"
exit $status
