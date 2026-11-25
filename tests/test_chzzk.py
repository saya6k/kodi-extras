"""Tests of plugin.video.chzzk against a fake CHZZK API shaped like the real
one (checked 2026-11-25). Run: python3 -m unittest discover -s tests"""

import importlib.util
import json
import os
import sys
import threading
import types
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

PLUGIN = os.path.join(os.path.dirname(__file__), "..", "addons", "plugin.video.chzzk")
sys.path.insert(0, PLUGIN)

import chzzk  # noqa: E402

CHANNEL = {"channelId": "c1", "channelName": "Streamer", "channelImageUrl": "https://img/c1.png",
           "verifiedMark": True}
LIVE = {"liveId": 7, "liveTitle": "Playing", "concurrentUserCount": 1234, "adult": False,
        "liveImageUrl": "https://thumb/image_{type}.jpg", "defaultThumbnailImageUrl": None,
        "liveCategoryValue": "Game", "channel": CHANNEL}
PLAYBACK = json.dumps({"media": [
    {"mediaId": "HLS", "protocol": "HLS", "path": "https://live/hls.m3u8"},
    {"mediaId": "LLHLS", "protocol": "HLS", "path": "https://live/llhls.m3u8"},
]})


def ok(content):
    return 200, {"code": 200, "message": None, "content": content}


ANSWERS = {
    "/service/v1/lives": lambda q: ok({"size": 20, "page": {"next": {"concurrentUserCount": 100, "liveId": 8}},
                                       "data": [LIVE]}),
    "/service/v1/search/lives": lambda q: ok({"page": {"next": {"offset": 20}},
                                              "data": [{"live": dict(LIVE, channelId="c1"), "channel": CHANNEL}]}),
    "/service/v1/search/channels": lambda q: ok({"page": {"next": None},
                                                 "data": [{"channel": dict(CHANNEL, openLive=True, followerCount=5)}]}),
    "/service/v1/channels/c1": lambda q: ok(dict(CHANNEL, openLive=True, channelDescription="hi")),
    "/service/v1/channels/c1/videos": lambda q: ok({"page": int(q["page"]), "totalPages": 2, "data": [
        {"videoNo": 99, "videoTitle": "Replay", "thumbnailImageUrl": "https://img/v.jpg", "duration": 3600,
         "publishDate": "2026-11-25 01:59:28", "videoCategoryValue": "Game", "adult": False}]}),
    "/service/v3/channels/c1/live-detail": lambda q: ok(dict(LIVE, status="OPEN", livePlaybackJson=PLAYBACK)),
    "/service/v3/channels/off/live-detail": lambda q: ok(dict(LIVE, status="CLOSE", livePlaybackJson=None)),
    "/service/v3/channels/adult/live-detail": lambda q: ok(dict(LIVE, status="OPEN", adult=True,
                                                                livePlaybackJson=None)),
    "/service/v3/videos/99": lambda q: ok({"videoNo": 99, "videoId": "ABC", "inKey": "K/1", "vodStatus": "ABR_HLS",
                                           "liveRewindPlaybackJson": None, "adult": False}),
    "/service/v3/videos/100": lambda q: ok({"videoNo": 100, "videoId": "DEF", "inKey": "K2",
                                            "liveRewindPlaybackJson": PLAYBACK}),
    "/service/v3/videos/101": lambda q: ok({"videoNo": 101, "videoId": None, "inKey": None, "adult": True}),
    "/service/v1/channels/followings": lambda q: (
        ok({"totalCount": 2, "followingList": [
            {"channelId": "c2", "channel": {"channelName": "Off", "channelImageUrl": ""},
             "streamer": {"openLive": False}, "liveInfo": {}},
            {"channelId": "c1", "channel": {"channelName": "Streamer", "channelImageUrl": ""},
             "streamer": {"openLive": True}, "liveInfo": {"liveTitle": "Playing", "concurrentUserCount": 9}},
        ]}) if FakeApi.cookie else (401, {"code": 401, "message": "권한이 없습니다.", "content": None})),
}


class FakeApi(BaseHTTPRequestHandler):
    requests = []
    cookie = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        FakeApi.requests.append((parsed.path, query, dict(self.headers)))
        FakeApi.cookie = self.headers.get("Cookie")
        status, body = ANSWERS.get(parsed.path, lambda q: (404, {"code": 404, "message": "없음"}))(query)
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class ApiCase(unittest.TestCase):
    def setUp(self):
        FakeApi.requests = []
        self.server = HTTPServer(("127.0.0.1", 0), FakeApi)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.api_url = f"http://127.0.0.1:{self.server.server_address[1]}/service"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def client(self, nid_aut="", nid_ses=""):
        return chzzk.Chzzk(nid_aut, nid_ses, api=self.api_url, vod_playback="https://vod/playback", timeout=5)


class ClientTest(ApiCase):
    def test_popular_lives_and_their_cursor(self):
        lives, cursor = self.client().popular_lives()
        self.assertEqual(cursor, {"concurrentUserCount": 100, "liveId": 8})
        self.assertEqual(lives[0]["thumbnail"], "https://thumb/image_720.jpg")
        self.assertEqual(lives[0]["channel_id"], "c1")
        self.client().popular_lives(cursor)
        self.assertEqual(FakeApi.requests[-1][1]["liveId"], "8")
        self.assertNotIn("liveId", FakeApi.requests[0][1])

    def test_searches(self):
        lives, offset = self.client().search_lives("롤")
        self.assertEqual((lives[0]["channel_name"], offset), ("Streamer", 20))
        self.assertEqual(FakeApi.requests[-1][1]["keyword"], "롤")
        channels, offset = self.client().search_channels("x", 20)
        self.assertEqual((channels[0]["live"], channels[0]["followers"], offset), (True, 5, None))

    def test_videos_and_pages(self):
        videos, more = self.client().channel_videos("c1", 0)
        self.assertTrue(more)
        self.assertEqual(videos[0]["date"], "2026-11-25")
        _, more = self.client().channel_videos("c1", 1)
        self.assertFalse(more)

    def test_live_stream_prefers_plain_hls(self):
        self.assertEqual(self.client().live_stream("c1"), chzzk.Stream("https://live/hls.m3u8", chzzk.HLS))

    def test_not_live_and_adult(self):
        with self.assertRaises(chzzk.NotLive):
            self.client().live_stream("off")
        with self.assertRaises(chzzk.AdultOnly):
            self.client().live_stream("adult")
        with self.assertRaises(chzzk.AdultOnly):
            self.client().video_stream(101)

    def test_video_plays_the_dash_manifest_with_its_accept_header(self):
        stream = self.client().video_stream(99)
        self.assertEqual(stream.url, "https://vod/playback/ABC?key=K%2F1")
        self.assertEqual(stream.mime, chzzk.DASH)
        path, _, headers = stream.kodi_path().partition("|")
        headers = dict(urllib.parse.parse_qsl(headers))
        self.assertEqual(headers["Accept"], "application/dash+xml")
        self.assertNotIn("+", stream.kodi_path().partition("|")[2])

    def test_replay_plays_the_live_recording(self):
        self.assertEqual(self.client().video_stream(100), chzzk.Stream("https://live/hls.m3u8", chzzk.HLS))

    def test_no_cookie_without_both(self):
        self.assertFalse(self.client("a", "").logged_in)
        self.client("a", "").popular_lives()
        self.assertNotIn("Cookie", FakeApi.requests[-1][2])

    def test_followings_need_the_cookies(self):
        with self.assertRaises(chzzk.ChzzkError) as raised:
            self.client().followings()
        self.assertEqual(raised.exception.status, 401)
        self.assertEqual(str(raised.exception), "권한이 없습니다.")
        channels = self.client(" aut ", "ses").followings()
        self.assertEqual(FakeApi.requests[-1][2]["Cookie"], "NID_AUT=aut; NID_SES=ses")
        self.assertEqual([(c["channel_id"], c["live"]) for c in channels], [("c2", False), ("c1", True)])
        self.assertEqual(channels[1]["title"], "Playing")

    def test_api_error_code(self):
        with self.assertRaises(chzzk.ChzzkError) as raised:
            self.client().channel("missing")
        self.assertEqual(raised.exception.status, 404)

    def test_channel_ids_are_quoted(self):
        with self.assertRaises(chzzk.ChzzkError):
            self.client().channel("../lives")
        self.assertEqual(FakeApi.requests[-1][0], "/service/v1/channels/..%2Flives")


class FakeKodi:
    """Just enough of xbmc, xbmcaddon, xbmcgui and xbmcplugin for default.py."""

    def __init__(self, settings):
        self.items = []
        self.resolved = None
        self.ended = None
        self.notifications = []
        kodi = self

        class Tag:
            def __getattr__(self, name):
                return lambda *args: None

        class ListItem:
            def __init__(self, label="", path=""):
                self.label, self.path, self.props, self.mime = label, path, {}, None

            def setArt(self, art):
                self.art = art

            def getVideoInfoTag(self):
                return Tag()

            def setProperty(self, key, value):
                self.props[key] = value

            def addContextMenuItems(self, items):
                self.menu = items

            def setMimeType(self, mime):
                self.mime = mime

            def setContentLookup(self, value):
                pass

        class Dialog:
            def notification(self, heading, message, icon=None):
                kodi.notifications.append(message)

            def input(self, heading, *args, **kwargs):
                return "검색어"

        class Addon:
            def getSetting(self, key):
                return settings.get(key, "")

            def getLocalizedString(self, string_id):
                return f"#{string_id} %s" if string_id in (32030, 32043, 32044) else f"#{string_id}"

            def getAddonInfo(self, key):
                return {"id": "plugin.video.chzzk", "name": "CHZZK"}[key]

        def add(handle, url, item, isFolder):
            kodi.items.append((url, item, isFolder))

        def resolve(handle, succeeded, item):
            kodi.resolved = (succeeded, item)

        def end(handle, succeeded=True):
            kodi.ended = succeeded

        self.modules = {
            "xbmc": types.SimpleNamespace(log=lambda *a: None, LOGWARNING=2),
            "xbmcaddon": types.SimpleNamespace(Addon=Addon),
            "xbmcgui": types.SimpleNamespace(ListItem=ListItem, Dialog=Dialog, NOTIFICATION_ERROR="error"),
            "xbmcplugin": types.SimpleNamespace(addDirectoryItem=add, setResolvedUrl=resolve,
                                                endOfDirectory=end, setContent=lambda *a: None),
        }


class PluginTest(ApiCase):
    def run_plugin(self, path, query="", settings=None):
        kodi = FakeKodi(settings or {})
        saved_modules = {name: sys.modules.get(name) for name in kodi.modules}
        saved_argv = sys.argv
        real_client = chzzk.Chzzk
        sys.modules.update(kodi.modules)
        sys.argv = [f"plugin://plugin.video.chzzk/{path}", "1", query]
        # default.py makes its client from the cookies alone; point it at the fake API.
        chzzk.Chzzk = lambda nid_aut, nid_ses: real_client(nid_aut, nid_ses, api=self.api_url,
                                                           vod_playback="https://vod/playback", timeout=5)
        try:
            # By path: other add-ons on sys.path have a default.py too.
            spec = importlib.util.spec_from_file_location("chzzk_default", os.path.join(PLUGIN, "default.py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()
        finally:
            chzzk.Chzzk = real_client
            sys.argv = saved_argv
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
        return kodi

    def test_root_shows_followings_only_with_cookies(self):
        routes = [url for url, _, _ in self.run_plugin("").items]
        self.assertEqual(routes, ["plugin://plugin.video.chzzk/popular", "plugin://plugin.video.chzzk/search_lives",
                                  "plugin://plugin.video.chzzk/search_channels"])
        routes = [url for url, _, _ in self.run_plugin("", settings={"nid_aut": "a", "nid_ses": "b"}).items]
        self.assertIn("plugin://plugin.video.chzzk/followings", routes)

    def test_popular_links_from_a_nested_folder(self):
        kodi = self.run_plugin("popular")
        urls = [url for url, _, _ in kodi.items]
        self.assertEqual(urls[0], "plugin://plugin.video.chzzk/play_live?id=c1")
        page = urllib.parse.urlparse(urls[-1])
        self.assertEqual(page.path, "/popular")
        cursor = json.loads(dict(urllib.parse.parse_qsl(page.query))["cursor"])
        self.assertEqual(cursor, {"concurrentUserCount": 100, "liveId": 8})
        self.run_plugin("popular", "?" + page.query)
        self.assertEqual(FakeApi.requests[-1][1]["liveId"], "8")

    def test_channel_lists_its_live_then_videos(self):
        kodi = self.run_plugin("channel", "?id=c1")
        urls = [url for url, _, _ in kodi.items]
        self.assertEqual(urls[:2], ["plugin://plugin.video.chzzk/play_live?id=c1",
                                    "plugin://plugin.video.chzzk/play_video?no=99"])
        self.assertEqual(urls[-1], "plugin://plugin.video.chzzk/channel?id=c1&page=1")

    def test_search_asks_for_the_keyword(self):
        kodi = self.run_plugin("search_lives")
        self.assertEqual(FakeApi.requests[-1][1]["keyword"], "검색어")
        self.assertIn("plugin://plugin.video.chzzk/search_lives?keyword=%EA%B2%80%EC%83%89%EC%96%B4&offset=20",
                      [url for url, _, _ in kodi.items])

    def test_play_video_through_inputstream_adaptive(self):
        succeeded, item = self.run_plugin("play_video", "?no=99").resolved
        self.assertTrue(succeeded)
        self.assertTrue(item.path.startswith("https://vod/playback/ABC?key=K%2F1|Accept="))
        self.assertEqual(item.mime, chzzk.DASH)
        self.assertEqual(item.props["inputstream"], "inputstream.adaptive")
        self.assertEqual(item.props["inputstream.adaptive.manifest_type"], "mpd")
        self.assertIn("Accept=application%2Fdash%2Bxml", item.props["inputstream.adaptive.manifest_headers"])

    def test_play_live_hls(self):
        succeeded, item = self.run_plugin("play_live", "?id=c1").resolved
        self.assertEqual((succeeded, item.path, item.props["inputstream.adaptive.manifest_type"]),
                         (True, "https://live/hls.m3u8", "hls"))

    def test_failed_playback_tells_kodi_and_the_user(self):
        kodi = self.run_plugin("play_live", "?id=off")
        self.assertFalse(kodi.resolved[0])
        self.assertEqual(kodi.notifications, ["#32040"])
        kodi = self.run_plugin("followings")
        self.assertFalse(kodi.ended)
        self.assertEqual(kodi.notifications, ["#32042"])


if __name__ == "__main__":
    unittest.main()
