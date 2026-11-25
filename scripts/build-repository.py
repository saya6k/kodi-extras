#!/usr/bin/env python3
"""Builds the Kodi repository into dist/repo, to be served at BASE_URL as is.

    scripts/build-repository.py https://example.org/kodi-extras

dist/repo holds addons.xml and its md5, <id>/<id>-<version>.zip for every
add-on in repository/addons.txt and for repository.kodiextras itself, and
repository.kodiextras-<version>.zip at the top for the first install from a
zip file, with an index.html that links it: Kodi's file manager reads the
links of an HTML page as a folder, where a host such as GitHub Pages lists
no directories.
"""

import hashlib
import html
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOSITORY_ID = "repository.kodiextras"
SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {".DS_Store", ".gitkeep"}


def listed_addons(path):
    with open(path, encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip() and not line.startswith("#")]


def addon_version(addon_dir):
    root = ET.parse(os.path.join(addon_dir, "addon.xml")).getroot()
    return root.get("id"), root.get("version")


def zip_addon(addon_dir, addon_id, path):
    """Zips addon_dir with the add-on id as the top folder, as Kodi expects."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for directory, dirs, files in os.walk(addon_dir):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                if name in SKIP_FILES or name.endswith(".pyc"):
                    continue
                full = os.path.join(directory, name)
                archive.write(full, os.path.join(addon_id, os.path.relpath(full, addon_dir)))


def addon_xml_body(addon_dir):
    """addon.xml without its XML declaration, for addons.xml."""
    with open(os.path.join(addon_dir, "addon.xml"), encoding="utf-8") as file:
        text = file.read()
    if text.startswith("<?xml"):
        text = text[text.index("?>") + 2:]
    return text.strip()


def build(base_url, out):
    """Writes the repository to out; returns the zips it made."""
    base_url = base_url.rstrip("/")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    with tempfile.TemporaryDirectory() as staging:
        # The repository add-on gets its URLs filled in before it is zipped.
        repository = os.path.join(staging, REPOSITORY_ID)
        shutil.copytree(os.path.join(ROOT, "repository", REPOSITORY_ID), repository)
        addon_xml = os.path.join(repository, "addon.xml")
        with open(addon_xml, encoding="utf-8") as file:
            text = file.read().replace("@BASE_URL@", base_url)
        with open(addon_xml, "w", encoding="utf-8") as file:
            file.write(text)

        dirs = [repository] + [os.path.join(ROOT, "addons", addon_id)
                               for addon_id in listed_addons(os.path.join(ROOT, "repository", "addons.txt"))]
        bodies = []
        zips = []
        for addon_dir in dirs:
            addon_id, version = addon_version(addon_dir)
            if addon_id != os.path.basename(addon_dir):
                raise SystemExit(f"{addon_dir}: addon.xml says id {addon_id}")
            os.makedirs(os.path.join(out, addon_id))
            zip_path = os.path.join(out, addon_id, f"{addon_id}-{version}.zip")
            zip_addon(addon_dir, addon_id, zip_path)
            if addon_id == REPOSITORY_ID:
                shutil.copy(zip_path, out)
                repository_zip = os.path.basename(zip_path)
            bodies.append(addon_xml_body(addon_dir))
            zips.append(zip_path)

    addons = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n' + "\n".join(bodies) + "\n</addons>\n"
    with open(os.path.join(out, "addons.xml"), "w", encoding="utf-8") as file:
        file.write(addons)
    with open(os.path.join(out, "addons.xml.md5"), "w", encoding="utf-8") as file:
        file.write(hashlib.md5(addons.encode("utf-8")).hexdigest())
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as file:
        file.write(index_html(repository_zip))
    return zips


def index_html(repository_zip):
    name = html.escape(repository_zip)
    return (f'<!doctype html>\n<html><head><meta charset="utf-8"><title>kodi-extras</title></head>\n'
            f'<body><a href="{name}">{name}</a></body></html>\n')


def main(argv):
    if len(argv) != 2 or not argv[1].startswith(("http://", "https://")):
        raise SystemExit(__doc__)
    for path in build(argv[1], os.path.join(ROOT, "dist", "repo")):
        print(path)


if __name__ == "__main__":
    main(sys.argv)
