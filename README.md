# quarto dia

"Astrofotografia diária automatizada para o @fourthday_".

## How it works

1. **Prepare images** (`.github/workflows/prepare.yml`) picks new images from NASA APOD
   (public-domain ones only), the NASA Image and Video Library, ESA/Webb, ESA/Hubble, ESO and
   NOIRLab, crops them to 4:5 (1080×1350 JPEG) and stores them in `queue/`.
2. A caption (`caption.txt`, Portuguese then English) is written for each queued image,
   following [CAPTION_GUIDE.md](CAPTION_GUIDE.md).
3. **Post to Instagram** (`.github/workflows/post.yml`) publishes the oldest captioned image
   through the Instagram API, moves it to `posted/` and records it in `history.json`, so no
   image is ever posted twice. Run by hand it is a dry run unless you untick the box.
4. **Refresh Instagram token** (`.github/workflows/token.yml`) renews the 60-day token on the
   1st and 15th of each month.

## Secrets

Stored in GitHub under **Settings → Secrets and variables → Actions**, never in this repo:

| Name | What |
| --- | --- |
| `IG_ACCESS_TOKEN` | Instagram long-lived token for @fourthday_ |
| `NASA_API_KEY` | NASA API key (optional) |

## Running locally

```
pip install -r requirements.txt
python fourthday.py prepare --count 1
python fourthday.py publish --dry-run
```
