"""The add-on's dialogs: Thread network status and management, and picking
the dongle and the backbone interface. Run from the settings' buttons as
RunScript(script.service.threadbridge,<action>), or from the add-on list."""

import os
import sys

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import common

ADDON_ID = "script.service.threadbridge"
JOINER_TIMEOUT_S = 120
COMMISSIONER_WAIT_S = 15
STATUS_LABELS = {
    "state": 32130, "network_name": 32131, "channel": 32132, "pan_id": 32133, "ext_pan_id": 32134,
    "routers": 32135, "rloc16": 32136, "border_agent": 32137, "coprocessor": 32138,
}


def addon():
    return xbmcaddon.Addon(ADDON_ID)


def text(string_id):
    return addon().getLocalizedString(string_id)


def name():
    return addon().getAddonInfo("name")


def rest():
    return common.Rest(port=int(addon().getSetting("rest_port") or 8081))


def notify(message, error=False):
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification(name(), message, icon)


def show_error(error):
    if error.status is None:
        xbmcgui.Dialog().ok(name(), text(32101))
    else:
        xbmcgui.Dialog().ok(name(), text(32123) % error)


def status():
    api = rest()
    node = api.node()
    dataset = api.active_dataset()
    try:
        coprocessor = api.coprocessor_version()
    except common.RestError:
        coprocessor = None
    lines = [f"{text(STATUS_LABELS[key])}: {value}" for key, value in common.status_lines(node, dataset, coprocessor)]
    xbmcgui.Dialog().textviewer(text(32139), "\n".join(lines))


def confirm_replace(api):
    """Asks before an existing network is left; True to go on."""
    if api.active_dataset() is None:
        return True
    return xbmcgui.Dialog().yesno(name(), text(32107))


def form():
    api = rest()
    network_name = xbmcgui.Dialog().input(text(32104), "threadbridge")
    if not network_name:
        return
    if not common.valid_network_name(network_name):
        xbmcgui.Dialog().ok(name(), text(32105))
        return
    channel = xbmcgui.Dialog().input(text(32106), type=xbmcgui.INPUT_NUMERIC)
    if channel and not 11 <= int(channel) <= 26:
        xbmcgui.Dialog().ok(name(), text(32124))
        return
    if not confirm_replace(api):
        return
    common.replace_network(api, common.form_dataset(network_name, channel))
    notify(text(32108))


def read_file(path):
    file = xbmcvfs.File(path)
    try:
        return file.read()
    finally:
        file.close()


def import_dataset():
    choice = xbmcgui.Dialog().select(text(32109), [text(32110), text(32111)])
    if choice == 0:
        raw = xbmcgui.Dialog().input(text(32112))
    elif choice == 1:
        path = xbmcgui.Dialog().browse(1, text(32111), "files")
        raw = read_file(path) if path else ""
    else:
        return
    if not raw:
        return
    dataset = common.normalize_dataset(raw)
    if dataset is None:
        xbmcgui.Dialog().ok(name(), text(32113))
        return
    api = rest()
    if not confirm_replace(api):
        return
    common.replace_network(api, dataset)
    notify(text(32114))


def export_dataset():
    tlvs = rest().active_dataset_tlvs()
    if tlvs is None:
        xbmcgui.Dialog().ok(name(), text(32115))
        return
    profile = xbmcvfs.translatePath(addon().getAddonInfo("profile"))
    os.makedirs(profile, exist_ok=True)
    path = os.path.join(profile, "dataset.txt")
    with open(path, "w", encoding="utf-8") as file:
        file.write(tlvs + "\n")
    xbmcgui.Dialog().textviewer(text(32043), f"{tlvs}\n\n{text(32116) % path}")


def joiner():
    pskd = xbmcgui.Dialog().input(text(32117))
    if not pskd:
        return
    pskd = pskd.upper()
    if not common.valid_pskd(pskd):
        xbmcgui.Dialog().ok(name(), text(32118))
        return
    eui64 = xbmcgui.Dialog().input(text(32119))
    if eui64 and not common.valid_eui64(eui64):
        xbmcgui.Dialog().ok(name(), text(32120))
        return
    api = rest()
    if api.commissioner_state() != "active":
        api.set_commissioner(True)
        monitor = xbmc.Monitor()
        for _ in range(COMMISSIONER_WAIT_S):
            if api.commissioner_state() == "active" or monitor.waitForAbort(1):
                break
        if api.commissioner_state() != "active":
            xbmcgui.Dialog().ok(name(), text(32121))
            return
    api.add_joiner(pskd, eui64 or None, JOINER_TIMEOUT_S)
    xbmcgui.Dialog().ok(name(), text(32122) % JOINER_TIMEOUT_S)


def pick(setting, choices, empty_message, automatic=None):
    """Sets `setting` to one of `choices`; `automatic` adds a first entry that clears it."""
    if not choices:
        xbmcgui.Dialog().ok(name(), text(empty_message))
        return
    labels = ([automatic] if automatic else []) + choices
    choice = xbmcgui.Dialog().select(name(), labels)
    if choice < 0:
        return
    if automatic:
        addon().setSetting(setting, "" if choice == 0 else choices[choice - 1])
    else:
        addon().setSetting(setting, choices[choice])


def pick_device():
    pick("device", common.serial_devices(), 32102, automatic=text(32125))


def pick_backbone():
    pick("backbone", common.network_interfaces(), 32103)


ACTIONS = {
    "status": status, "form": form, "import": import_dataset, "export": export_dataset, "joiner": joiner,
    "pick_device": pick_device, "pick_backbone": pick_backbone,
}
MENU = [("status", 32040), ("form", 32041), ("import", 32042), ("export", 32043), ("joiner", 32044)]


def main(argv):
    action = argv[1] if len(argv) > 1 else None
    if action is None:
        choice = xbmcgui.Dialog().select(name(), [text(label) for _, label in MENU])
        if choice < 0:
            return
        action = MENU[choice][0]
    try:
        ACTIONS[action]()
    except common.RestError as error:
        show_error(error)


if __name__ == "__main__":
    main(sys.argv)
