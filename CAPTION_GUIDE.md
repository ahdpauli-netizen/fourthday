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

## Tone of the 🙏 application (Adriano, 2026-10-10)

Plain and conversational, like a friend pointing something out. Short everyday words.
Not preachy, not academic, not formal, not "spiritual-sounding" (no priest/pastor/archbishop
voice, no "irmãos", "amados", "glória", "bênção", no sermon clichés like "as sombras da vida").
Start from something concrete in the image, then one simple line about God. Example:
"Urano leva suas luas sem perder nenhuma, todas presas por uma força que ninguém vê.
Quem segura tudo isso no lugar também segura a sua vida."

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
