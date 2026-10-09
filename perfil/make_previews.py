"""Downloads candidate profile pictures and makes round previews (Instagram style)."""
import io, json, sys, urllib.parse, urllib.request
from PIL import Image, ImageDraw

UA = {"User-Agent": "fourthday-profile-previews"}

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()

# name -> list of candidate URLs (first that works wins) or ("nasa", query, n)
DIRECT = {}
NASA = {
    "apollo8": "as08-14-2383",
    "apollo8b": "Apollo 8 Earthrise",
    "m45": "Pleiades M45 star cluster",
    "sol-disco": "SDO full disk sun",
    "carina": "Webb Cosmic Cliffs Carina",
    "lua-lro": "LRO Moon near side",
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
    img.save("perfil/out2/%s-original.jpg" % name, quality=88)
    circle(img).save("perfil/out2/%s-circulo.png" % name)
    circle(img, 110).save("perfil/out2/%s-pequeno.png" % name)
    log.append({"name": name, "src": src, "size": img.size})

import os; os.makedirs("perfil/out2", exist_ok=True)
log = []
for name, urls in DIRECT.items():
    for u in urls:
        try:
            save(name, get(u), u, log); break
        except Exception as e:
            print("fail", u, e, file=sys.stderr)
for name, q in NASA.items():
    try:
        for i, (nid, title, u) in enumerate(nasa_search(q, 6)):
            try:
                save("%s-%d" % (name, i), get(u), "%s | %s | %s" % (nid, title, u), log)
            except Exception as e:
                print("fail", u, e, file=sys.stderr)
    except Exception as e:
        print("search fail", q, e, file=sys.stderr)
json.dump(log, open("perfil/out2/log.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(log, indent=1, ensure_ascii=False))
