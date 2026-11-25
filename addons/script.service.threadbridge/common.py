"""What the add-on's scripts share, without Kodi: the service configuration
built from the settings, the otbr-agent REST API, and checks of what the user
types."""

import json
import os
import re
import urllib.error
import urllib.request

BAUDRATES = ["115200", "230400", "460800", "921600"]
SERIAL_BY_ID = "/dev/serial/by-id"
SYS_NET = "/sys/class/net"
# Thread's own interface and ones a backbone never is.
NOT_BACKBONE = {"lo", "wpan0"}
# Thread 1.x joiner credentials: 6 to 32 of 0-9 and A-Z without I, O, Q and Z.
PSKD = re.compile(r"^[0-9A-HJ-NPR-Y]{6,32}$")
EUI64 = re.compile(r"^[0-9a-fA-F]{16}$")
NETWORK_NAME_BYTES = 16


def quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def flag(value):
    return "1" if str(value).lower() == "true" else "0"


def values(settings):
    """The service's environment from the add-on settings (Kodi's strings)."""
    baudrate = settings.get("baudrate") or "460800"
    return {
        "RADIO_DEVICE": settings.get("device", "").strip(),
        "RADIO_BAUDRATE": baudrate if baudrate in BAUDRATES else "460800",
        "RADIO_FLOW_CONTROL": flag(settings.get("flow_control", "true")),
        "BACKBONE_IF": settings.get("backbone", "").strip() or "eth0",
        "REST_ADDRESS": "0.0.0.0" if flag(settings.get("rest_public", "false")) == "1" else "127.0.0.1",
        "REST_PORT": str(int(settings.get("rest_port") or 8081)),
        "NAT64": flag(settings.get("nat64", "true")),
        "FIREWALL": flag(settings.get("firewall", "true")),
    }


def config_text(config):
    """`config` as a systemd EnvironmentFile."""
    return "".join(f"{key}={quote(value)}\n" for key, value in config.items())


def serial_devices(directory=SERIAL_BY_ID):
    """The serial devices by their stable names, which survive replugging."""
    try:
        return sorted(os.path.join(directory, name) for name in os.listdir(directory))
    except FileNotFoundError:
        return []


def network_interfaces(directory=SYS_NET):
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return []
    return sorted(name for name in names if name not in NOT_BACKBONE)


def valid_pskd(pskd):
    return bool(PSKD.match(pskd))


def valid_eui64(eui64):
    return bool(EUI64.match(eui64))


def normalize_dataset(text):
    """A dataset in TLV hex from what was pasted or read from a file, or None.

    Accepts whitespace and line breaks inside, and a `dataset` line as
    `ot-ctl dataset active -x` and Home Assistant print it."""
    hexdigits = re.sub(r"\s+", "", text)
    if hexdigits.lower().startswith("dataset"):
        hexdigits = hexdigits[len("dataset"):]
    if not hexdigits or len(hexdigits) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", hexdigits):
        return None
    return hexdigits.upper()


def valid_network_name(name):
    return 0 < len(name.encode("utf-8")) <= NETWORK_NAME_BYTES


class RestError(Exception):
    """The REST API answered with an error, or did not answer."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Rest:
    """The otbr-agent REST API on this box."""

    def __init__(self, port=8081, host="127.0.0.1", timeout=10):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    def request(self, method, path, body=None, content_type="application/json", accept="application/json"):
        data = None
        headers = {"Accept": accept}
        if body is not None:
            data = (json.dumps(body) if content_type == "application/json" else body).encode("utf-8")
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise RestError(error.code, error_message(error.read().decode("utf-8", "replace")) or error.reason)
        except (urllib.error.URLError, OSError) as error:
            raise RestError(None, str(getattr(error, "reason", error)))

    def json(self, method, path, body=None):
        _, text = self.request(method, path, body)
        return json.loads(text) if text.strip() else None

    def node(self):
        return self.json("GET", "/node")

    def state(self):
        return self.json("GET", "/node/state")

    def set_state(self, enabled):
        self.json("PUT", "/node/state", "enable" if enabled else "disable")

    def active_dataset(self):
        """The active dataset as JSON, or None when there is none."""
        return self.json("GET", "/node/dataset/active")

    def active_dataset_tlvs(self):
        status, text = self.request("GET", "/node/dataset/active", accept="text/plain")
        return text.strip() if status == 200 and text.strip() else None

    def set_active_dataset(self, dataset):
        """Writes the active dataset: a JSON object (keys left out get random
        values) or TLVs in hex. Thread must be disabled."""
        if isinstance(dataset, str):
            self.request("PUT", "/node/dataset/active", dataset, content_type="text/plain")
        else:
            self.request("PUT", "/node/dataset/active", dataset)

    def coprocessor_version(self):
        return self.json("GET", "/node/coprocessor/version")

    def commissioner_state(self):
        return self.json("GET", "/node/commissioner/state")

    def set_commissioner(self, enabled):
        self.json("PUT", "/node/commissioner/state", "enable" if enabled else "disable")

    def add_joiner(self, pskd, eui64=None, timeout_s=120):
        joiner = {"pskd": pskd, "timeout": timeout_s}
        joiner["joinerId"] = eui64.lower() if eui64 else "*"
        self.json("POST", "/node/commissioner/joiner", joiner)


def error_message(text):
    """The message of a REST error body ({"title": ..., "status": ..., "detail": ...})."""
    try:
        body = json.loads(text)
        return body.get("detail") or body.get("title") or text.strip()
    except (ValueError, AttributeError):
        return text.strip()


def replace_network(rest, dataset):
    """Leaves the current network, if any, and attaches with `dataset`."""
    rest.set_state(False)
    rest.set_active_dataset(dataset)
    rest.set_state(True)


def form_dataset(name, channel=None):
    """A new network's dataset; otbr-agent fills in random keys and IDs."""
    dataset = {"networkName": name}
    if channel:
        dataset["channel"] = int(channel)
    return dataset


def status_lines(node, dataset, coprocessor):
    """What the status dialog shows: (label key, value) pairs."""
    node = node or {}
    dataset = dataset or {}
    lines = [
        ("state", node.get("state", "")),
        ("network_name", node.get("networkName") or dataset.get("networkName", "")),
        ("channel", dataset.get("channel", "")),
        ("pan_id", f"0x{dataset['panId']:04x}" if isinstance(dataset.get("panId"), int) else ""),
        ("ext_pan_id", node.get("extPanId") or dataset.get("extPanId", "")),
        ("routers", node.get("routerCount", "")),
        ("rloc16", node.get("rloc16", "")),
        ("border_agent", node.get("baState", "")),
        ("coprocessor", coprocessor or ""),
    ]
    return [(key, str(value)) for key, value in lines if value != ""]
