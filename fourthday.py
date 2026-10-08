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
MIN_SHORT_SIDE = 1000
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


def is_public_domain(credit, copyright_):
    """APOD: keep agency images; skip anything marked copyright/license or credited only to a person."""
    text = strip_html(credit) + " " + strip_html(copyright_)
    if re.search(r"copyright|licen[sc]e|\u00a9|\(c\)", text, re.I):
        return False
    return bool(re.search(r"\b(NASA|ESA|ESO|NOIRLab|JPL|STScI|NSF|CSA|JAXA|SDO|Hubble|Webb|Chandra|"
                          r"Juno|Cassini|Gemini|CTIO|KPNO|Rubin)\b", text))


def src_apod():
    """NASA APOD via the new science.nasa.gov endpoint. Skips copyrighted images."""
    url = "https://science.nasa.gov/wp-json/wp/v2/apod-basic"
    pages = list(range(1, 40))
    random.shuffle(pages)
    for page in pages[:10]:
        try:
            items = get(url, params={"per_page": 50, "page": page}).json()
        except Exception as e:  # noqa: BLE001
            log("  apod page %d: %s" % (page, e))
            continue
        if isinstance(items, dict):
            items = items.get("items") or items.get("data") or []
        n_img = n_pd = 0
        if items:
            log("  apod sample credit=%r copyright=%r" % (strip_html(items[0].get("credit"))[:80],
                                                          strip_html(items[0].get("copyright"))[:80]))
        for it in items:
            if it.get("media_type") != "image":
                continue
            n_img += 1
            if not is_public_domain(it.get("credit") or "", it.get("copyright") or ""):
                continue
            n_pd += 1
            img = it.get("hdurl") or it.get("url") or ""
            if "apod-basic" in img or "/image-article/" in img:
                continue
            desc = re.sub(r"^\s*Explanation:\s*", "", strip_html(it.get("explanation")))
            yield {
                "key": "apod:%s" % it.get("date"),
                "source": "NASA APOD",
                "title": strip_html(it.get("title")),
                "description": desc,
                "credit": re.sub(r"^\s*(Image|Video)?\s*Credits?\s*:\s*", "",
                                 strip_html(it.get("credit"))) or "NASA",
                "image_url": img,
                "page_url": it.get("permalink") or it.get("url"),
                "date": it.get("date"),
            }
        log("  apod page %d: %d items, %d images, %d public domain" % (page, len(items), n_img, n_pd))


NASA_QUERIES = [
    "nebula", "galaxy", "star cluster", "supernova remnant", "spiral galaxy",
    "Hubble nebula", "Webb galaxy", "Chandra", "planetary nebula", "star forming region",
    "Jupiter Juno", "Saturn Cassini", "Mars surface", "Moon", "aurora from space",
]
NASA_BAD = re.compile(
    r"\b(astronaut|engineer|technician|test|launch|rollout|crew|ceremony|history|model|"
    r"hardware|assembly|poster|logo|annotated|labell?ed|comparison|infographic|"
    r"briefing|meeting|clean ?room|mockup|artist|illustration|concept|rendering|"
    r"animation|graphic|chart|diagram)\b", re.I)


def src_nasa_images():
    """NASA Image and Video Library (public domain, NASA credit)."""
    queries = NASA_QUERIES[:]
    random.shuffle(queries)
    items = []
    for q in queries[:4]:
        try:
            data = get("https://images-api.nasa.gov/search",
                       params={"q": q, "media_type": "image", "page": random.randint(1, 3)}).json()
        except Exception as e:  # noqa: BLE001
            log("  nasa search %r: %s" % (q, e))
            continue
        found = data.get("collection", {}).get("items", [])
        log("  nasa search %r: %d results" % (q, len(found)))
        items += found
    random.shuffle(items)
    for it in items:
        d = (it.get("data") or [{}])[0]
        text = "%s %s %s" % (d.get("title", ""), d.get("description", ""), " ".join(d.get("keywords") or []))
        if NASA_BAD.search(text) or not ASTRO_CATEGORY.search(text):
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
    cats = ["galaxies", "nebulae", "starclusters", "stars", "solarsystem"]
    random.shuffle(cats)
    cat = base + "archive/category/%s/" % cats[0]
    urls = [cat + "page/%d/" % random.randint(2, 6), cat, base + "archive/category/%s/" % cats[1], base]
    for url in urls:
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
        if i not in seen and i not in ("page", "archive", "potw", "potm", "iotw", "feed", "search", "viewall", "list"):
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
    # The text right after the page title, up to the "About the Image" box.
    body = strip_html(t.split("About the Image")[0])
    idx = body.rfind(title) if title else -1
    desc = body[idx + len(title):].strip() if idx >= 0 else ""
    alt = ""
    m = re.search(r"\[Image Description:(.*?)\]", desc, re.S)
    if m:
        alt = m.group(1).strip()
        desc = desc[:m.start()].strip()
    if len(desc) < 80 or len(desc) > 8000:
        desc = meta("og:description") or meta("description")

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
        "alt_text": alt,
        "distance": field("Distance"),
        "name": field("Name"),
        "constellation": field("Constellation"),
        "type": field("Type"),
        "category": ", ".join(strip_html(c) for c in re.findall(
            r'href=["\'][^"\']*/images/archive/category/[^"\']*["\'][^>]*>(.*?)</a>',
            t.split("About the Object", 1)[-1] if "About the Object" in t else "", re.S)),
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


ASTRO_CATEGORY = re.compile(
    r"nebula|galax|star|cluster|solar system|planet|comet|sky|moon|sun|quasar|black hole|"
    r"cosmolog|milky way|aurora|eclipse|supernova|asteroid", re.I)
BAD_TYPE = re.compile(r"artwork|illustration|chart|animation|\bgraphic|logo", re.I)


def materialize(cand):
    """Fill in metadata, download and check the image. Returns the image, or raises ValueError."""
    if "lazy_meta" in cand:
        cand.update(cand.pop("lazy_meta")())
    if not cand.get("title") or not cand.get("description"):
        raise ValueError("missing title/description")
    if NASA_BAD.search(cand["title"]) or BAD_TYPE.search(cand.get("type") or ""):
        raise ValueError("not an astronomical photo (%s / %s)" % (cand["title"], cand.get("type")))
    if "category" in cand and not ASTRO_CATEGORY.search(cand["category"] or ""):
        raise ValueError("category not astronomical (%r)" % cand["category"])
    url = cand["image_url"]() if callable(cand["image_url"]) else cand["image_url"]
    if not url:
        raise ValueError("no image file")
    cand["image_url"] = url
    im = download_image(url)
    w, h = im.size
    ratio = (w / h) / (TARGET_W / TARGET_H)
    if min(ratio, 1 / ratio) < MAX_CROP_LOSS:
        raise ValueError("shape too far from 4:5 (%dx%d)" % (w, h))
    if min(w, h * TARGET_W / TARGET_H) < MIN_SHORT_SIDE:
        raise ValueError("too small (%dx%d)" % (w, h))
    return im


def prepare_one(known, sources, tries_per_source=25):
    for src in sources:
        log("source: %s" % src.__name__)
        try:
            tries = 0
            for cand in src():
                if cand["key"] in known:
                    continue
                tries += 1
                if tries > tries_per_source:
                    break
                try:
                    im = materialize(cand)
                except Exception as e:  # noqa: BLE001
                    log("  skip %s: %s" % (cand["key"], e))
                    known.add(cand["key"])
                    continue
                w, h = im.size
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
    """Find one usable image per source and report, without touching the queue."""
    ok = 0
    known = known_keys()
    for src in SOURCES:
        log("== %s" % src.__name__)
        found = None
        try:
            for i, cand in enumerate(src()):
                if i >= 25:
                    break
                if cand["key"] in known:
                    continue
                try:
                    im = materialize(cand)
                except Exception as e:  # noqa: BLE001
                    log("  skip %s: %s" % (cand["key"], e))
                    continue
                found = (cand, im)
                break
        except Exception as e:  # noqa: BLE001
            log("  source failed: %r" % e)
        if found:
            cand, im = found
            ok += 1
            log("OK   %s | %s | %dx%d | dist=%r | type=%r | cat=%r | credit=%r | desc=%d chars" % (
                cand["key"], cand.get("title"), im.size[0], im.size[1], cand.get("distance"),
                cand.get("type"), cand.get("category"), cand.get("credit"), len(cand.get("description") or "")))
            log("     desc: %s..." % (cand.get("description") or "")[:160].replace("\n", " "))
        else:
            log("FAIL %s: nothing usable" % src.__name__)
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
