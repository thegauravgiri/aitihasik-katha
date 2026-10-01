import argparse

# faiss must be imported before anything that pulls in gRPC/protobuf (langchain_google_genai and
# the google-cloud clients, transitively via .pipeline below). Importing them in the other order
# reliably segfaults on this machine (native library init-order conflict). Keep this import first.
import faiss  # noqa: F401

from .core.logging import configure_logging
from .core.settings import settings
from .ingest.pdf_ingestor import ingest_directory, ingest_pdf
from .pipeline import publish_all_pending, publish_run, run_pipeline_v1
from .storage import run_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aitihasik Katha workflow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline_cmd = subparsers.add_parser("run", help="Run end-to-end generation pipeline")
    pipeline_cmd.add_argument("--topic", default=None, help="Optional seed topic for story generation")
    pipeline_cmd.add_argument(
        "--run-id",
        default=None,
        help="Resume an existing run id, reusing any already-generated stage output",
    )
    pipeline_cmd.add_argument(
        "--mode",
        choices=["image", "mixed", "video"],
        default=None,
        help="How scenes are shown: still images with camera moves, a mix, or all video (default: CLIP_MODE)",
    )
    pipeline_cmd.add_argument(
        "--video-model",
        default=None,
        help="Video model for this run, e.g. veo-3.1-lite-generate-preview or gemini-omni-1.1-flash "
        "(default: VIDEO_MODEL)",
    )

    pipeline_cmd.add_argument(
        "--publish",
        action="store_true",
        help="Post to Instagram as soon as the video is made (default: stop for review, then use "
        "`instagram upload --run-id`; AUTO_PUBLISH=true in .env does the same)",
    )

    ingest_cmd = subparsers.add_parser("ingest", help="Ingest one PDF or a directory")
    ingest_cmd.add_argument("--path", default=None, help="Single PDF path to ingest")
    ingest_cmd.add_argument("--language", default="en", choices=["en", "ne"], help="Language for single PDF ingestion")
    ingest_cmd.add_argument("--base-dir", default="data/pdfs", help="Base directory with en/ and ne/ subfolders")

    subparsers.add_parser("list", help="List tracked runs and their status")

    instagram_cmd = subparsers.add_parser("instagram", help="Instagram publishing commands")
    instagram_subparsers = instagram_cmd.add_subparsers(dest="instagram_command", required=True)
    upload_cmd = instagram_subparsers.add_parser(
        "upload", help="Publish a completed run's video to Instagram"
    )
    upload_group = upload_cmd.add_mutually_exclusive_group(required=True)
    upload_group.add_argument("--run-id", default=None, help="Publish a specific run id")
    upload_group.add_argument(
        "--all",
        action="store_true",
        help="Publish every tracked run with a ready video that hasn't been uploaded yet",
    )

    return parser


def _print_runs() -> None:
    records = run_store.list_runs()
    if not records:
        print("No tracked runs yet.")
        return

    header = f"{'run_id':<38} {'status':<12} {'video':<6} {'uploaded':<9} {'topic'}"
    print(header)
    print("-" * len(header))
    for record in records:
        print(
            f"{record.run_id:<38} {record.status:<12} "
            f"{'yes' if record.video_ready else 'no':<6} "
            f"{'yes' if record.instagram_uploaded else 'no':<9} "
            f"{record.topic or ''}"
        )


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()

    if args.command == "run":
        if args.mode:
            settings.CLIP_MODE = args.mode
        if args.video_model:
            settings.VIDEO_MODEL = args.video_model
        if args.publish:
            settings.AUTO_PUBLISH = True
        run_pipeline_v1(topic=args.topic, run_id=args.run_id)
        return

    if args.command == "list":
        _print_runs()
        return

    if args.command == "instagram":
        if args.all:
            published = publish_all_pending()
            print(f"Published {len(published)} run(s): {', '.join(published) or '(none pending)'}")
        else:
            publish_run(args.run_id)
            print(f"Published run {args.run_id}")
        return

    if args.path:
        ingest_pdf(args.path, language=args.language)
    else:
        ingest_directory(base_dir=args.base_dir)


if __name__ == "__main__":
    main()
