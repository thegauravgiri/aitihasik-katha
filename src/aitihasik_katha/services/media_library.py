"""The library of real photos and footage found for any video, kept on disk so later videos
reuse it instead of searching and downloading again.

    data/media_library/index.json   what each file is, its licence, author and credit line
    data/media_library/files/       the downloaded images and videos
"""
import json
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from ..core.settings import settings


@dataclass
class LibraryItem:
    title: str  # the Commons file name
    file: str  # path relative to the library's files/ folder
    kind: str  # "image" or "video"
    license: str
    artist: str
    page_url: str
    width: int
    height: int
    description: str = ""
    queries: list[str] = field(default_factory=list)
    added: str = field(default_factory=lambda: date.today().isoformat())

    @property
    def credit(self) -> str:
        return f'"{self.title}" by {self.artist}, {self.license}, via Wikimedia Commons'


def normalise_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


def _safe_name(title: str) -> str:
    stem, dot, extension = title.rpartition(".")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", stem or title)[:80] + (dot + extension.lower() if dot else "")


class MediaLibrary:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.MEDIA_LIBRARY_PATH)
        self.files_dir = self.root / "files"
        self._index_path = self.root / "index.json"
        self._lock = threading.Lock()
        self._items: dict[str, LibraryItem] = {}
        if self._index_path.exists():
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._items = {title: LibraryItem(**item) for title, item in raw.items()}

    def path_of(self, item: LibraryItem) -> str:
        return str(self.files_dir / item.file)

    def for_query(self, query: str) -> list[LibraryItem]:
        """Items already accepted for this exact search phrase whose files are still on disk."""
        wanted = normalise_query(query)
        return [i for i in self._items.values() if wanted in i.queries and (self.files_dir / i.file).exists()]

    def get(self, title: str) -> LibraryItem | None:
        item = self._items.get(title)
        return item if item and (self.files_dir / item.file).exists() else None

    def file_path_for(self, title: str) -> Path:
        self.files_dir.mkdir(parents=True, exist_ok=True)
        return self.files_dir / _safe_name(title)

    def add(self, item: LibraryItem, query: str) -> LibraryItem:
        with self._lock:
            known = self._items.setdefault(item.title, item)
            if normalise_query(query) not in known.queries:
                known.queries.append(normalise_query(query))
            self.root.mkdir(parents=True, exist_ok=True)
            self._index_path.write_text(
                json.dumps({t: asdict(i) for t, i in self._items.items()}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            return known
