"""Dante receivers subscribed to the service's streams, run from the add-on's
settings, through `atmos67 dante` (netaudio's reverse-engineered Dante
control: not yet tried on a Dante device)."""

import json
import subprocess

import xbmcgui

import common
import service

ATMOS67 = "/usr/bin/atmos67"


def text(string_id, *args):
    value = service.addon().getLocalizedString(string_id)
    return value % args if args else value


def dante(args, progress=None):
    """Runs `atmos67 dante …`; its JSON lines, or None after showing the error.
    `progress`, a dialog shown meanwhile, is closed before anything else shows."""
    try:
        result = subprocess.run([ATMOS67, "dante"] + args, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        result = None
    finally:
        if progress is not None:
            progress.close()
    if result is None:
        xbmcgui.Dialog().ok(text(32160), text(32166) + "\ntimed out")
        return None
    if result.returncode != 0:
        xbmcgui.Dialog().ok(text(32160), text(32166) + "\n" + result.stderr.strip()[-400:])
        return None
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def where(device):
    """The flags naming where `list` found the device, so it is not looked for again."""
    flags = ["--device", device["name"], "--ipv4", device["ipv4"], "--port", str(device["port"])]
    return flags + (["--protocol", device["protocol"]] if device.get("protocol") else [])


def connect(device):
    try:
        streams = common.answer_json(common.command("status"))["streams"]
    except (OSError, ValueError, KeyError):
        xbmcgui.Dialog().ok(text(32160), text(32143))
        return
    rows = [f"{s['name']}   {' '.join(s['channels'])}" for s in streams]
    chosen = xbmcgui.Dialog().select(text(32163), rows)
    if chosen < 0:
        return
    stream = streams[chosen]
    first = xbmcgui.Dialog().numeric(0, text(32164), "1")
    if not first or int(first) < 1:
        return
    done = dante(["connect"] + where(device) + ["--stream", stream["name"],
                  "--control", common.CONTROL, "--first-channel", first])
    if done is not None:
        last = int(first) + len(stream["channels"]) - 1
        xbmcgui.Dialog().ok(text(32160), text(32165, stream["name"], device["name"], int(first), last))


def manage():
    dialog = xbmcgui.DialogProgress()
    dialog.create(text(32160), text(32161))
    devices = dante(["list", "--seconds", "3"], dialog)
    if devices is None:
        return
    if not devices:
        xbmcgui.Dialog().ok(text(32160), text(32162))
        return
    chosen = xbmcgui.Dialog().select(text(32160), [f"{d['name']}   {d['ipv4']}" for d in devices])
    if chosen < 0:
        return
    device = devices[chosen]
    action = xbmcgui.Dialog().select(device["name"], [text(32167), text(32168), text(32169)])
    if action == 0:
        connect(device)
    elif action in (1, 2):
        flag = [] if action == 1 else ["--off"]
        if dante(["aes67"] + where(device) + flag) is not None:
            xbmcgui.Dialog().ok(text(32160), text(32170))


if __name__ == "__main__":
    manage()
