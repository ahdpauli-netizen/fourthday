"""Search the NASA Image Library and save thumbnails + metadata to search/ for review."""
import json, sys, pathlib, requests

q = sys.argv[1]
media = sys.argv[2] if len(sys.argv) > 2 else "image"
out = pathlib.Path("search"); out.mkdir(exist_ok=True)
r = requests.get("https://images-api.nasa.gov/search", params={"q": q, "media_type": media}, timeout=60)
items = r.json()["collection"]["items"]
items.sort(key=lambda it: it["data"][0].get("date_created", ""), reverse=True)
res = []
for i, it in enumerate(items[:24]):
    d = it["data"][0]
    thumb = next((l["href"] for l in it.get("links", []) if l.get("rel") == "preview"), None)
    if thumb:
        try:
            (out / ("%02d.jpg" % i)).write_bytes(requests.get(thumb, timeout=60).content)
        except Exception as e:
            print("thumb failed", e)
    assets = []
    if media == "video":
        try:
            assets = [x["href"] for x in requests.get("https://images-api.nasa.gov/asset/%s" % d["nasa_id"], timeout=60).json()["collection"]["items"]]
        except Exception as e:
            print("asset failed", e)
    res.append({"assets": assets, "i": i, "nasa_id": d["nasa_id"], "title": d.get("title"), "date": d.get("date_created"),
                "center": d.get("center"), "photographer": d.get("photographer"),
                "description": (d.get("description") or "")[:600]})
(out / "results.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
print(len(res), "results")
