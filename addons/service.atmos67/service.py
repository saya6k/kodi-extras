"""Hands the add-on's settings to the atmos67 systemd service, and Kodi's
volume to the running sender.

The service reads its settings from atmos67.conf in the add-on's profile
directory, in the format of a systemd EnvironmentFile, and is restarted when
they change. Volume changes go straight to the sender's control socket, since
Kodi does not scale passthrough audio itself.
"""

import json
import os
import subprocess

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import common

ADDON_ID = "service.atmos67"
UNITS = ["atmos67-ptp4l.service", "atmos67-phc2sys.service", "atmos67.service"]
SETTINGS = ["layout", "interface", "address", "ptp_domain", "buffer_ms", "mode", "subs", "slope",
            "max_volume_db"] + [f"xo_{group}" for group in common.GROUPS]


def addon():
    # A new object each time: an Addon object keeps the settings it was created with.
    return xbmcaddon.Addon(ADDON_ID)


def notify(message):
    xbmcgui.Dialog().notification(addon().getAddonInfo("name"), message, xbmcgui.NOTIFICATION_ERROR)


def profile():
    return xbmcvfs.translatePath(addon().getAddonInfo("profile"))


def settings():
    current = addon()
    return {key: current.getSetting(key) for key in SETTINGS}


def kodi_volume():
    request = {"jsonrpc": "2.0", "id": 1, "method": "Application.GetProperties",
               "params": {"properties": ["volume", "muted"]}}
    result = json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result", {})
    return result.get("volume", 100), result.get("muted", False)


def volume_db(percent, muted):
    return common.volume_db(percent, muted, float(addon().getSetting("max_volume_db") or 0))


def write_config(mode=None):
    """Writes the service configuration; True when more than the volume changed."""
    path = os.path.join(profile(), "atmos67.conf")
    values = common.values(settings(), common.read_levels(profile()), profile(), volume_db(*kodi_volume()), mode)
    new = common.config_text(values)
    try:
        with open(path, encoding="utf-8") as file:
            old = file.read()
    except FileNotFoundError:
        old = ""
    keep = lambda text: [line for line in text.splitlines() if not line.startswith("VOLUME_DB=")]
    if keep(old) == keep(new):
        return False
    os.makedirs(profile(), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(new)
    return True


def restart():
    if not os.path.exists("/usr/bin/atmos67"):
        notify(addon().getLocalizedString(32040))
        return False
    result = subprocess.run(["sudo", "-n", "systemctl", "restart"] + UNITS, capture_output=True, text=True)
    if result.returncode != 0:
        xbmc.log(f"{ADDON_ID}: {result.stderr.strip()}", xbmc.LOGERROR)
        notify(addon().getLocalizedString(32041))
        return False
    return True


def apply(mode=None):
    if write_config(mode):
        restart()


def save_volume(percent, muted):
    """Keeps the configuration's volume current without touching the rest of
    it, so a restart that does not go through apply() starts at this volume."""
    path = os.path.join(profile(), "atmos67.conf")
    try:
        with open(path, encoding="utf-8") as file:
            old = file.read()
    except FileNotFoundError:
        return
    new = common.replace_volume(old, volume_db(percent, muted))
    if new != old:
        with open(path, "w", encoding="utf-8") as file:
            file.write(new)


def send_volume(percent, muted):
    save_volume(percent, muted)
    try:
        if muted:
            common.command("mute 1")
        else:
            common.command(f"volume {volume_db(percent, False)}")
            common.command("mute 0")
    except OSError as error:
        # The service is starting or stopped; it starts at the volume written to its configuration.
        xbmc.log(f"{ADDON_ID}: volume not sent: {error}", xbmc.LOGDEBUG)


def kodi_rpc(method, params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return json.loads(xbmc.executeJSONRPC(json.dumps(request)))


def sync_picture():
    """Delays the picture by the time the sound takes to reach the speakers."""
    current = addon()
    if current.getSetting("auto_av_offset") != "true":
        return
    try:
        sender_ms = common.answer_value(common.command("latency"))
    except (OSError, ValueError) as error:
        xbmc.log(f"{ADDON_ID}: no latency from the sender: {error}", xbmc.LOGWARNING)
        return
    offset = common.av_offset(sender_ms, float(current.getSetting("receiver_latency_ms") or 0),
                              float(current.getSetting("av_trim_ms") or 0))
    players = kodi_rpc("Player.GetActivePlayers", {}).get("result", [])
    video = [p["playerid"] for p in players if p.get("type") == "video"]
    if video:
        result = kodi_rpc("Player.SetAudioDelay", {"playerid": video[0], "offset": offset})
        xbmc.log(f"{ADDON_ID}: audio offset {offset} s: {result}", xbmc.LOGINFO)


class Player(xbmc.Player):
    def onAVStarted(self):
        if self.isPlayingVideo():
            sync_picture()


class Monitor(xbmc.Monitor):
    def onSettingsChanged(self):
        apply()

    def onNotification(self, sender, method, data):
        if method == "Application.OnVolumeChanged":
            event = json.loads(data)
            send_volume(event.get("volume", 100), event.get("muted", False))


if __name__ == "__main__":
    player = Player()
    monitor = Monitor()
    apply()
    monitor.waitForAbort()
