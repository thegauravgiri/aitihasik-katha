# 🎬 Aitihasik Katha

AI-powered historical storytelling pipeline that turns historical context into short-form vertical videos.

It combines retrieval-augmented generation (RAG), AI video generation, text-to-speech, subtitle timing, video composition, and optional Instagram publishing.

## 🎥 Demo

https://github.com/user-attachments/assets/bed1955f-2072-4d4e-b453-8095a51eb50d

## 📱 Live

Instagram: https://instagram.com/aitihasik_katha

## 🚀 What This Project Does

Given a topic (or random historical context), the pipeline:

1. Retrieves relevant historical passages from a vector-backed knowledge base, and researches the subject on the web (Google Search grounding) for more facts.
2. Writes a 45–60 second Nepali script built for short-form retention: a hook in the first sentence, open loops, rising stakes, a payoff, and a closing question plus a like/follow nudge.
3. Splits the script into scenes (one short sentence per shot, so there's a cut every few seconds).
4. Writes a character sheet (how each recurring character looks) and plans a shot per scene.
5. Gets one reference image per character: a freely licensed Wikipedia portrait for real historical figures, otherwise a generated one.
6. Synthesizes voice-over audio and transcribes it to timed words for subtitles.
7. Draws each scene's opening frame from the shared character references, turns it into a clip (animated by the video model, or a slow camera move over the still, depending on the clip mode), fits each clip to its narration time, and merges everything into one reel.
8. Uploads the final video to Google Cloud Storage and optionally publishes it to Instagram.

## 🗂️ Current Project Structure

```text
aitihasik-katha/
├── pyproject.toml
├── requirements.txt
├── pyrightconfig.json
├── README.md
├── data/
│   ├── embeddings/
│   │   ├── chroma.sqlite3
│   │   ├── nepali-history.json
│   │   └── 88c6b1ae-a89a-428f-9ded-34a969a755ce/
│   └── fonts/
├── examples/
├── notebooks/
│   ├── data-ingestion.ipynb
│   └── instagram-upload.ipynb
├── runs/
│   └── <run-id>/
│       ├── audios/
│       ├── images/
│       ├── output/
│       └── videos/
├── src/
│   └── aitihasik_katha/
│       ├── __main__.py
│       ├── cli.py
│       ├── pipeline.py
│       ├── core/
│       │   └── settings.py
│       ├── ingest/
│       │   └── pdf_ingestor.py
│       ├── services/
│       │   ├── audio_service.py
│       │   ├── caption_service.py
│       │   ├── character_service.py
│       │   ├── instagram_service.py
│       │   ├── instagram_oauth.py
│       │   ├── image_service.py
│       │   ├── omni_video_service.py
│       │   ├── reference_service.py
│       │   ├── research_service.py
│       │   ├── scene_timing.py
│       │   ├── story_service.py
│       │   ├── subtitle_service.py
│       │   ├── veo_video_service.py
│       │   ├── video_generation_service.py
│       │   └── video_service.py
│       ├── storage/
│       │   └── vector_store.py
│       └── utils/
│           ├── gcs.py
│           ├── genai_client.py
│           ├── ocr.py
│           ├── retry.py
│           └── translation.py
└── tests/
```

## ⚙️ How It Works (End-to-End)

```text
Topic or random source
        |
        v
Vector retrieval (local FAISS index over precomputed embeddings)
        |
        v
Story generation (Gemini via LangChain)
        |
        +-----------------------------------+
        |                                   |
        v                                   v
Character sheet + shot plan (Gemini)   Audio generation (Cloud TTS)
        |                                   |
        v                                   v
Reference image per character          Speech transcription (Cloud Speech-to-Text)
(Wikipedia portrait or Nano Banana 2)       |
        |                                   |
        v                                   |
Opening frame per scene (Nano Banana 2,     |
drawn from the characters' references)      |
        |                                   |
        +-----------------+-----------------+
                          v
        Per-scene durations from subtitle timing
                          |
                          v
     One clip per scene (Veo 3.1 Lite image-to-video)
                          |
                          v
             Video composition (MoviePy + FFmpeg)
                        |
                        v
         Upload to GCS -> optional Instagram publish
```

## ☁️ Google Cloud Integration

Semantic retrieval runs locally via FAISS, not Google Cloud. This project still relies on Google Cloud for the rest of the pipeline:

- Cloud Text-to-Speech for narration.
- Cloud Speech-to-Text v2 for word-level subtitles.
- Cloud Storage for storing the final video artifact.

### 🧩 Required APIs

Enable these APIs in your Google Cloud project:

- Cloud Speech-to-Text API
- Cloud Text-to-Speech API
- Cloud Storage API

### 🔐 Credentials

You need service-account credentials and must set `GOOGLE_APPLICATION_CREDENTIALS` in `.env`.

Example:

```env
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
PROJECT_ID=your-gcp-project-id
BUCKET=your-gcs-bucket
```

Recommended minimum IAM scopes/roles for the service account:

- Speech-to-Text and Text-to-Speech usage
- Cloud Storage object read/write

## 🛠️ Installation

### 🐍 1. Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 🧱 2. System dependencies

`pdf2image` and video rendering require native tools.

macOS:

```bash
brew install tesseract tesseract-lang ffmpeg poppler
```

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-nep ffmpeg poppler-utils
```

## 🧪 Environment Configuration

Create a `.env` file in the repository root.

```env
# LLM + generation
GEMINI_API_KEY=your_gemini_api_key
CHAT_MODEL=gemini-2.0-flash
AUDIO_MODEL=chirp3-hd
VIDEO_MODEL=veo-3.1-lite-generate-preview   # animates each scene's opening frame
IMAGE_MODEL=gemini-3.1-flash-image          # character references + scene opening frames
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
PROJECT_ID=your-gcp-project-id
BUCKET=your-gcs-bucket
BUCKET_URI=gs://your-gcs-bucket

# Optional Instagram publish
INSTAGRAM_CLIENT_ID=...
INSTAGRAM_CLIENT_SECRET=...
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_PAGE_ACCESS_TOKEN=...
INSTAGRAM_USER_ID=...

# Optional run paths
RUNS_PATH=runs/
IMAGE_PATH=images/
VIDEO_PATH=videos/
AUDIO_PATH=audios/
OUTPUT_PATH=output/
```

## 💻 CLI Usage

All commands are exposed via:

```bash
python -m aitihasik_katha <command>
```

### ▶️ Run full pipeline

```bash
python -m aitihasik_katha run
```

With topic seed:

```bash
python -m aitihasik_katha run --topic "Unification of Nepal"
```

Choose how scenes are rendered and which video model to use, per run (defaults come from
`CLIP_MODE` and `VIDEO_MODEL` in `.env`):

```bash
python -m aitihasik_katha run --mode image                 # stills with camera moves only: ~$1.50–2 per video, no video quota used
python -m aitihasik_katha run --mode mixed                 # planner picks video vs still per scene; the hook is always video
python -m aitihasik_katha run --mode video                 # every scene animated
python -m aitihasik_katha run --video-model gemini-omni-1.1-flash   # any veo-* or gemini-omni-* model
```

With `--topic`, the story is researched on the web first and supported by matching archive
passages. Without one, a random archive passage picks the subject and web research expands on it
(`USE_WEB_RESEARCH=false` to use the archive only). The research brief and its sources are saved
as `output/research.md` and `output/sources.json`.

Output is created under `runs/<uuid>/`:

- `runs/<uuid>/audios/story.mp3`
- `runs/<uuid>/images/ref_<character>.png` (character references)
- `runs/<uuid>/videos/video_clip_*.mp4` (one per scene)
- `runs/<uuid>/output/characters.json`, `scene_plan.json`
- `runs/<uuid>/output/final_video.mp4`

### 🔁 Recovering failed or incomplete runs

Every run's progress (story/audio/media/video/publish) is tracked in a local SQLite
registry at `runs/pipeline.db`. If generation fails partway through, or the video was
generated but the Instagram upload failed, you can recover without starting over:

```bash
# See every tracked run and its status
python -m aitihasik_katha list

# Resume a specific run: any stage whose output already exists on disk is
# reused rather than regenerated (and it won't re-publish if it was already
# successfully posted to Instagram).
python -m aitihasik_katha run --run-id <uuid>

# Retry publishing a single run whose video is ready but wasn't uploaded
python -m aitihasik_katha instagram upload --run-id <uuid>

# Retry publishing every tracked run that's ready but not yet uploaded
python -m aitihasik_katha instagram upload --all
```

### 📚 Ingest PDFs

```bash
python -m aitihasik_katha ingest --base-dir data/pdfs
```

Single file:

```bash
python -m aitihasik_katha ingest --path data/pdfs/en/sample.pdf --language en
```

## ⚠️ Important Note About Ingestion

`ingest` currently parses and chunks PDFs, but `VectorStore.add_document()` is intentionally not implemented for the FAISS index in the current codebase.

That means:

- Retrieval during `run` expects `data/embeddings/nepali-history.json` (chunk text + metadata) and `data/embeddings/history.json` (matching embedding vectors) to already exist, aligned row-for-row by id.
- The project can run end-to-end once those two embedding files are already provisioned.
- If you need ingestion-to-index automation, you will need to implement the embed + append step for your environment, then rebuild the FAISS index (it's built in memory from those files on first use).

## 🔍 Where Google Cloud Is Used In Runtime

During `run`, the pipeline does the following cloud operations (story context retrieval itself is local, via FAISS):

1. Calls Gemini for the story, character sheet, shot plan and caption, Nano Banana 2 for reference images and scene frames, and Veo 3.1 Lite for video clips.
2. Calls Cloud TTS to generate `story.mp3`.
3. Uploads audio to GCS temporarily for Speech-to-Text v2 batch recognition.
4. Deletes temporary transcription audio object from GCS.
5. Uploads final video to GCS and returns a public URL.
6. Optionally sends that URL to Instagram Graph API for publishing.

## 🧯 Troubleshooting

- `Could not find ffmpeg`: install FFmpeg and ensure it is on your shell `PATH`.
- `PDFInfoNotInstalledError` from `pdf2image`: install Poppler.
- `DefaultCredentialsError`: verify `GOOGLE_APPLICATION_CREDENTIALS` path and permissions.
- Empty or poor retrieval: verify `data/embeddings/nepali-history.json` and `data/embeddings/history.json` exist and their `ids`/`id` columns line up row-for-row.
- Instagram publish failures: verify page token, user id, and app permissions.

## 🧠 Development Notes

- Entry point: `python -m aitihasik_katha`
- CLI commands: `run`, `list`, `instagram upload`, `ingest`
- Settings source: environment variables loaded via `.env`
- Main orchestrator: `src/aitihasik_katha/pipeline.py`

### ⚡ Concurrency

The visuals stage (character sheet, reference images, shot plan, scene opening
frames) and audio generation/transcription run concurrently, since they don't
depend on each other.
Clip generation fans out across scenes once both are done, because each clip's
length comes from the narration timing. This is bounded by `MAX_PARALLEL_SCENES`
(default `4`) — raise it if your quota allows more, lower it if you see
rate-limit retries in the logs.

### 🎭 Character consistency

Each clip is generated independently, so consistency comes from shared inputs
rather than chaining clips together:

- `characters.json` fixes each recurring character's appearance once per run.
- One reference image per character (`images/ref_<id>.png`). Each scene's opening
  frame (`images/scene_<n>.png`) is drawn from the references of the characters in
  it, then Veo 3.1 Lite animates that frame. (Veo Lite doesn't accept reference
  images directly, so the frame carries the likeness into the clip.)
- For real historical figures, the reference is the lead image of their English
  Wikipedia article, used only if it's public domain, CC0 or CC BY (CC BY-SA is
  skipped, since its share-alike term would arguably cover the video) and Gemini
  confirms it clearly shows that person. The character's description is then
  rewritten from that image so text and picture agree, and a credit line is
  added to the Instagram caption. Everyone else gets a generated reference
  (`IMAGE_MODEL`). Set `USE_HISTORICAL_PORTRAITS=false` to always generate.
- Each choice is saved next to the image (`images/ref_<id>.json`) so resumed runs
  reuse it.
- The character's description is repeated word for word in every frame and clip prompt.

If a scene's clip still fails after retries, the run is marked `failed` and nothing
is published; fix the cause and resume with `run --run-id <id>`.

## 📌 Disclaimer

This project is intended for educational and research use. Always validate generated historical content before publication.
