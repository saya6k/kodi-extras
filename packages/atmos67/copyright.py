"""Writes the package's copyright file: where the source is, and the license
of everything built into /usr/bin/atmos67 (atmos67, FFmpeg and each Rust
crate), taken from the sources the build used, so the notices match the code.

    copyright.py ATMOS67_SRC TARGET OUTPUT

Run after the build, with the same CARGO_HOME, so the crates are in place."""

import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG_DOC = "/opt/ffmpeg-armhf/share/doc/ffmpeg"
NOTICE_NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "UNLICENSE", "COPYRIGHT", "THIRD_PARTY_NOTICES")


# For crates under MIT that ship no license file: the standard text with
# the authors the crate names.
MIT = """  ships no license file; the MIT license it names:

  Copyright (c) {authors}

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
"""


def section(title):
    return f"\n{title}\n{'=' * len(title)}\n\n"


def source_line(name):
    for line in open(os.path.join(HERE, "atmos67-source")):
        if line.startswith(f"{name}="):
            return line.strip().split("=", 1)[1]
    raise KeyError(name)


def linked_packages(src, target):
    """The packages the binary links: those reachable from atmos67 through
    normal dependencies on the target (build and dev dependencies are not in it)."""
    meta = json.loads(subprocess.check_output(
        ["cargo", "metadata", "--format-version", "1", "--locked", "--filter-platform", target], cwd=src))
    nodes = {node["id"]: node for node in meta["resolve"]["nodes"]}
    seen, todo = set(), [meta["resolve"]["root"]]
    while todo:
        package = todo.pop()
        if package in seen:
            continue
        seen.add(package)
        todo += [dep["pkg"] for dep in nodes[package]["deps"]
                 if any(kind["kind"] is None for kind in dep["dep_kinds"])]
    packages = [p for p in meta["packages"] if p["id"] in seen and p["id"] != meta["resolve"]["root"]]
    return sorted(packages, key=lambda p: (p["name"], p["version"]))


def notice_files(package):
    """The crate's license files; a crate in a git workspace keeps them at
    the checkout's root, so look up to there."""
    directory = os.path.dirname(package["manifest_path"])
    in_git = package["source"] and package["source"].startswith("git+")
    while True:
        files = sorted(f for f in os.listdir(directory)
                       if f.upper().startswith(NOTICE_NAMES) and os.path.isfile(os.path.join(directory, f)))
        if files or not in_git or os.path.exists(os.path.join(directory, ".git")):
            return [os.path.join(directory, f) for f in files]
        directory = os.path.dirname(directory)


def main(src, target, output):
    url, rev = source_line("ATMOS67_URL"), source_line("ATMOS67_REV")
    ffmpeg_version = open(os.path.join(FFMPEG_DOC, "VERSION")).read().strip()
    gpl = open(os.path.join(src, "LICENSE")).read()
    out = [
        "atmos67: Kodi passthrough audio to per-speaker AES67 streams, packaged by kodi-extras.\n",
        "Each component below keeps its own license.\n",
        section("Corresponding source"),
        f"atmos67:   {url}/tree/{rev}\n",
        "packaging: https://github.com/saya6k/kodi-extras (packages/atmos67)\n",
        f"FFmpeg:    https://ffmpeg.org/releases/ffmpeg-{ffmpeg_version}.tar.xz, configured as in\n",
        "           packages/atmos67/Dockerfile\n",
        "Rust crates: the versions below, from crates.io or the git sources named,\n",
        "           as pinned by atmos67's Cargo.lock.\n",
        section("atmos67: GPL-3.0-only"),
        "atmos67 is free software: you can redistribute it and/or modify it under\n"
        "the terms of version 3 of the GNU General Public License as published by\n"
        "the Free Software Foundation. It links SECS 2R (AGPL-3.0-only) and conveys\n"
        "the combination under section 13 of the GPLv3; the SECS part stays under\n"
        "the AGPLv3.\n",
        section("atmos67 packaging (scripts, services, configuration): GPL-3.0-or-later"),
        "Copyright (C) 2026 saya6k\n\n"
        "This program is free software: you can redistribute it and/or modify it\n"
        "under the terms of the GNU General Public License as published by the Free\n"
        "Software Foundation, either version 3 of the License, or (at your option)\n"
        "any later version. It is distributed WITHOUT ANY WARRANTY.\n",
        section("GNU General Public License version 3"),
        gpl,
        section(f"FFmpeg {ffmpeg_version} (libavcodec, libavutil, libswresample, libavformat): LGPL-2.1-or-later"),
        open(os.path.join(FFMPEG_DOC, "COPYING.LGPLv2.1")).read(),
        section("Rust crates"),
    ]
    texts = {}
    for package in linked_packages(src, target):
        source = package["source"] or "local"
        out.append(f"{package['name']} {package['version']}: {package['license'] or 'see license files'} ({source})\n")
        files = notice_files(package)
        if not files:
            authors = ", ".join(package["authors"]) or f"the {package['name']} authors"
            if "MIT" in (package["license"] or ""):
                out.append(MIT.format(authors=authors))
            else:
                out.append(f"  ships no license file; copyright {authors}, under the license named above.\n")
        for path in files:
            text = open(path, errors="replace").read()
            digest = hashlib.sha256(text.encode()).hexdigest()[:12]
            texts.setdefault(digest, text)
            out.append(f"  {os.path.basename(path)}: text {digest} below\n")
    for digest, text in texts.items():
        out.append(section(f"License text {digest}"))
        out.append(text if text.endswith("\n") else text + "\n")
    with open(output, "w") as file:
        file.writelines(out)


if __name__ == "__main__":
    main(*sys.argv[1:])
