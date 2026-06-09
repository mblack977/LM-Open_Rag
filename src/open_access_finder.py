import logging
import re
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB
_HEADERS = {"User-Agent": "HerbGPT/1.0 (research tool; mailto:research@example.com)"}


def safe_filename(title: str, doc_id: int) -> str:
    safe = re.sub(r'[^\w\s-]', '', title.lower())
    safe = re.sub(r'[\s-]+', '_', safe).strip('_')[:60]
    return f"oa_{doc_id}_{safe}.pdf"


async def fetch_unpaywall(doi: str, email: str) -> Optional[str]:
    """Return the best open-access PDF URL for a DOI, or None."""
    url = f"{UNPAYWALL_BASE}/{doi.strip()}?email={email}"
    try:
        async with httpx.AsyncClient(timeout=20.0, headers=_HEADERS) as client:
            resp = await client.get(url)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            logger.warning(f"Unpaywall {resp.status_code} for DOI {doi!r}")
            return None
        data = resp.json()
        if not data.get("is_oa"):
            return None
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf")
        if not pdf_url:
            for loc in data.get("oa_locations", []):
                if loc.get("url_for_pdf"):
                    pdf_url = loc["url_for_pdf"]
                    break
        return pdf_url
    except Exception as e:
        logger.error(f"Unpaywall error for {doi!r}: {e}")
        return None


async def download_pdf(url: str, dest_path: Path) -> bool:
    """Stream a PDF to dest_path. Returns True on success."""
    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    logger.warning(f"PDF download {resp.status_code}: {url}")
                    return False
                total = 0
                chunks = []
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    total += len(chunk)
                    if total > MAX_PDF_BYTES:
                        logger.warning(f"PDF exceeds 25 MB limit, skipping: {url}")
                        return False
                    chunks.append(chunk)
        dest_path.write_bytes(b"".join(chunks))
        logger.info(f"Downloaded {total // 1024} KB → {dest_path.name}")
        return True
    except Exception as e:
        logger.error(f"PDF download error for {url}: {e}")
        return False
