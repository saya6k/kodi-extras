"""What the add-on's scripts share, without Kodi: the service configuration
built from the settings, distances turned into delays, Kodi's volume in dB,
and the atmos67 sender's control socket."""

import json
import os
import socket

CONTROL = "/run/atmos67/control"
MODES = ["off", "manual", "auto"]
GROUPS = ["front", "center", "surround", "back", "top"]
SPEED_OF_SOUND = 343.0
# Kodi's volume from 1% to 100% spans this many dB below the maximum.
VOLUME_RANGE_DB = 60.0
# The sender's volume while Kodi is muted.
MUTED_DB = -120.0
# What the sender cannot see: the loopback capture (10 ms periods) and the
# decoder's access units (up to 32 ms for Dolby Digital). An estimate.
DECODE_ALLOWANCE_MS = 40.0


def quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def delays_ms(distances):
    """Delays that bring every speaker to the farthest one's arrival."""
    if not distances:
        return {}
    farthest = max(distances.values())
    return {role: round((farthest - d) / SPEED_OF_SOUND * 1000.0, 3) for role, d in distances.items()}


def volume_db(percent, muted, max_db):
    """Kodi's volume (0 to 100 %) as the sender's volume in dB."""
    if muted or percent <= 0:
        return MUTED_DB
    return round(max_db - VOLUME_RANGE_DB * (1.0 - percent / 100.0), 2)


def answer_value(answer):
    """The value of a sender answer `ok <value>`."""
    status, _, value = answer.partition(" ")
    if status != "ok" or not value:
        raise ValueError(answer)
    return float(value)


def answer_json(answer):
    """The JSON of a sender answer `ok {...}`."""
    status, _, value = answer.partition(" ")
    if status != "ok" or not value:
        raise ValueError(answer)
    return json.loads(value)


def av_offset(sender_ms, receiver_ms, trim_ms):
    """Kodi's audio offset in seconds for audio that arrives this late.

    Negative: Kodi holds the picture back until the sound catches up."""
    return -round((sender_ms + DECODE_ALLOWANCE_MS + receiver_ms + trim_ms) / 1000.0, 3)


def pairs(values):
    return " ".join(f"{key}={value}" for key, value in values.items())


def read_levels(profile):
    """Per-speaker trims (dB) and distances (m): {"L": {"trim": -1.0, "distance": 3.2}}."""
    try:
        with open(os.path.join(profile, "levels.json"), encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, ValueError):
        return {}


def write_levels(profile, levels):
    os.makedirs(profile, exist_ok=True)
    with open(os.path.join(profile, "levels.json"), "w", encoding="utf-8") as file:
        json.dump(levels, file, indent=1, sort_keys=True)


CHANNELS_PER_STREAM = 8


def streams_path(profile):
    return os.path.join(profile, "streams.json")


def read_streams(profile):
    """The stream plan: [{"name", "address", "channels": [speaker names]}], or [] for 8 channels a stream."""
    try:
        with open(streams_path(profile), encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, ValueError):
        return []


def write_streams(profile, streams):
    os.makedirs(profile, exist_ok=True)
    if streams:
        with open(streams_path(profile), "w", encoding="utf-8") as file:
            json.dump(streams, file, indent=1)
    elif os.path.exists(streams_path(profile)):
        os.remove(streams_path(profile))


def address_after(address, steps):
    parts = [int(p) for p in address.split(".")]
    value = sum(p << (8 * (3 - i)) for i, p in enumerate(parts)) + steps
    return ".".join(str((value >> (8 * (3 - i))) & 255) for i in range(4))


def default_streams(outputs, first):
    """What the sender does without a plan: 8 channels a stream, addresses counting up."""
    streams = []
    for index in range(0, len(outputs), CHANNELS_PER_STREAM):
        channels = outputs[index:index + CHANNELS_PER_STREAM]
        streams.append({"name": f"atmos67 ch {index + 1}-{index + len(channels)}",
                        "address": address_after(first, index // CHANNELS_PER_STREAM), "channels": channels})
    return streams


def stream_problem(stream):
    """Why the sender would refuse `stream`, or None."""
    if len(stream["channels"]) > CHANNELS_PER_STREAM:
        return "channels"
    try:
        parts = [int(p) for p in stream["address"].split(".")]
    except ValueError:
        return "address"
    if len(parts) != 4 or not 224 <= parts[0] <= 239 or any(not 0 <= p <= 255 for p in parts):
        return "address"
    return None


def unassigned(outputs, streams):
    used = {channel for stream in streams for channel in stream["channels"]}
    return [output for output in outputs if output not in used]


def auto_design(profile):
    return os.path.join(profile, "designs", "current")


def values(settings, levels, profile, volume, mode=None):
    """The service configuration for `settings` (Kodi's strings by id).

    `mode` overrides the setting, as the calibration does to measure."""
    if mode is None:
        mode = MODES[int(settings["mode"] or 0)]
    trims = {role: level["trim"] for role, level in sorted(levels.items()) if level.get("trim")}
    distances = {role: level["distance"] for role, level in levels.items() if level.get("distance") is not None}
    # A measured design has its speakers aligned already.
    delays = {} if mode == "auto" else {r: d for r, d in sorted(delays_ms(distances).items()) if d}
    crossover = {group: int(settings[f"xo_{group}"]) for group in GROUPS if int(settings[f"xo_{group}"] or 0) > 0}
    return {
        "LAYOUT": settings["layout"],
        "INTERFACE": settings["interface"],
        "ADDRESS": settings["address"],
        "PTP_DOMAIN": settings["ptp_domain"],
        "BUFFER_MS": settings["buffer_ms"],
        "MODE": mode,
        "SUBS": settings["subs"],
        "SLOPE": settings["slope"],
        "CROSSOVER": "" if mode == "measure" else pairs(crossover),
        "TRIMS": "" if mode == "measure" else pairs(trims),
        "DELAYS": "" if mode == "measure" else pairs(delays),
        "AUTO_DESIGN": auto_design(profile),
        "STREAMS": streams_path(profile) if read_streams(profile) else "",
        "VOLUME_DB": volume,
    }


def config_text(values):
    return "".join(f"{key}={quote(value)}\n" for key, value in values.items())


def replace_volume(text, volume):
    """`text`, a configuration from config_text, with its volume set to `volume`."""
    return "".join(f"VOLUME_DB={quote(volume)}\n" if line.startswith("VOLUME_DB=") else line + "\n"
                   for line in text.splitlines())


def command(line, path=CONTROL, timeout=5.0):
    """Sends one command to the sender and returns its answer."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect(path)
        connection.sendall((line + "\n").encode())
        answer = b""
        while not answer.endswith(b"\n"):
            chunk = connection.recv(256)
            if not chunk:
                break
            answer += chunk
    return answer.decode().strip()


def progress(line):
    """The step and detail of a line `atmos67 calibrate` prints, or None."""
    try:
        event = json.loads(line)
    except ValueError:
        return None
    return event.get("step"), event.get("detail", "")
