import argparse

from .core.logging import configure_logging
from .ingest.pdf_ingestor import ingest_directory, ingest_pdf
from .pipeline import run_pipeline_v1


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

    ingest_cmd = subparsers.add_parser("ingest", help="Ingest one PDF or a directory")
    ingest_cmd.add_argument("--path", default=None, help="Single PDF path to ingest")
    ingest_cmd.add_argument("--language", default="en", choices=["en", "ne"], help="Language for single PDF ingestion")
    ingest_cmd.add_argument("--base-dir", default="data/pdfs", help="Base directory with en/ and ne/ subfolders")

    return parser


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()
    if args.command == "run":
        run_pipeline_v1(topic=args.topic, run_id=args.run_id)
        return

    if args.path:
        ingest_pdf(args.path, language=args.language)
    else:
        ingest_directory(base_dir=args.base_dir)


if __name__ == "__main__":
    main()
