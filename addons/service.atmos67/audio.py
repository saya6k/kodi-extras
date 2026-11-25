"""Points Kodi's audio output at the atmos67 loopback device with every
passthrough format enabled. Run from the add-on's settings."""

import json

import xbmc
import xbmcaddon
import xbmcgui

DEVICE = "ALSA:hdmi_atmos67"
# In this order: the passthrough settings only apply once passthrough is on.
SETTINGS = [
    ("audiooutput.audiodevice", DEVICE),
    # 2.0 speakers, so that multichannel audio Kodi decodes itself (AAC, FLAC)
    # is transcoded to Dolby Digital, which atmos67 can decode.
    ("audiooutput.channels", 1),
    ("audiooutput.passthrough", True),
    ("audiooutput.passthroughdevice", DEVICE),
    ("audiooutput.ac3passthrough", True),
    ("audiooutput.ac3transcode", True),
    ("audiooutput.eac3passthrough", True),
    ("audiooutput.dtspassthrough", True),
    ("audiooutput.truehdpassthrough", True),
    ("audiooutput.dtshdpassthrough", True),
]


def set_setting(setting, value):
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Settings.SetSettingValue",
        "params": {"setting": setting, "value": value},
    }
    return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result") is True


if __name__ == "__main__":
    addon = xbmcaddon.Addon("service.atmos67")
    failed = [setting for setting, value in SETTINGS if not set_setting(setting, value)]
    if failed:
        message = addon.getLocalizedString(32043) + "\n" + "\n".join(failed)
    else:
        message = addon.getLocalizedString(32042)
    xbmcgui.Dialog().ok(addon.getAddonInfo("name"), message)
