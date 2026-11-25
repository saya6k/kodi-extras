"""Hands the add-on's settings to the threadbridge systemd service.

The service reads threadbridge.conf in the add-on's profile directory, in the
format of a systemd EnvironmentFile, and is restarted when it changes.
"""

import os
import subprocess

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import common

ADDON_ID = "script.service.threadbridge"
UNIT = "threadbridge.service"
SETTINGS = ["device", "baudrate", "flow_control", "backbone", "rest_public", "rest_port", "nat64", "firewall"]


def addon():
    # A new object each time: an Addon object keeps the settings it was created with.
    return xbmcaddon.Addon(ADDON_ID)


def write_config():
    """Writes the service configuration; True when it changed."""
    profile = xbmcvfs.translatePath(addon().getAddonInfo("profile"))
    path = os.path.join(profile, "threadbridge.conf")
    current = addon()
    new = common.config_text(common.values({key: current.getSetting(key) for key in SETTINGS}))
    try:
        with open(path, encoding="utf-8") as file:
            if file.read() == new:
                return False
    except FileNotFoundError:
        pass
    os.makedirs(profile, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(new)
    return True


def restart():
    result = subprocess.run(["sudo", "-n", "systemctl", "restart", UNIT], capture_output=True, text=True)
    if result.returncode != 0:
        xbmc.log(f"threadbridge: restart failed: {result.stderr.strip()}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(addon().getAddonInfo("name"), addon().getLocalizedString(32100),
                                      xbmcgui.NOTIFICATION_ERROR)


class Monitor(xbmc.Monitor):
    def onSettingsChanged(self):
        if write_config():
            restart()


if __name__ == "__main__":
    monitor = Monitor()
    # The first start after installing the add-on: the service has run on
    # the package's defaults so far.
    if write_config():
        restart()
    monitor.waitForAbort()
