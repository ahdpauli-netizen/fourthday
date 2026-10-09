# Caption guide (@fourthday_)

Every queued image (`queue/<folder>/`) needs a `caption.txt` before it can be posted.
`meta.json` beside it has the source title, description, credit and link.

## Shape

```
🔭 <Nome do objeto em português>

<2–3 frases: o que é, onde fica, distância.>
✨ Curiosidade: <um fato marcante, em uma frase.>

📏 Distância: <valor> anos-luz
📷 Crédito: <crédito completo da fonte>

🇺🇸 <Object name in English>
<Same 2–3 sentences in English.>
✨ Fun fact: <same fact.>
📏 Distance: <value> light-years
📷 Credit: <full source credit>

"E fez também as estrelas." Gn 1:16   (optional, at most one post in three)

#astrofotografia #astrophotography #<object> #<telescope> #space #universo ...
```

## Rules

- No ages or "X years ago" for any phenomenon (no "this crater is 200 million years old", "the collision began 700 million years ago", no historical dates). Distances in light-years are fine. Exception: a recent event with a concrete date (e.g. a meteorite that fell on day X), used sparingly so the account never feels like a news feed.

- If a queued image is not a good post (charts, panels with text, B&W), delete its folder and add its key to `rejected` in `history.json` with a short reason, so it never comes back.

- Never a black-and-white image on its own (the script already skips them). Black and white is
  allowed only as the 2nd slide of a carousel: the colour image first, then the same photo in
  black and white to reveal the science behind it (`python fourthday.py carousel queue/<folder>`
  creates `image-2.jpg`). Carousels are optional; use one only when the comparison tells something.
  When there is a 2nd slide, the caption says what it shows ("Arraste para o lado…" / "Swipe…").

- Portuguese (BR) first, then English. Science content; the Genesis line is optional and light.
- Facts come from `meta.json` (description, distance). If the distance is not given there, use a well-established value and say "cerca de / about"; if unsure, leave the distance line out.
- Credit exactly as the source gives it. Always credit ESA, ESO and NOIRLab in full (e.g. "ESA/Webb, NASA & CSA, …"). NASA images: "NASA" plus the named centre or photographer.
- Read the whole description for extra credit lines (e.g. "Processing: …", "CC-BY …") and include them.
- When the image is the Sun or the Moon, the Gn 1:16 "luzeiros" line fits especially well.
- Up to 2,200 characters and 15–20 hashtags (Instagram limit is 30).
- No links (they are not clickable in Instagram captions).
