<p align="center">
  <img src="assets/logo/logo-horizontal-reversed.png" alt="Aitihasik Katha logo" width="520">
</p>

<p align="center">
  <b>Short history videos about Nepal, made with AI.</b>
</p>

<p align="center">
  <a href="https://instagram.com/aitihasik_katha">Instagram</a> ·
  <a href="#demo">Demo</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#usage">Usage</a>
</p>

# Aitihasik Katha: AI History Video Generator for Nepal

**Aitihasik Katha** (ऐतिहासिक कथा, "historical story") is an open-source Python app that turns the history of Nepal into short vertical videos for **Instagram Reels, YouTube Shorts and TikTok**.

Give it a topic, or let it pick one. It researches the history, writes a gripping script in Nepali, creates the scenes and characters, adds a voice-over with subtitles, and can post the finished reel to Instagram.

## Demo

https://github.com/user-attachments/assets/bed1955f-2072-4d4e-b453-8095a51eb50d

See more on Instagram: [@aitihasik_katha](https://instagram.com/aitihasik_katha)

## Features

- **Research from two sources**: a local archive of Nepali history books and live web search.
- **Scripts made to be watched**: a planner picks the shortest length that tells the topic well (30 to 90 seconds), then the script gets a specific hook, fresh hooks along the way and an ending that loops back to the start.
- **Checked before it's made**: every script is reviewed against your topic and the research, and rewritten if it drifts, is too long or has weak hooks or unsupported claims.
- **Covers that get tapped**: a cover image with a bold hook title, also shown over the first seconds of the video.
- **Consistent characters**: the same person looks the same in every scene. Real historical figures use their actual portraits when a free one exists.
- **Three video styles**: images only, mixed, or full video.
- **Choose your video model**: Google Veo or Gemini Omni, switched from settings.
- **Nepali voice-over** with word-by-word subtitles.
- **Review, then post**: a run stops with the video, cover and caption ready, and you post it when you're happy. Failed runs are easy to retry.

## How it works

1. **Research** the topic from the archive and the web.
2. **Write** a short Nepali script.
3. **Design** the characters and plan each shot.
4. **Create** an image for every scene, then animate it (or add a slow camera move).
5. **Record** the voice-over and time the subtitles.
6. **Edit** everything into one vertical video.
7. **Review** the video, cover and caption, then **publish** to Instagram.

Built with Google Gemini, Veo, Nano Banana 2, Google Cloud Text-to-Speech and Speech-to-Text, FAISS and MoviePy.

## Quick start

**You need:** Python 3.10+, FFmpeg, Poppler, Tesseract, a Gemini API key, and a Google Cloud project with Text-to-Speech, Speech-to-Text and Cloud Storage enabled.

Install the system tools. On macOS:

```bash
brew install ffmpeg poppler tesseract tesseract-lang
```

On Ubuntu:

```bash
sudo apt install ffmpeg poppler-utils tesseract-ocr tesseract-ocr-nep
```

Then set up the project:

```bash
git clone https://github.com/thegauravgiri/aitihasik-katha.git
cd aitihasik-katha
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp .env.example .env
```

Then fill in `.env` and run:

```bash
python -m aitihasik_katha run --topic "Battle of Kirtipur"
```

The run stops when the video is ready. Check `runs/<run-id>/output/` (`final_video.mp4`, `cover.jpg`, `caption.txt`), then post it:

```bash
python -m aitihasik_katha instagram upload --run-id <run-id>
```

To post automatically instead, add `--publish` to the run command or set `AUTO_PUBLISH=true`.

## Configuration

All settings live in `.env` (see `.env.example`). The main ones:

| Setting | What it does |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key |
| `CHAT_MODEL` | Model for research, scripts and captions |
| `VIDEO_MODEL` | Video model, e.g. `veo-3.1-lite-generate-preview` or `gemini-omni-1.1-flash` |
| `IMAGE_MODEL` | Image model for characters and scenes |
| `CLIP_MODE` | `image`, `mixed` or `video` |
| `USE_WEB_RESEARCH` | Search the web for more facts (`true`/`false`) |
| `USE_STORY_REVIEW` | Check each script against the topic and research, and rewrite it if needed (`true`/`false`) |
| `AUTO_PUBLISH` | Post to Instagram as soon as the video is made (`true`/`false`, default `false`) |
| `USE_HISTORICAL_PORTRAITS` | Use real portraits from Wikipedia (`true`/`false`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to your Google Cloud service account file |
| `PROJECT_ID`, `BUCKET` | Your Google Cloud project and storage bucket |
| `INSTAGRAM_USER_ID`, `INSTAGRAM_PAGE_ACCESS_TOKEN` | Needed to post to Instagram |

## Usage

Make a video on a random topic, on a topic you choose, in a chosen style, or with a different video model:

```bash
python -m aitihasik_katha run
python -m aitihasik_katha run --topic "Unification of Nepal"
python -m aitihasik_katha run --mode image
python -m aitihasik_katha run --video-model gemini-omni-1.1-flash
```

### Video styles

| Mode | Looks like | Cost per video* |
|---|---|---|
| `image` | Still images with slow camera moves | about $1.50 |
| `mixed` | Video for action scenes, images for the rest | about $3 |
| `video` | Every scene animated | about $5 |

\*Rough estimate for a 55-second video with Veo 3.1 Lite. Omni and Veo Fast cost more.

### Check, resume and publish runs

```bash
python -m aitihasik_katha list
python -m aitihasik_katha run --run-id <run-id>
python -m aitihasik_katha instagram upload --run-id <run-id>
python -m aitihasik_katha instagram upload --all
```

A resumed run reuses everything it already made, and a published run is never posted twice.

### Add history books

```bash
python -m aitihasik_katha ingest --base-dir data/pdfs
python -m aitihasik_katha ingest --path data/pdfs/en/book.pdf --language en
```

The story search reads from `data/embeddings/nepali-history.json` and `data/embeddings/history.json`, so these files must exist before you run the app.

## Project structure

```text
src/aitihasik_katha/
├── cli.py          # command line
├── pipeline.py     # runs every step in order
├── services/       # research, story, characters, images, video, audio, Instagram
├── storage/        # history search index and run history
└── utils/          # shared helpers
assets/logo/        # logo files
tests/              # automated tests
```

Run the tests with `python -m pytest`.

## Disclaimer

The videos are made with AI and may contain mistakes. Please check the facts before you publish. This project is for education.
