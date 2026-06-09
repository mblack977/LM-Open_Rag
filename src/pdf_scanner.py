import logging
import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.65

try:
    import PyPDF2
    _HAS_PYPDF2 = True
except ImportError:
    _HAS_PYPDF2 = False


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _pdf_metadata_title(path: Path) -> str:
    if not _HAS_PYPDF2:
        return ""
    try:
        reader = PyPDF2.PdfReader(str(path), strict=False)
        info = reader.metadata
        if info:
            title = info.get('/Title') or info.get('Title') or ''
            return str(title).strip()
    except Exception:
        pass
    return ""


def scan_directory(scan_dir: Path) -> List[Tuple[Path, str, str]]:
    """Return list of (pdf_path, norm_stem, norm_meta_title) for every PDF found."""
    pdfs = list(scan_dir.rglob("*.pdf")) + list(scan_dir.rglob("*.PDF"))
    result = []
    for p in pdfs:
        norm_stem = _normalize(p.stem)
        meta_title = _pdf_metadata_title(p)
        norm_meta = _normalize(meta_title) if meta_title else ""
        result.append((p, norm_stem, norm_meta))
    logger.info(f"pdf_scanner: found {len(result)} PDFs in {scan_dir}")
    return result


def find_pdf_matches(
    documents: List[Dict[str, Any]],
    scan_dir: Path,
) -> List[Dict[str, Any]]:
    """
    Match documents (without PDFs) to PDF files in scan_dir.
    Returns list of match dicts sorted by score descending.
    """
    pdf_data = scan_directory(scan_dir)
    if not pdf_data:
        return []

    logger.info(f"Matching {len(documents)} unattached docs against {len(pdf_data)} PDFs")

    matches = []
    for doc in documents:
        doc_id = doc.get("id")
        title = doc.get("title") or ""
        if not title or doc_id is None:
            continue

        norm_title = _normalize(title)
        best_score = 0.0
        best_path: Optional[Path] = None
        best_method = ""

        for pdf_path, norm_stem, norm_meta in pdf_data:
            stem_score = _similarity(norm_title, norm_stem)
            meta_score = _similarity(norm_title, norm_meta) if norm_meta else 0.0
            score = max(stem_score, meta_score)
            method = "metadata" if (norm_meta and meta_score >= stem_score) else "filename"

            if score > best_score:
                best_score = score
                best_path = pdf_path
                best_method = method

        if best_score >= MATCH_THRESHOLD and best_path is not None:
            matches.append({
                "document_id": doc_id,
                "document_title": title,
                "pdf_path": str(best_path),
                "pdf_name": best_path.name,
                "score": round(best_score, 3),
                "match_method": best_method,
            })
            logger.info(
                f"  Matched '{best_path.name}' → '{title[:60]}' "
                f"(score={best_score:.2f}, {best_method})"
            )
        else:
            logger.debug(f"  No match for '{title[:60]}' (best={best_score:.2f})")

    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches


def copy_pdf_to_uploads(pdf_path: Path, uploads_dir: Path, doc_id: int) -> Path:
    """Copy a matched PDF into the uploads directory. Returns the destination path."""
    dest = uploads_dir / pdf_path.name
    if dest.exists() and dest.resolve() != pdf_path.resolve():
        dest = uploads_dir / f"doc{doc_id}_{pdf_path.name}"
    shutil.copy2(str(pdf_path), str(dest))
    return dest
