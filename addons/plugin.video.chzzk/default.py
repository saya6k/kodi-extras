"""The plugin's folders and playback. Kodi calls it with the plugin URL
(plugin://plugin.video.chzzk/<route>?<query>), the folder handle and the query."""

import json
import sys
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

import chzzk

ADDON = xbmcaddon.Addon()
ROOT = f"plugin://{ADDON.getAddonInfo('id')}/"
HANDLE = int(sys.argv[1])


def text(string_id):
    return ADDON.getLocalizedString(string_id)


def client():
    return chzzk.Chzzk(ADDON.getSetting("nid_aut"), ADDON.getSetting("nid_ses"))


def url(route, **query):
    return f"{ROOT}{route}" + (f"?{urllib.parse.urlencode(query)}" if query else "")


def folder(label, route, art=None, **query):
    item = xbmcgui.ListItem(label)
    if art:
        item.setArt(art)
    xbmcplugin.addDirectoryItem(HANDLE, url(route, **query), item, isFolder=True)


def adult_mark(item):
    return f"[19] {item}" if item else item


def add_live(live):
    label = live["channel_name"]
    if live["adult"]:
        label = adult_mark(label)
    item = xbmcgui.ListItem(f"{label} - {live['title']}")
    item.setArt({"thumb": live["thumbnail"] or live["channel_image"], "icon": live["channel_image"],
                 "fanart": live["thumbnail"]})
    tag = item.getVideoInfoTag()
    tag.setTitle(live["title"])
    tag.setPlot(f"{live['channel_name']}\n{live['category']}\n{text(32030) % live['viewers']}")
    tag.setGenres([live["category"]] if live["category"] else [])
    item.setProperty("IsPlayable", "true")
    item.addContextMenuItems([(text(32031), f"Container.Update({url('channel', id=live['channel_id'])})")])
    xbmcplugin.addDirectoryItem(HANDLE, url("play_live", id=live["channel_id"]), item, isFolder=False)


def add_channel(channel):
    label = channel["channel_name"]
    if channel.get("live"):
        label = f"[LIVE] {label}"
    item = xbmcgui.ListItem(label)
    item.setArt({"thumb": channel["channel_image"], "icon": channel["channel_image"]})
    plot = channel.get("title") or channel.get("description") or ""
    item.getVideoInfoTag().setPlot(plot)
    xbmcplugin.addDirectoryItem(HANDLE, url("channel", id=channel["channel_id"]), item, isFolder=True)


def add_video(video):
    label = adult_mark(video["title"]) if video["adult"] else video["title"]
    item = xbmcgui.ListItem(label)
    item.setArt({"thumb": video["thumbnail"], "fanart": video["thumbnail"]})
    tag = item.getVideoInfoTag()
    tag.setTitle(video["title"])
    tag.setDuration(int(video["duration"]))
    tag.setPremiered(video["date"])
    tag.setGenres([video["category"]] if video["category"] else [])
    item.setProperty("IsPlayable", "true")
    xbmcplugin.addDirectoryItem(HANDLE, url("play_video", no=video["video_no"]), item, isFolder=False)


def next_page(route, **query):
    folder(f"[{text(32032)}]", route, **query)


def end(content="videos"):
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE)


def root(_query):
    folder(text(32010), "popular")
    folder(text(32011), "search_lives")
    folder(text(32012), "search_channels")
    if client().logged_in:
        folder(text(32013), "followings")
    end("files")


def popular(query):
    cursor = json.loads(query["cursor"]) if "cursor" in query else None
    lives, next_cursor = client().popular_lives(cursor)
    for live in lives:
        add_live(live)
    if next_cursor:
        next_page("popular", cursor=json.dumps(next_cursor))
    end()


def ask_keyword(query):
    if query.get("keyword"):
        return query["keyword"]
    return xbmcgui.Dialog().input(text(32033))


def search_lives(query):
    keyword = ask_keyword(query)
    if not keyword:
        return end()
    lives, offset = client().search_lives(keyword, int(query.get("offset", 0)))
    for live in lives:
        add_live(live)
    if offset:
        next_page("search_lives", keyword=keyword, offset=offset)
    end()


def search_channels(query):
    keyword = ask_keyword(query)
    if not keyword:
        return end()
    channels, offset = client().search_channels(keyword, int(query.get("offset", 0)))
    for channel in channels:
        add_channel(channel)
    if offset:
        next_page("search_channels", keyword=keyword, offset=offset)
    end("files")


def followings(_query):
    channels = client().followings()
    # Live channels first, as the web client lists them.
    for channel in sorted(channels, key=lambda c: not c["live"]):
        add_channel(channel)
    end("files")


def channel(query):
    channel_id = query["id"]
    api = client()
    page = int(query.get("page", 0))
    if page == 0:
        info = api.channel(channel_id)
        if info["live"]:
            item = xbmcgui.ListItem(f"[LIVE] {info['channel_name']}")
            item.setArt({"thumb": info["channel_image"], "icon": info["channel_image"]})
            item.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(HANDLE, url("play_live", id=channel_id), item, isFolder=False)
    videos, more = api.channel_videos(channel_id, page)
    for video in videos:
        add_video(video)
    if more:
        next_page("channel", id=channel_id, page=page + 1)
    end()


def play(stream):
    item = xbmcgui.ListItem(path=stream.kodi_path())
    item.setMimeType(stream.mime)
    item.setContentLookup(False)
    item.setProperty("inputstream", "inputstream.adaptive")
    # Kodi 20 needs the type; inputstream.adaptive 21 and later work it out.
    item.setProperty("inputstream.adaptive.manifest_type", "mpd" if stream.mime == chzzk.DASH else "hls")
    if stream.headers:
        item.setProperty("inputstream.adaptive.manifest_headers", urllib.parse.urlencode(stream.headers, quote_via=urllib.parse.quote))
    xbmcplugin.setResolvedUrl(HANDLE, True, item)


def play_live(query):
    play(client().live_stream(query["id"]))


def play_video(query):
    play(client().video_stream(query["no"]))


ROUTES = {
    "": root, "popular": popular, "search_lives": search_lives, "search_channels": search_channels,
    "followings": followings, "channel": channel, "play_live": play_live, "play_video": play_video,
}
PLAYBACK = {"play_live", "play_video"}


def message(error):
    if isinstance(error, chzzk.NotLive):
        return text(32040)
    if isinstance(error, chzzk.AdultOnly):
        return text(32041)
    if error.status == 401:
        return text(32042)
    if error.status is None:
        return text(32043) % error
    return text(32044) % error


def main():
    route = urllib.parse.urlparse(sys.argv[0]).path.strip("/")
    query = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip("?")))
    try:
        ROUTES[route](query)
    except chzzk.ChzzkError as error:
        xbmc.log(f"plugin.video.chzzk: {route}: {error.status} {error}", xbmc.LOGWARNING)
        xbmcgui.Dialog().notification(ADDON.getAddonInfo("name"), message(error), xbmcgui.NOTIFICATION_ERROR)
        if route in PLAYBACK:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        else:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


if __name__ == "__main__":
    main()
