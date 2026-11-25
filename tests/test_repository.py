"""The Kodi repository that scripts/build-repository.py builds, fetched the
way Kodi fetches it. Run: python3 -m unittest discover -s tests"""

import functools
import hashlib
import importlib.util
import io
import os
import tempfile
import threading
import unittest
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.join(os.path.dirname(__file__), "..")
spec = importlib.util.spec_from_file_location("build_repository", os.path.join(ROOT, "scripts", "build-repository.py"))
build_repository = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_repository)


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.temp.name, "repo")
        self.server = HTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=self.temp.name))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/repo"
        build_repository.build(self.base + "/", self.out)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def get(self, url):
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read()

    def test_kodi_can_follow_the_repository_addon(self):
        with zipfile.ZipFile(os.path.join(self.out, "repository.kodiextras-1.0.0.zip")) as archive:
            repo = ET.fromstring(archive.read("repository.kodiextras/addon.xml"))
        directory = repo.find("extension[@point='xbmc.addon.repository']/dir")
        info, checksum, datadir = (directory.find(tag).text for tag in ("info", "checksum", "datadir"))
        self.assertEqual(datadir, self.base)

        addons_xml = self.get(info)
        self.assertEqual(self.get(checksum).decode(), hashlib.md5(addons_xml).hexdigest())

        listed = {addon.get("id"): addon for addon in ET.fromstring(addons_xml)}
        self.assertEqual(set(listed), {"repository.kodiextras", "script.service.threadbridge"})
        for addon_id, entry in listed.items():
            version = entry.get("version")
            data = self.get(f"{datadir}/{addon_id}/{addon_id}-{version}.zip")
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = archive.namelist()
                self.assertTrue(all(name.startswith(addon_id + "/") for name in names), names)
                inside = ET.fromstring(archive.read(f"{addon_id}/addon.xml"))
            entry.tail = None
            self.assertEqual(ET.tostring(inside), ET.tostring(entry))

    def test_no_placeholder_or_junk_left(self):
        with open(os.path.join(self.out, "addons.xml"), encoding="utf-8") as file:
            self.assertNotIn("@BASE_URL@", file.read())
        with zipfile.ZipFile(os.path.join(self.out, "script.service.threadbridge",
                                          "script.service.threadbridge-0.1.0.zip")) as archive:
            names = archive.namelist()
        self.assertIn("script.service.threadbridge/resources/settings.xml", names)
        self.assertFalse([n for n in names if "__pycache__" in n or n.endswith((".pyc", ".DS_Store", ".gitkeep"))])


if __name__ == "__main__":
    unittest.main()
