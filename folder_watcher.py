"""
Folder watcher — monitors a directory and auto-ingests new files into HerbGPT.

Usage:
    python folder_watcher.py

Configuration (edit constants below or set environment variables):
    WATCH_FOLDER      — folder to monitor for new files
    INGEST_COLLECTION — HerbGPT collection to ingest into
    HERBGPT_URL       — HerbGPT server base URL
"""

import json
import logging
import os
import time
from pathlib import Path

import httpx
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ── Configuration ─────────────────────────────────────────────────────────────
WATCH_FOLDER = os.getenv("WATCH_FOLDER", r"C:\Herb Project\Herb_files")
COLLECTION   = os.getenv("INGEST_COLLECTION", "HerbGPT")
SERVER_URL   = os.getenv("HERBGPT_URL", "http://localhost:8010")
INGESTED_LOG = Path(__file__).parent / "data" / ".ingested_files.json"
SUPPORTED_EXT = {".pdf", ".txt", ".docx", ".md"}
SETTLE_SECONDS = 3  # wait after file appears to ensure it's fully written

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _load_ingested() -> set:
    if INGESTED_LOG.exists():
        try:
            return set(json.loads(INGESTED_LOG.read_text()))
        except Exception:
            pass
    return set()


def _save_ingested(ingested: set) -> None:
    INGESTED_LOG.parent.mkdir(parents=True, exist_ok=True)
    INGESTED_LOG.write_text(json.dumps(sorted(ingested), indent=2))


def ingest_file(file_path: Path, ingested: set) -> None:
    key = str(file_path.resolve())

    if key in ingested:
        logger.info("Already ingested, skipping: %s", file_path.name)
        return

    if file_path.suffix.lower() not in SUPPORTED_EXT:
        logger.debug("Unsupported extension, skipping: %s", file_path.name)
        return

    if not file_path.exists() or not file_path.is_file():
        return

    logger.info("Ingesting: %s  →  collection '%s'", file_path.name, COLLECTION)
    try:
        with open(file_path, "rb") as fh:
            resp = httpx.post(
                f"{SERVER_URL}/upload",
                data={"collection": COLLECTION},
                files={"file": (file_path.name, fh, "application/octet-stream")},
                timeout=300.0,
            )

        if resp.status_code == 200:
            ingested.add(key)
            _save_ingested(ingested)
            logger.info("Ingested successfully: %s", file_path.name)
        else:
            logger.error(
                "Ingest failed (%s): %s — %s",
                resp.status_code,
                file_path.name,
                resp.text[:300],
            )
    except Exception as exc:
        logger.error("Error ingesting %s: %s", file_path.name, exc)


class _IngestHandler(FileSystemEventHandler):
    def __init__(self, ingested: set):
        self._ingested = ingested

    def on_created(self, event):
        if event.is_directory:
            return
        time.sleep(SETTLE_SECONDS)
        ingest_file(Path(event.src_path), self._ingested)

    def on_moved(self, event):
        if event.is_directory:
            return
        time.sleep(SETTLE_SECONDS)
        ingest_file(Path(event.dest_path), self._ingested)


def main():
    watch_path = Path(WATCH_FOLDER)
    if not watch_path.exists():
        logger.error("Watch folder does not exist: %s", watch_path)
        return

    ingested = _load_ingested()
    logger.info("Watch folder : %s", watch_path)
    logger.info("Collection   : %s", COLLECTION)
    logger.info("Server       : %s", SERVER_URL)
    logger.info("Already logged: %d file(s)", len(ingested))

    # Catch any files already sitting in the folder
    for f in sorted(watch_path.iterdir()):
        if f.is_file():
            ingest_file(f, ingested)

    handler = _IngestHandler(ingested)
    observer = Observer()
    observer.schedule(handler, str(watch_path), recursive=False)
    observer.start()
    logger.info("Watcher running — drop files into %s to auto-ingest. Ctrl+C to stop.", watch_path)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
