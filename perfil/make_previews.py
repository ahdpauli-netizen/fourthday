"""Downloads candidate profile pictures and makes round previews (Instagram style)."""
import io, json, sys, urllib.parse, urllib.request
from PIL import Image, ImageDraw

UA = {"User-Agent": "fourthday-profile-previews"}

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()

# name -> list of candidate URLs (first that works wins) or ("nasa", query, n)
DIRECT = {
    "pilares-webb": ["https://cdn.esawebb.org/archives/images/large/weic2216a.jpg",
                     "https://cdn.esawebb.org/archives/images/screen/weic2216a.jpg"],
    "pilares-hubble": ["https://cdn.esahubble.org/archives/images/large/heic1501a.jpg",
                       "https://cdn.spacetelescope.org/archives/images/large/heic1501a.jpg"],
    "orion-hubble": ["https://cdn.esahubble.org/archives/images/large/heic0601a.jpg",
                     "https://cdn.spacetelescope.org/archives/images/large/heic0601a.jpg"],
    "pleiades-eso": ["https://cdn.eso.org/images/large/eso0928a.jpg"],
}
NASA = {
    "sol-sdo": "SDO sun 304",
    "sol-sdo-flare": "solar flare SDO",
    "earthrise": "Earthrise Apollo 8",
    "lua-cheia": "full moon",
    "pleiades": "Pleiades",
    "eclipse": "total solar eclipse corona 2017",
    "orion": "Orion Nebula",
}

def nasa_search(q, n=4):
    data = json.loads(get("https://images-api.nasa.gov/search?media_type=image&q=" + urllib.parse.quote(q)))
    out = []
    for it in data["collection"]["items"][:n]:
        nid = it["data"][0]["nasa_id"]
        out.append((nid, it["data"][0].get("title", ""), "https://images-assets.nasa.gov/image/%s/%s~medium.jpg" % (urllib.parse.quote(nid), urllib.parse.quote(nid))))
    return out

def circle(img, size=400):
    w, h = img.size; s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    bg = Image.new("RGB", (size, size), "white"); bg.paste(img, (0, 0), mask)
    return bg

def save(name, raw, src, log):
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((1600, 1600))
    img.save("perfil/out/%s-original.jpg" % name, quality=88)
    circle(img).save("perfil/out/%s-circulo.png" % name)
    circle(img, 110).save("perfil/out/%s-pequeno.png" % name)
    log.append({"name": name, "src": src, "size": img.size})

import os; os.makedirs("perfil/out", exist_ok=True)
log = []
for name, urls in DIRECT.items():
    for u in urls:
        try:
            save(name, get(u), u, log); break
        except Exception as e:
            print("fail", u, e, file=sys.stderr)
for name, q in NASA.items():
    try:
        for i, (nid, title, u) in enumerate(nasa_search(q)):
            try:
                save("%s-%d" % (name, i), get(u), "%s | %s | %s" % (nid, title, u), log)
            except Exception as e:
                print("fail", u, e, file=sys.stderr)
    except Exception as e:
        print("search fail", q, e, file=sys.stderr)
json.dump(log, open("perfil/out/log.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(log, indent=1, ensure_ascii=False))
