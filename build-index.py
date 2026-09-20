#!/usr/bin/env python3
"""Build the PixInsight update repository served at https://pixinsight.psf-guard.com/.

Reads packages.json, checks every package, and writes a directory holding
updates.xri, the package archives (flat, at the repository root, as PixInsight
resolves fileName relative to the repository URL) and index.html.

  build-index.py --check            validate packages.json and the archives
  build-index.py --out DIR          write a fresh output tree into DIR
  build-index.py --publish DIR      update a live docroot in place: archives
                                    land first, then index.html, then
                                    updates.xri, each swapped in atomically;
                                    archives no longer listed are removed last

Format reference: https://pixinsight.com/doc/docs/PIRepositoryReference/PIRepositoryReference.html
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from xml.dom import minidom

HERE = os.path.dirname(os.path.abspath(__file__))
OS_VALUES = {"any", "all", "freebsd", "linux", "macosx", "osx", "macos", "windows"}
ARCH_VALUES = {"noarch", "any", "all", "x64", "x86_64", "amd64", "arm64"}
TYPE_VALUES = {"generic", "file", "module", "script", "doc", "documentation",
               "resource", "development", "corelibs", "docsys"}
VERSION = r"\d+\.\d+\.\d+(-\d+)?(\.\d+)?"
VERSION_RANGE = re.compile(rf"^{VERSION}:{VERSION}$")
RELEASE_DATE = re.compile(r"^\d{8}(\d{2}){0,3}$")


def fail(msg):
    sys.exit(f"build-index: {msg}")


def load(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data.get("packages"), list) or not data["packages"]:
        fail("packages.json needs a non-empty 'packages' list")
    if "serverURL" in data and not re.match(r"^https://[^\s]+/$", data["serverURL"]):
        fail("serverURL must be an https URL ending in '/'")
    seen = set()
    for i, p in enumerate(data["packages"]):
        where = f"packages[{i}]"
        for key in ("file", "type", "releaseDate", "title", "description", "platforms"):
            if key not in p:
                fail(f"{where}: missing '{key}'")
        if p["type"] not in TYPE_VALUES:
            fail(f"{where}: type {p['type']!r} is not one of {sorted(TYPE_VALUES)}")
        if not RELEASE_DATE.match(p["releaseDate"]):
            fail(f"{where}: releaseDate {p['releaseDate']!r} must be YYYYMMDD[hh[mm[ss]]]")
        if not p["platforms"]:
            fail(f"{where}: needs at least one platform")
        for plat in p["platforms"]:
            if plat.get("os") not in OS_VALUES:
                fail(f"{where}: os {plat.get('os')!r} is not one of {sorted(OS_VALUES)}")
            if plat.get("arch") not in ARCH_VALUES:
                fail(f"{where}: arch {plat.get('arch')!r} is not one of {sorted(ARCH_VALUES)}")
            if not VERSION_RANGE.match(plat.get("version", "")):
                fail(f"{where}: version {plat.get('version')!r} must be 'from:to', e.g. 1.9.4:1.9.99")
        src = os.path.join(HERE, p["file"])
        if not os.path.isfile(src):
            fail(f"{where}: file not found: {p['file']}")
        name = os.path.basename(p["file"])
        if name in seen:
            fail(f"{where}: duplicate archive name {name}")
        seen.add(name)
        p["_src"] = src
        p["_name"] = name
        with open(src, "rb") as fh:
            p["_sha1"] = hashlib.sha1(fh.read()).hexdigest()
    return data


def paragraphs(parent, items):
    if isinstance(items, str):
        items = [items]
    for text in items:
        ET.SubElement(parent, "p").text = text


def build_xri(data):
    xri = ET.Element("xri", version="1.0")
    paragraphs(ET.SubElement(xri, "description"), data.get("description", []))
    groups = {}
    for p in data["packages"]:
        for plat in p["platforms"]:
            key = (plat["os"], plat["arch"], plat["version"])
            groups.setdefault(key, []).append(p)
    for (os_, arch, version), packages in groups.items():
        platform = ET.SubElement(xri, "platform", os=os_, arch=arch, version=version)
        for p in packages:
            package = ET.SubElement(platform, "package", fileName=p["_name"], sha1=p["_sha1"],
                                    type=p["type"], releaseDate=p["releaseDate"])
            # PixInsight resolves fileName against the repository URL as the
            # user typed it, and a URL with no path after the host ends up as
            # "https://<fileName>". serverURL pins the base explicitly.
            if data.get("serverURL"):
                package.set("serverURL", data["serverURL"])
            ET.SubElement(package, "title").text = p["title"]
            paragraphs(ET.SubElement(package, "description"), p["description"])
    pretty = minidom.parseString(ET.tostring(xri, encoding="unicode")).toprettyxml(indent="   ")
    # minidom emits its own declaration; keep exactly one, in the PixInsight form.
    body = pretty.split("\n", 1)[1]
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def stage(directory, name, payload=None, src=None):
    """Write payload (bytes) or copy src into a temporary file in directory."""
    fd, temporary = tempfile.mkstemp(prefix=".build-index-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            if src is not None:
                with open(src, "rb") as sfh:
                    shutil.copyfileobj(sfh, fh)
            else:
                fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(temporary, 0o644)
        return temporary
    except BaseException:
        os.remove(temporary)
        raise


def publish(data, directory, xri, index):
    os.makedirs(directory, exist_ok=True)
    staged = []
    try:
        # Archives first, so updates.xri never points at a missing file.
        for p in data["packages"]:
            staged.append((stage(directory, p["_name"], src=p["_src"]), os.path.join(directory, p["_name"])))
        staged.append((stage(directory, "index.html", payload=index), os.path.join(directory, "index.html")))
        staged.append((stage(directory, "updates.xri", payload=xri.encode("utf-8")), os.path.join(directory, "updates.xri")))
        for temporary, target in staged:
            os.replace(temporary, target)
        staged.clear()
    finally:
        for temporary, _ in staged:
            try:
                os.remove(temporary)
            except FileNotFoundError:
                pass
    listed = {p["_name"] for p in data["packages"]}
    for name in sorted(os.listdir(directory)):
        if name.endswith(".zip") and name not in listed:
            os.remove(os.path.join(directory, name))
            print(f"removed stale archive {name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--out", metavar="DIR")
    mode.add_argument("--publish", metavar="DIR")
    args = ap.parse_args()

    data = load(os.path.join(HERE, "packages.json"))
    index_path = os.path.join(HERE, "index.html")
    if not os.path.isfile(index_path):
        fail("index.html not found")
    with open(index_path, "rb") as fh:
        index = fh.read()
    xri = build_xri(data)

    if args.check:
        for p in data["packages"]:
            print(f"ok {p['_name']} sha1={p['_sha1']} {p['title']}")
        print(f"ok {len(data['packages'])} package(s)")
        return
    target = args.out or args.publish
    if args.out:
        if os.path.exists(target) and os.listdir(target):
            fail(f"--out directory is not empty: {target}")
    publish(data, target, xri, index)
    print(f"wrote {len(data['packages'])} package(s) to {target}")


if __name__ == "__main__":
    main()
