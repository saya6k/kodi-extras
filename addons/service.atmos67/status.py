"""What the atmos67 service is doing, run from the add-on's settings."""

import subprocess

import xbmcgui

import common
import service


def text(string_id, *args):
    value = service.addon().getLocalizedString(string_id)
    return value % args if args else value


def show():
    addon = service.addon()
    active = subprocess.run(["systemctl", "is-active", "atmos67"], capture_output=True, text=True).stdout.strip()
    mode = [text(32052), text(32053), text(32054)][int(addon.getSetting("mode") or 0)]
    lines = [text(32141, active or "?"), text(32142, mode)]
    try:
        status = common.answer_json(common.command("status"))
    except (OSError, ValueError):
        lines.append(text(32143))
        xbmcgui.Dialog().textviewer(text(32140), "\n".join(lines))
        return
    lines += [
        text(32144, status["grandmaster"], status["domain"]),
        text(32145) if status["playing"] else text(32146),
        text(32147) if status["muted"] else text(32148, status["volume_db"]),
        text(32149, status["latency_ms"]),
        text(32150, status["send_errors"]),
        "",
        text(32151, status["source"]),
    ]
    for stream in status["streams"]:
        lines.append(f"  {stream['name']}   {stream['address']}   {' '.join(stream['channels'])}")
    xbmcgui.Dialog().textviewer(text(32140), "\n".join(lines))


if __name__ == "__main__":
    show()
