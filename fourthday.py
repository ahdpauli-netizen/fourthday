#!/usr/bin/env python3
"""Fourth Day: automatic astrophotography posts for Instagram @fourthday_.

Commands:
  prepare [--count N]     Fill queue/ with up to N new images (cropped JPEG + meta.json).
  publish [--dry-run]     Publish the oldest queued item that has a caption.txt.
  refresh-token           Refresh the long-lived Instagram token (valid for 60 days).
  check-token             Show which account the token belongs to (no posting).

Secrets come only from environment variables, never from files in this repo:
  IG_ACCESS_TOKEN   Instagram long-lived token (required for publish/refresh/check)
  NASA_API_KEY      NASA api.nasa.gov key (optional, used only as an APOD fallback)
"""

import argparse
import datetime as dt
import html
import io
import json
import os
import random
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "queue"
POSTED = ROOT / "posted"
HISTORY = ROOT / "history.json"

IG_USER_ID = os.environ.get("IG_USER_ID", "17841479712033797")
IG_API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
REPO = os.environ.get("GITHUB_REPOSITORY", "ahdpauli-netizen/fourthday")
BRANCH = os.environ.get("PUBLISH_BRANCH", "main")

TARGET_W, TARGET_H = 1080, 1350  # 4:5 portrait
MIN_SHORT_SIDE = 1080
MAX_CROP_LOSS = 0.5  # skip images where the 4:5 crop would keep less than half the width/height
MAX_DOWNLOAD = 80 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 400_000_000

UA = {"User-Agent": "fourthday-bot/1.0 (+https://github.com/%s)" % REPO}
session = requests.Session()
session.headers.update(UA)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url, **kw):
    kw.setdefault("timeout", 60)
    r = session.get(url, **kw)
    r.raise_for_status()
    return r


def strip_html(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", s)).strip()


# ---------------------------------------------------------------- sources
# Each source yields candidate dicts:
#   key, source, title, description, credit, image_url, page_url, distance (optional)


def src_apod():
    """NASA APOD via the new science.nasa.gov endpoint. Skips copyrighted images."""
    page = random.randint(1, 30)
    url = "https://science.nasa.gov/wp-json/wp/v2/apod-basic"
    items = get(url, params={"per_page": 50, "page": page}).json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("data") or []
    for it in items:
        if it.get("media_type") != "image" or strip_html(it.get("copyright") or ""):
            continue
        img = it.get("hdurl") or ""
        if not re.search(r"\.(jpe?g|png)(\?|$)", img, re.I):
            continue
        desc = re.sub(r"^\s*Explanation:\s*", "", strip_html(it.get("explanation")))
        yield {
            "key": "apod:%s" % it.get("date"),
            "source": "NASA APOD",
            "title": strip_html(it.get("title")),
            "description": desc,
            "credit": strip_html(it.get("credit")) or "NASA",
            "image_url": img,
            "page_url": it.get("permalink") or it.get("url"),
            "date": it.get("date"),
        }


NASA_QUERIES = [
    "nebula", "galaxy", "star cluster", "supernova remnant", "spiral galaxy",
    "Hubble nebula", "Webb galaxy", "Chandra", "planetary nebula", "star forming region",
    "Jupiter Juno", "Saturn Cassini", "Mars surface", "Moon", "aurora from space",
]
NASA_BAD = re.compile(
    r"\b(astronaut|engineer|technician|test|launch|rollout|crew|ceremony|portrait|"
    r"briefing|meeting|clean ?room|mockup|artist|illustration|concept|rendering|"
    r"animation|graphic|chart|diagram)\b", re.I)


def src_nasa_images():
    """NASA Image and Video Library (public domain, NASA credit)."""
    q = random.choice(NASA_QUERIES)
    data = get("https://images-api.nasa.gov/search",
               params={"q": q, "media_type": "image", "page": random.randint(1, 5)}).json()
    items = data.get("collection", {}).get("items", [])
    random.shuffle(items)
    for it in items:
        d = (it.get("data") or [{}])[0]
        text = "%s %s %s" % (d.get("title", ""), d.get("description", ""), " ".join(d.get("keywords") or []))
        if NASA_BAD.search(text):
            continue
        nasa_id = d.get("nasa_id")
        if not nasa_id:
            continue
        yield {
            "key": "nasa:%s" % nasa_id,
            "source": "NASA Image Library",
            "title": d.get("title", "").strip(),
            "description": strip_html(d.get("description", "")),
            "credit": (d.get("secondary_creator") or d.get("photographer") or "NASA").strip(),
            "image_url": lambda nid=nasa_id: nasa_asset(nid),
            "page_url": "https://images.nasa.gov/details/%s" % nasa_id,
            "date": (d.get("date_created") or "")[:10],
        }


def nasa_asset(nasa_id):
    files = [x["href"] for x in get("https://images-api.nasa.gov/asset/%s" % nasa_id).json()
             ["collection"]["items"]]
    for suffix in ("~large.jpg", "~orig.jpg", "~medium.jpg"):
        for f in files:
            if f.lower().endswith(suffix):
                return f.replace("http://", "https://")
    return None


# djangoplicity sites (ESA/Webb, ESA/Hubble, ESO, NOIRLab) share one layout.
DJANGO_SITES = {
    "esawebb": {"name": "ESA/Webb", "base": "https://esawebb.org/images/",
                "large": "https://cdn.esawebb.org/archives/images/large/{id}.jpg",
                "credit": "ESA/Webb, NASA & CSA"},
    "esahubble": {"name": "ESA/Hubble", "base": "https://esahubble.org/images/",
                  "large": "https://cdn.esahubble.org/archives/images/large/{id}.jpg",
                  "credit": "ESA/Hubble & NASA"},
    "eso": {"name": "ESO", "base": "https://www.eso.org/public/images/",
            "large": "https://cdn.eso.org/images/large/{id}.jpg",
            "credit": "ESO"},
    "noirlab": {"name": "NOIRLab", "base": "https://noirlab.edu/public/images/",
                "large": "https://noirlab.edu/public/media/archives/images/large/{id}.jpg",
                "credit": "NOIRLab/NSF/AURA"},
}
DJANGO_SKIP = re.compile(r"(^|[^a-z])(art|ann|anim|fig|chart|graph|logo|org|ext|outreach|pho|eso-)", re.I)


def django_ids(site):
    """Image ids from a random page of the site's image archive (and its feed)."""
    base = site["base"]
    ids = []
    page = random.randint(1, 25)
    for url in (base + "page/%d/" % page, base):
        try:
            text = get(url).text
        except Exception as e:  # noqa: BLE001
            log("  %s: %s" % (url, e))
            continue
        path = re.escape(re.sub(r"^https://[^/]+", "", base))
        ids += re.findall(r'(?:href=["\']|["\']url["\']\s*:\s*["\']|id["\']?\s*:\s*["\'])%s([a-z0-9-]+)/' % path, text)
        ids += re.findall(r'\bid\s*:\s*["\']([a-z0-9-]+)["\']', text)
        if ids:
            break
    seen, out = set(), []
    for i in ids:
        if i not in seen and i not in ("page", "archive", "potw", "potm", "iotw", "feed", "search"):
            seen.add(i)
            out.append(i)
    return out


def django_meta(site, image_id):
    page_url = site["base"] + image_id + "/"
    t = get(page_url).text

    def meta(prop):
        m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']*)' % prop, t, re.I) \
            or re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']%s["\']' % prop, t, re.I)
        return html.unescape(m.group(1)).strip() if m else ""

    title = meta("og:title") or strip_html((re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S) or [None, ""])[1])
    title = re.sub(r"\s*\|\s*(ESA/Webb|ESA/Hubble|ESO|NOIRLab).*$", "", title)
    # Full description: paragraphs of the main column before the "About the Image" box.
    body = t.split("About the Image")[0]
    paras = [strip_html(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
    paras = [p for p in paras if len(p) > 60 and "cookie" not in p.lower()]
    desc = "\n\n".join(paras[:8]) or meta("og:description") or meta("description")

    def field(label):
        m = re.search(r">\s*%s:?\s*</(?:td|th|div|span|strong|b)>\s*<(?:td|div|span)[^>]*>(.*?)</(?:td|div|span)>"
                      % label, t, re.S | re.I)
        return strip_html(m.group(1)) if m else ""

    credit = field("Credit") or ""
    if not credit:
        m = re.search(r"Credit:\s*</[^>]+>\s*(.*?)</(?:div|p)>", t, re.S | re.I)
        credit = strip_html(m.group(1)) if m else site["credit"]
    return {
        "title": title,
        "description": desc,
        "credit": credit,
        "distance": field("Distance"),
        "name": field("Name"),
        "constellation": field("Constellation"),
        "type": field("Type"),
        "page_url": page_url,
    }


def make_django_source(slug):
    site = DJANGO_SITES[slug]

    def src():
        ids = django_ids(site)
        random.shuffle(ids)
        for image_id in ids:
            if DJANGO_SKIP.search(image_id):
                continue
            key = "%s:%s" % (slug, image_id)

            def lazy(image_id=image_id):
                return site["large"].format(id=image_id)

            yield {"key": key, "source": site["name"], "image_url": lazy,
                   "lazy_meta": lambda image_id=image_id: django_meta(site, image_id)}

    src.__name__ = "src_" + slug
    return src


SOURCES = [src_apod, src_nasa_images] + [make_django_source(s) for s in DJANGO_SITES]


# ---------------------------------------------------------------- image work


def download_image(url):
    r = session.get(url, timeout=120, stream=True)
    r.raise_for_status()
    buf = io.BytesIO()
    for chunk in r.iter_content(1 << 16):
        buf.write(chunk)
        if buf.tell() > MAX_DOWNLOAD:
            raise ValueError("image too large to download")
    buf.seek(0)
    im = Image.open(buf)
    im = ImageOps.exif_transpose(im)
    return im.convert("RGB")


def smart_crop(im, tw=TARGET_W, th=TARGET_H):
    """Crop to tw:th around the brightest area (where astronomical objects usually are)."""
    w, h = im.size
    target = tw / th
    if w / h > target:  # too wide: choose x
        cw, ch = int(round(h * target)), h
    else:  # too tall: choose y
        cw, ch = w, int(round(w / target))
    small = im.convert("L").resize((max(1, w // 16), max(1, h // 16))).filter(ImageFilter.GaussianBlur(4))
    sw, sh = small.size
    px = small.load()
    tot = sx = sy = 0.0
    for y in range(sh):
        for x in range(sw):
            v = px[x, y] ** 2
            tot += v
            sx += v * x
            sy += v * y
    cx = (sx / tot + 0.5) * w / sw if tot else w / 2
    cy = (sy / tot + 0.5) * h / sh if tot else h / 2
    # Blend toward the centre so the crop does not hug an edge.
    cx = 0.6 * cx + 0.4 * w / 2
    cy = 0.6 * cy + 0.4 * h / 2
    left = int(min(max(cx - cw / 2, 0), w - cw))
    top = int(min(max(cy - ch / 2, 0), h - ch))
    return im.crop((left, top, left + cw, top + ch)).resize((tw, th), Image.LANCZOS)


def save_jpeg(im, path):
    for q in (92, 88, 82, 75):
        im.save(path, "JPEG", quality=q, optimize=True, progressive=True)
        if path.stat().st_size < 7.5 * 1024 * 1024:
            return
    raise ValueError("could not get JPEG under 8 MB")


# ---------------------------------------------------------------- history / queue


def load_history():
    if HISTORY.exists():
        return json.loads(HISTORY.read_text())
    return {"posted": {}}


def save_history(h):
    HISTORY.write_text(json.dumps(h, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def known_keys():
    keys = set(load_history()["posted"])
    for d in QUEUE.glob("*/meta.json"):
        keys.add(json.loads(d.read_text())["key"])
    return keys


def queue_items():
    return sorted(p for p in QUEUE.glob("*") if (p / "meta.json").exists())


def prepare_one(known, rng_sources):
    for src in rng_sources:
        log("source: %s" % src.__name__)
        try:
            for cand in src():
                if cand["key"] in known:
                    continue
                try:
                    if "lazy_meta" in cand:
                        cand.update(cand.pop("lazy_meta")())
                    url = cand["image_url"]() if callable(cand["image_url"]) else cand["image_url"]
                    if not url:
                        continue
                    cand["image_url"] = url
                    if not cand.get("title") or not cand.get("description"):
                        continue
                    if NASA_BAD.search(cand["title"]):
                        continue
                    im = download_image(url)
                    w, h = im.size
                    ratio = (w / h) / (TARGET_W / TARGET_H)
                    if min(ratio, 1 / ratio) < MAX_CROP_LOSS:
                        log("  skip %s: shape too far from 4:5 (%dx%d)" % (cand["key"], w, h))
                        known.add(cand["key"])
                        continue
                    if min(w, h * TARGET_W / TARGET_H) < MIN_SHORT_SIDE:
                        log("  skip %s: too small (%dx%d)" % (cand["key"], w, h))
                        known.add(cand["key"])
                        continue
                except Exception as e:  # noqa: BLE001
                    log("  skip %s: %s" % (cand["key"], e))
                    continue
                slug = re.sub(r"[^a-z0-9]+", "-", cand["key"].lower()).strip("-")[:60]
                stamp = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
                d = QUEUE / ("%s-%s" % (stamp, slug))
                d.mkdir(parents=True)
                save_jpeg(smart_crop(im), d / "image.jpg")
                cand["original_size"] = [w, h]
                cand["prepared_at"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
                (d / "meta.json").write_text(json.dumps(cand, indent=2, ensure_ascii=False) + "\n")
                known.add(cand["key"])
                log("  queued %s -> %s" % (cand["key"], d.relative_to(ROOT)))
                return d
        except Exception as e:  # noqa: BLE001
            log("  source failed: %s" % e)
    return None


def cmd_selftest(args):
    """Try every source once and report, without touching the queue."""
    ok = 0
    for src in SOURCES:
        try:
            cand = next(iter(src()))
            if "lazy_meta" in cand:
                cand.update(cand.pop("lazy_meta")())
            url = cand["image_url"]() if callable(cand["image_url"]) else cand["image_url"]
            im = download_image(url)
            log("OK   %-18s %s | %s | %dx%d | dist=%r | credit=%r | desc=%d chars" % (
                src.__name__, cand["key"], cand.get("title"), im.size[0], im.size[1],
                cand.get("distance"), cand.get("credit"), len(cand.get("description") or "")))
            ok += 1
        except Exception as e:  # noqa: BLE001
            log("FAIL %-18s %r" % (src.__name__, e))
    log("%d/%d sources working" % (ok, len(SOURCES)))


def cmd_prepare(args):
    QUEUE.mkdir(exist_ok=True)
    known = known_keys()
    have = len(queue_items())
    made = []
    # Rotate sources so the feed mixes observatories; start after the last one used.
    order = SOURCES[:]
    random.shuffle(order)
    while have + len(made) < args.count:
        d = prepare_one(known, order)
        if not d:
            log("no new image found this round")
            break
        made.append(d)
        order = order[1:] + order[:1]
    print(json.dumps([str(d.relative_to(ROOT)) for d in made]))


# ---------------------------------------------------------------- Instagram


def ig(method, path, **params):
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        sys.exit("IG_ACCESS_TOKEN is not set")
    params["access_token"] = token
    url = "%s/%s" % (IG_API, path)
    r = session.request(method, url, params=params if method == "GET" else None,
                        data=params if method != "GET" else None, timeout=60)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:500]}
    if r.status_code >= 400 or "error" in body:
        sys.exit("Instagram API error %s: %s" % (r.status_code, json.dumps(body.get("error", body))))
    return body


def raw_url(path):
    return "https://raw.githubusercontent.com/%s/%s/%s" % (REPO, BRANCH, path.relative_to(ROOT).as_posix())


def cmd_publish(args):
    items = [d for d in queue_items() if (d / "caption.txt").exists()]
    if not items:
        sys.exit("No queued item has a caption.txt yet; nothing to publish.")
    d = items[0]
    meta = json.loads((d / "meta.json").read_text())
    caption = (d / "caption.txt").read_text().strip()
    if len(caption) > 2200:
        sys.exit("Caption is %d characters; Instagram allows 2200." % len(caption))
    if len(re.findall(r"#\w", caption)) > 30:
        sys.exit("Caption has more than 30 hashtags.")
    url = raw_url(d / "image.jpg")
    log("item:    %s\nimage:   %s\nchars:   %d" % (d.name, url, len(caption)))
    if args.dry_run:
        print("DRY RUN, nothing published.\n\n" + caption)
        return
    head = session.head(url, timeout=30)
    if head.status_code != 200:
        sys.exit("Image URL is not public yet (%s): %s" % (head.status_code, url))
    container = ig("POST", "%s/media" % IG_USER_ID, image_url=url, caption=caption)["id"]
    for _ in range(30):
        st = ig("GET", container, fields="status_code,status").get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            sys.exit("Media container failed: %s" % st)
        time.sleep(5)
    media_id = ig("POST", "%s/media_publish" % IG_USER_ID, creation_id=container)["id"]
    link = ig("GET", media_id, fields="permalink").get("permalink")
    POSTED.mkdir(exist_ok=True)
    dest = POSTED / d.name
    shutil.move(str(d), str(dest))
    h = load_history()
    h["posted"][meta["key"]] = {
        "media_id": media_id, "permalink": link, "title": meta.get("title"),
        "folder": str(dest.relative_to(ROOT)),
        "posted_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    save_history(h)
    print("Published: %s" % link)


def cmd_refresh(args):
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        sys.exit("IG_ACCESS_TOKEN is not set")
    r = session.get("https://graph.instagram.com/refresh_access_token",
                    params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    body = r.json()
    if "access_token" not in body:
        sys.exit("Refresh failed: %s" % json.dumps(body.get("error", body)))
    days = int(body.get("expires_in", 0)) // 86400
    log("Token refreshed; valid for %d more days." % days)
    out = os.environ.get("GITHUB_OUTPUT")
    if out and body["access_token"] != token:
        print("::add-mask::" + body["access_token"])
        with open(out, "a") as f:
            f.write("new_token=%s\nchanged=true\n" % body["access_token"])


def cmd_check(args):
    me = ig("GET", "me", fields="user_id,username,account_type")
    print(json.dumps(me))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("prepare")
    pp.add_argument("--count", type=int, default=3)
    pb = sub.add_parser("publish")
    pb.add_argument("--dry-run", action="store_true")
    sub.add_parser("selftest")
    sub.add_parser("refresh-token")
    sub.add_parser("check-token")
    args = p.parse_args()
    {"prepare": cmd_prepare, "selftest": cmd_selftest, "publish": cmd_publish,
     "refresh-token": cmd_refresh, "check-token": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    main()
