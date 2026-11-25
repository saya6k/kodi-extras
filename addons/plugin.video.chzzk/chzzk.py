"""The CHZZK (치지직) web API, without Kodi: lives, channels, videos, and the
stream to play for each. The API has no public documentation; this follows
what chzzk.naver.com itself requests.

Without cookies every public live and video plays. NID_AUT and NID_SES, the
cookies of a logged-in naver.com session, add the followed channels and
age-restricted streams (for an adult-verified account).
"""

import json
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.chzzk.naver.com/service"
VOD_PLAYBACK = "https://apis.naver.com/neonplayer/vodplay/v2/playback"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0 Safari/537.36")
PAGE_SIZE = 20
THUMBNAIL_SIZE = "720"

HLS = "application/vnd.apple.mpegurl"
DASH = "application/dash+xml"


class ChzzkError(Exception):
    """The API refused, or did not answer (status None)."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class NotLive(ChzzkError):
    def __init__(self):
        super().__init__(None, "not live")


class AdultOnly(ChzzkError):
    """Age-restricted: needs the cookies of an adult-verified account."""

    def __init__(self):
        super().__init__(None, "adult only")


class Stream:
    def __init__(self, url, mime, headers=None):
        self.url = url
        self.mime = mime
        # Headers the manifest request needs (Kodi's `url|Header=value`).
        self.headers = headers or {}

    def kodi_path(self):
        """The URL with the headers in Kodi's `url|Name=value&...` form."""
        if not self.headers:
            return self.url
        return self.url + "|" + urllib.parse.urlencode(self.headers, quote_via=urllib.parse.quote)

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __repr__(self):
        return f"Stream({self.url!r}, {self.mime!r}, {self.headers!r})"


def thumbnail(url):
    """Live thumbnails carry a `{type}` size placeholder."""
    return url.replace("{type}", THUMBNAIL_SIZE) if url else ""


def live_item(live, channel=None):
    """A live from a list, search result or channel, as the plugin shows it."""
    channel = channel or live.get("channel") or {}
    return {
        "channel_id": channel.get("channelId") or live.get("channelId", ""),
        "channel_name": channel.get("channelName", ""),
        "title": live.get("liveTitle") or "",
        "thumbnail": thumbnail(live.get("liveImageUrl") or live.get("defaultThumbnailImageUrl")),
        "channel_image": channel.get("channelImageUrl") or "",
        "viewers": live.get("concurrentUserCount") or 0,
        "category": live.get("liveCategoryValue") or "",
        "adult": bool(live.get("adult")),
    }


def channel_item(channel):
    return {
        "channel_id": channel.get("channelId", ""),
        "channel_name": channel.get("channelName", ""),
        "channel_image": channel.get("channelImageUrl") or "",
        "description": channel.get("channelDescription") or "",
        "followers": channel.get("followerCount") or 0,
        "live": bool(channel.get("openLive")),
    }


def video_item(video):
    return {
        "video_no": video.get("videoNo"),
        "title": video.get("videoTitle") or "",
        "thumbnail": video.get("thumbnailImageUrl") or "",
        "duration": video.get("duration") or 0,
        "date": (video.get("publishDate") or "")[:10],
        "category": video.get("videoCategoryValue") or "",
        "adult": bool(video.get("adult")),
    }


def hls_from_playback_json(text):
    """The HLS master playlist in a `...PlaybackJson` string, or None.

    Plain HLS before low-latency HLS: Kodi's players handle it better."""
    if not text:
        return None
    media = json.loads(text).get("media") or []
    paths = {m.get("mediaId"): m.get("path") for m in media if m.get("protocol") == "HLS" and m.get("path")}
    return paths.get("HLS") or paths.get("LLHLS") or next(iter(paths.values()), None)


def following_item(entry):
    """An entry of the followed channels, live or not.

    Its shape is what the web client is known to receive; it could not be
    checked without an account."""
    channel = entry.get("channel") or {}
    live = entry.get("liveInfo") or {}
    streamer = entry.get("streamer") or {}
    item = channel_item(dict(channel, channelId=entry.get("channelId") or channel.get("channelId")))
    item["live"] = bool(streamer.get("openLive", channel.get("openLive")))
    item["title"] = live.get("liveTitle") or ""
    item["viewers"] = live.get("concurrentUserCount") or 0
    item["category"] = live.get("liveCategoryValue") or ""
    return item


class Chzzk:
    def __init__(self, nid_aut="", nid_ses="", api=API, vod_playback=VOD_PLAYBACK, timeout=15):
        self.api = api.rstrip("/")
        self.vod_playback = vod_playback.rstrip("/")
        self.timeout = timeout
        self.cookie = f"NID_AUT={nid_aut.strip()}; NID_SES={nid_ses.strip()}" if nid_aut and nid_ses else None

    @property
    def logged_in(self):
        return self.cookie is not None

    def get(self, path, **params):
        """The `content` of an API answer."""
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.api}{path}" + (f"?{query}" if query else "")
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise ChzzkError(error.code, api_message(error.read()) or error.reason)
        except (urllib.error.URLError, OSError) as error:
            raise ChzzkError(None, str(getattr(error, "reason", error)))
        except ValueError:
            raise ChzzkError(None, "not JSON")
        if body.get("code") != 200:
            raise ChzzkError(body.get("code"), body.get("message") or "error")
        return body.get("content")

    def popular_lives(self, cursor=None):
        """A page of lives by viewers, and the cursor of the next (or None)."""
        cursor = cursor or {}
        content = self.get("/v1/lives", size=PAGE_SIZE, sortType="POPULAR",
                           concurrentUserCount=cursor.get("concurrentUserCount"), liveId=cursor.get("liveId"))
        return [live_item(live) for live in content.get("data") or []], (content.get("page") or {}).get("next")

    def search_lives(self, keyword, offset=0):
        content = self.get("/v1/search/lives", keyword=keyword, offset=offset, size=PAGE_SIZE)
        items = [live_item(entry.get("live") or {}, entry.get("channel")) for entry in content.get("data") or []]
        return items, next_offset(content)

    def search_channels(self, keyword, offset=0):
        content = self.get("/v1/search/channels", keyword=keyword, offset=offset, size=PAGE_SIZE)
        return [channel_item(entry.get("channel") or {}) for entry in content.get("data") or []], next_offset(content)

    def channel(self, channel_id):
        return channel_item(self.get(f"/v1/channels/{quote(channel_id)}") or {})

    def channel_videos(self, channel_id, page=0):
        """A page of the channel's videos, newest first, and whether more follow."""
        content = self.get(f"/v1/channels/{quote(channel_id)}/videos", sortType="LATEST", pagingType="PAGE",
                           page=page, size=PAGE_SIZE)
        return [video_item(v) for v in content.get("data") or []], page + 1 < (content.get("totalPages") or 0)

    def followings(self):
        content = self.get("/v1/channels/followings", page=0, size=505, sortType="FOLLOW")
        return [following_item(entry) for entry in content.get("followingList") or []]

    def live_stream(self, channel_id):
        content = self.get(f"/v3/channels/{quote(channel_id)}/live-detail")
        if not content or content.get("status") != "OPEN":
            raise NotLive()
        url = hls_from_playback_json(content.get("livePlaybackJson"))
        if url:
            return Stream(url, HLS)
        if content.get("adult"):
            raise AdultOnly()
        raise ChzzkError(None, "no stream")

    def video_stream(self, video_no):
        content = self.get(f"/v3/videos/{int(video_no)}") or {}
        # A recent broadcast's replay plays from the live recording.
        url = hls_from_playback_json(content.get("liveRewindPlaybackJson"))
        if url:
            return Stream(url, HLS)
        if content.get("videoId") and content.get("inKey"):
            # The playback API answers JSON unless the manifest is asked for.
            url = f"{self.vod_playback}/{quote(content['videoId'])}?" + urllib.parse.urlencode({"key": content["inKey"]})
            return Stream(url, DASH, {"Accept": DASH, "User-Agent": USER_AGENT})
        if content.get("adult"):
            raise AdultOnly()
        raise ChzzkError(None, "no stream")


def quote(value):
    return urllib.parse.quote(str(value), safe="")


def next_offset(content):
    return ((content.get("page") or {}).get("next") or {}).get("offset")


def api_message(raw):
    try:
        return json.loads(raw.decode("utf-8")).get("message")
    except (ValueError, AttributeError, UnicodeDecodeError):
        return None
