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

🙏 <1–2 frases ligando o que a imagem mostra a uma verdade bíblica.>
"<versículo, ARA>" <Ref>

🙏 <same application in English.>
"<verse in English>" <Ref>

#astrofotografia #astrophotography #<object> #<telescope> #space #universo ...
```

## The 3 pillars (Adriano, 2026-10-10)

Every post has three parts:
1. **God's power revealed in creation**: the image and the short description.
2. **A curiosity** about the object (✨ line).
3. **A biblical principle applied to the post** (🙏 block).
   The pillars are NOT written as labels in the caption (no "Poder de Deus / Curiosidade / Princípio" headings);
   only the ✨ Curiosidade label stays. The 🙏 block is plain text, no "Princípio:" label. Not a loose verse: 1–2 sentences that
   take what the image shows and apply it to a biblical truth, then the verse that supports it.
   Any book, Genesis to Revelation (ARA in Portuguese). Vary the verses between posts.
   Adriano's example: stars being born cannot hide inside the dust (Webb sees them in infrared),
   just as we cannot hide from God's presence; "Para onde me ausentarei do teu Espírito?
   Para onde fugirei da tua face?" Sl 139:7.

## Voice of the opening line and the 🙏 application (Adriano, 2026-10-19)

Replaces the 2026-10-10 "plain" tone. Both the opening reflection and the 🙏 block are written in
Adriano's theological voice:
- Short, weighty sentences. Inversion of the obvious ("não é X, é Y").
- One question that provokes the reader, aimed at them and tied to the verse (e.g. "O que em você ainda precisa cair na terra para dar fruto?"). Adriano rejected a speculative "E se cair for justamente o caminho?".
- Christ at the center; Scripture as the base (the verse supports the point, not decoration).
- Images of light, fire and the secret place.
- A small, elegant dose of irony about human pride. No exaggeration, no sermon tone,
  never mocking anyone, no jokes or slapstick, no pastor/priest clichés ("irmãos", "amados").

Opening reflection: one short line (PT) right after the 🔭 title and a blank line, before the description;
the same in English right after the 🇺🇸 title line.
Example (Crab Nebula):
"Uma estrela morreu aqui. E ainda não parou de brilhar."
"🙏 Não é o fim da estrela, é semente. O que sobrou dela acende a nuvem inteira, e Cristo chamou isso
de grão de trigo. O que em você ainda precisa cair na terra para dar fruto?" + Jo 12:24.

## Adriano's own photos (meta.json has "own_photo": true)

Photos he took with his Seestar S50 telescope (pool in `mine/`, one goes into the queue each day).
Same caption pattern. The title is in `title_pt`. Credit line:
"📷 Foto: @fourthday_ · Telescópio Seestar S50" / "📷 Photo: @fourthday_ · Seestar S50 telescope".
Add #seestar #seestars50 #astrofotografiaamadora #amateurastronomy to the hashtags.

## Rules

- No ages or "X years ago" for any phenomenon (no "this crater is 200 million years old", "the collision began 700 million years ago", no historical dates). Distances in light-years are fine. Exception: a recent event with a concrete date (e.g. a meteorite that fell on day X), used sparingly so the account never feels like a news feed.

- If a queued image is not a good post (charts, panels with text, B&W), delete its folder and add its key to `rejected` in `history.json` with a short reason, so it never comes back.

- Never a black-and-white image on its own (the script already skips them). Black and white is
  allowed only as the 2nd slide of a carousel: the colour image first, then the same photo in
  black and white to reveal the science behind it (`python fourthday.py carousel queue/<folder>`
  creates `image-2.jpg`). Carousels are optional; use one only when the comparison tells something.
  When there is a 2nd slide, the caption says what it shows ("Arraste para o lado…" / "Swipe…").

- Portuguese (BR) first, then English. Science content, then the applied principle (always present).
- Facts come from `meta.json` (description, distance). If the distance is not given there, use a well-established value and say "cerca de / about"; if unsure, leave the distance line out.
- Credit exactly as the source gives it. Always credit ESA, ESO and NOIRLab in full (e.g. "ESA/Webb, NASA & CSA, …"). NASA images: "NASA" plus the named centre or photographer.
- Read the whole description for extra credit lines (e.g. "Processing: …", "CC-BY …") and include them.
- When the image is the Sun or the Moon, Gn 1:16 ("os dois grandes luzeiros") fits especially well as the principle verse.
- Up to 2,200 characters and 15–20 hashtags (Instagram limit is 30).
- No links (they are not clickable in Instagram captions).
- Vary the opening sentence, the 🙏 verse and the hashtag set from post to post (keep a few fixed tags like #fourthday #quartodia, rotate the rest) so captions never read as a template.
- Before writing a caption, check the subject against recent posts (history.json titles and the queue). If the same object or the same kind of scene (e.g. aurora from orbit) was posted in the last ~2 weeks, reject it (history.json "rejected") and run Prepare images again with a `source` input so no extra own photo is added.
