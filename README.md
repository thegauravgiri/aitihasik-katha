# 🎬 Aitihasik Katha

AI-powered historical storytelling pipeline that turns historical context into short-form vertical videos.

It combines retrieval-augmented generation (RAG), image generation, text-to-speech, subtitle timing, video composition, and optional Instagram publishing.

## 🎥 Demo

https://github.com/user-attachments/assets/bed1955f-2072-4d4e-b453-8095a51eb50d

## 📱 Live

Instagram: https://instagram.com/aitihasik_katha

## 🚀 What This Project Does

Given a topic (or random historical context), the pipeline:

1. Retrieves relevant historical passages from a vector-backed knowledge base.
2. Generates a documentary-style script.
3. Splits the script into scenes.
4. Generates one cinematic image per scene.
5. Synthesizes voice-over audio.
6. Transcribes audio to timed words for subtitles.
7. Builds animated clips from images and merges everything into one reel.
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
│       │   ├── image_service.py
│       │   ├── instagram_service.py
│       │   ├── instagram_oauth.py
│       │   ├── scene_timing.py
│       │   ├── story_service.py
│       │   ├── subtitle_service.py
│       │   └── video_service.py
│       ├── storage/
│       │   └── vector_store.py
│       └── utils/
│           ├── gcs.py
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
Vector retrieval (Vertex Matching Engine + local metadata JSON)
        |
        v
Story generation (Gemini via LangChain)
        |
        +------------------------------+
        |                              |
        v                              v
Image generation (Vertex)      Audio generation (Cloud TTS)
        |                              |
        +---------------+--------------+
                        v
          Speech transcription (Cloud Speech-to-Text)
                        |
                        v
         Subtitle timing + per-scene duration mapping
                        |
                        v
             Video composition (MoviePy + FFmpeg)
                        |
                        v
         Upload to GCS -> optional Instagram publish
```

## ☁️ Google Cloud Integration

This project relies on Google Cloud for multiple stages:

- Vertex AI Matching Engine for semantic retrieval.
- Vertex image model for scene images.
- Cloud Text-to-Speech for narration.
- Cloud Speech-to-Text v2 for word-level subtitles.
- Cloud Storage for storing the final video artifact.

### 🧩 Required APIs

Enable these APIs in your Google Cloud project:

- Vertex AI API
- Cloud Speech-to-Text API
- Cloud Text-to-Speech API
- Cloud Storage API

### 🔐 Credentials

You need service-account credentials and must set `GOOGLE_APPLICATION_CREDENTIALS` in `.env`.

Example:

```env
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
PROJECT_ID=your-gcp-project-id
LOCATION=us-central1
BUCKET=your-gcs-bucket
```

Recommended minimum IAM scopes/roles for the service account:

- Vertex AI access (query index and use vision model)
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
IMAGE_CHAT_MODEL=gemini-2.0-flash
IMAGE_MODEL=imagegeneration@006
AUDIO_MODEL=chirp3-hd
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
PROJECT_ID=your-gcp-project-id
LOCATION=us-central1
BUCKET=your-gcs-bucket
BUCKET_URI=gs://your-gcs-bucket

# Matching Engine configuration
INDEX_ID=projects/.../locations/.../indexes/...
INDEX_ENDPOINT_ID=projects/.../locations/.../indexEndpoints/...
DEPLOYED_INDEX_ID=your-deployed-index-id

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

Output is created under `runs/<uuid>/`:

- `runs/<uuid>/audios/story.mp3`
- `runs/<uuid>/images/*.png`
- `runs/<uuid>/videos/*.mp4`
- `runs/<uuid>/output/final_video.mp4`

### 📚 Ingest PDFs

```bash
python -m aitihasik_katha ingest --base-dir data/pdfs
```

Single file:

```bash
python -m aitihasik_katha ingest --path data/pdfs/en/sample.pdf --language en
```

## ⚠️ Important Note About Ingestion

`ingest` currently parses and chunks PDFs, but `VectorStore.add_document()` is intentionally not implemented for Matching Engine writes in the current codebase.

That means:

- Retrieval during `run` expects an already prepared index and metadata dataset.
- The project can run end-to-end once Matching Engine + embedding metadata are already provisioned.
- If you need ingestion-to-index automation, you will need to implement the index upsert step for your environment.

## 🔍 Where Google Cloud Is Used In Runtime

During `run`, the pipeline does the following cloud operations:

1. Reads neighbors from Vertex Matching Engine for story context.
2. Calls Gemini and Vertex image generation models.
3. Calls Cloud TTS to generate `story.mp3`.
4. Uploads audio to GCS temporarily for Speech-to-Text v2 batch recognition.
5. Deletes temporary transcription audio object from GCS.
6. Uploads final video to GCS and returns a public URL.
7. Optionally sends that URL to Instagram Graph API for publishing.

## 🧯 Troubleshooting

- `Could not find ffmpeg`: install FFmpeg and ensure it is on your shell `PATH`.
- `PDFInfoNotInstalledError` from `pdf2image`: install Poppler.
- `DefaultCredentialsError`: verify `GOOGLE_APPLICATION_CREDENTIALS` path and permissions.
- Empty or poor retrieval: verify Matching Engine IDs and deployed index configuration.
- Instagram publish failures: verify page token, user id, and app permissions.

## 🧠 Development Notes

- Entry point: `python -m aitihasik_katha`
- CLI commands: `run`, `ingest`
- Settings source: environment variables loaded via `.env`
- Main orchestrator: `src/aitihasik_katha/pipeline.py`

## 📌 Disclaimer

This project is intended for educational and research use. Always validate generated historical content before publication.
