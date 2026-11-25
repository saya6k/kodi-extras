"""Which speakers go in which AES67 stream, run from the add-on's settings.

Each stream has a name (what receivers such as Dante Controller show), a
multicast address and up to 8 of the outputs the service sends. Without a
plan the service sends 8 channels a stream in order.
"""

import copy
import subprocess

import xbmcgui

import common
import levels
import service


def text(string_id, *args):
    value = service.addon().getLocalizedString(string_id)
    return value % args if args else value


def row(stream):
    return f"{stream['name']}   {stream['address']}   {' '.join(stream['channels']) or '-'}"


def edit_stream(stream, outputs):
    """Edits one stream in place; False when the user deletes it."""
    while True:
        actions = [text(32123, stream["name"]), text(32124, stream["address"]),
                   text(32125, " ".join(stream["channels"]) or "-"), text(32126)]
        chosen = xbmcgui.Dialog().select(stream["name"], actions)
        if chosen < 0:
            return True
        if chosen == 0:
            stream["name"] = xbmcgui.Dialog().input(text(32127), stream["name"]) or stream["name"]
        elif chosen == 1:
            address = xbmcgui.Dialog().input(text(32128), stream["address"])
            if address and common.stream_problem({"address": address, "channels": []}) is None:
                stream["address"] = address
            elif address:
                xbmcgui.Dialog().ok(stream["name"], text(32129))
        elif chosen == 2:
            preselect = [i for i, output in enumerate(outputs) if output in stream["channels"]]
            picked = xbmcgui.Dialog().multiselect(text(32130), outputs, preselect=preselect)
            if picked is None:
                continue
            if len(picked) > common.CHANNELS_PER_STREAM:
                xbmcgui.Dialog().ok(stream["name"], text(32131, common.CHANNELS_PER_STREAM))
                continue
            stream["channels"] = [outputs[i] for i in picked]
        elif chosen == 3 and xbmcgui.Dialog().yesno(stream["name"], text(32132)):
            return False


def edit():
    profile = service.profile()
    settings = service.settings()
    try:
        outputs = levels.outputs(settings, profile, sent=True)
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError):
        xbmcgui.Dialog().ok(text(32120), text(32114))
        return
    saved = common.read_streams(profile)
    streams = copy.deepcopy(saved) or common.default_streams(outputs, settings["address"])
    while True:
        left = common.unassigned(outputs, streams)
        rows = [row(stream) for stream in streams] + [text(32121), text(32122)]
        heading = text(32120) + (f"  ({text(32133, ' '.join(left))})" if left else "")
        chosen = xbmcgui.Dialog().select(heading, rows)
        if chosen < 0:
            break
        if chosen == len(streams):
            taken = {s["address"] for s in streams}
            address = next(common.address_after(settings["address"], n) for n in range(256)
                           if common.address_after(settings["address"], n) not in taken)
            streams.append({"name": f"atmos67 {len(streams) + 1}", "address": address, "channels": []})
            if not edit_stream(streams[-1], outputs):
                streams.pop()
        elif chosen == len(streams) + 1:
            streams = common.default_streams(outputs, settings["address"])
        elif not edit_stream(streams[chosen], outputs):
            streams.pop(chosen)
    # The default plan is what the service does without one.
    plan = [] if streams == common.default_streams(outputs, settings["address"]) else streams
    if plan != saved:
        common.write_streams(profile, plan)
        service.write_config()
        service.restart()


if __name__ == "__main__":
    edit()
