"""Per-speaker level trims and distances, run from the add-on's settings.

Lists the outputs the service sends (its speakers, then its subwoofers) and
keeps a trim in dB and a distance in metres for each. Distances become
delays that bring every speaker to the farthest one's arrival; a measured
correction has its speakers aligned already and ignores them.
"""

import json
import os
import subprocess
import tempfile

import xbmcgui

import common
import service


def text(string_id, *args):
    value = service.addon().getLocalizedString(string_id)
    return value % args if args else value


def outputs(settings, profile, sent=False):
    """The roles of the outputs of the correction in the current mode. With
    `sent`, the channels the service sends: without correction ("off"), the
    rendered speakers, LFE included, rather than the outputs a design would have."""
    mode = common.MODES[int(settings["mode"] or 0)]
    if mode == "auto":
        with open(os.path.join(common.auto_design(profile), "secs-design.json"), encoding="utf-8") as file:
            return json.load(file)["outputs"]
    with tempfile.TemporaryDirectory() as folder:
        layout = ["--layout", settings["layout"]]
        subprocess.run(["/usr/bin/atmos67"] + layout + ["--write-design", folder, "--subs", settings["subs"]], check=True)
        with open(os.path.join(folder, "secs-design.json"), encoding="utf-8") as file:
            manifest = json.load(file)
    return manifest["inputs"] if sent and mode == "off" else manifest["outputs"]


def number(heading, value):
    entered = xbmcgui.Dialog().input(heading, "" if value is None else str(value))
    if entered == "":
        return value
    try:
        return float(entered)
    except ValueError:
        return value


def edit():
    profile = service.profile()
    levels = common.read_levels(profile)
    try:
        roles = outputs(service.settings(), profile)
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError):
        xbmcgui.Dialog().ok(text(32110), text(32114))
        return
    changed = False
    while True:
        rows = []
        for role in roles:
            level = levels.get(role, {})
            distance = level.get("distance")
            rows.append(text(32111, role, level.get("trim", 0.0), "-" if distance is None else f"{distance:.2f}"))
        chosen = xbmcgui.Dialog().select(text(32110), rows)
        if chosen < 0:
            break
        role = roles[chosen]
        level = levels.setdefault(role, {})
        level["trim"] = number(text(32112, role), level.get("trim", 0.0)) or 0.0
        level["distance"] = number(text(32113, role), level.get("distance"))
        changed = True
    if changed:
        common.write_levels(profile, levels)
        service.apply()


if __name__ == "__main__":
    edit()
