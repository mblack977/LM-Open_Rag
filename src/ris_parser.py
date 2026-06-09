import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TY_MAP = {
    "JOUR": "journal_article",
    "JFULL": "journal_article",
    "MGZN": "journal_article",
    "BOOK": "book",
    "CHAP": "book_chapter",
    "CONF": "conference_paper",
    "CPAPER": "conference_paper",
    "THES": "thesis",
    "RPRT": "report",
    "PAMP": "report",
    "NEWS": "other",
    "ELEC": "other",
    "GEN": "other",
    "UNPB": "other",
}


def parse_ris(text: str) -> List[Dict[str, Any]]:
    """Parse RIS-format text and return a list of document dicts ready for DB insert."""
    records: List[Dict[str, Any]] = []
    tags: Dict[str, List[str]] = {}

    for raw_line in text.splitlines():
        # Strip only line endings so a value-less "ER  - " doesn't shrink below the check
        line = raw_line.rstrip('\r\n')
        # RIS format: "XX  - value"  (separator is "  -"; trailing space before value optional)
        # Minimum valid line is "XX  -" (5 chars) for tags with no value (e.g. ER)
        if len(line) < 5 or line[2:5] != "  -":
            continue
        tag = line[:2].upper()
        value = line[5:].lstrip(' ').rstrip()

        if tag == "ER":
            if tags:
                record = _build_record(tags)
                if record:
                    records.append(record)
            tags = {}
            continue

        if value:
            tags.setdefault(tag, []).append(value)

    # Handle files that omit the final ER
    if tags:
        record = _build_record(tags)
        if record:
            records.append(record)

    logger.info(f"RIS parser: found {len(records)} records")
    return records


_FIELD_LIMITS = {
    "title": 1000,
    "author": 2000,
    "abstract": 8000,
    "notes": 5000,
    "apa7_reference": 2000,
}


def _trunc(value: str, field: str) -> str:
    limit = _FIELD_LIMITS.get(field)
    if limit and len(value) > limit:
        logger.warning(f"RIS field '{field}' truncated from {len(value)} to {limit} chars")
        return value[:limit]
    return value


def _build_record(tags: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
    doc: Dict[str, Any] = {}

    ty = tags.get("TY", [""])[0].upper()
    doc["document_type"] = _TY_MAP.get(ty, "other")

    # Title — required; skip record if absent
    title = (tags.get("TI") or tags.get("T1") or [""])[0]
    if not title:
        logger.warning("RIS record skipped: no title found")
        return None
    doc["title"] = _trunc(title, "title")

    # Authors
    raw_authors = tags.get("AU", [])
    if raw_authors:
        doc["author"] = _trunc("; ".join(raw_authors), "author")

    # Year — PY or Y1, split on "/" to get just the year part
    for year_tag in ("PY", "Y1"):
        year_vals = tags.get(year_tag, [])
        if year_vals:
            year_str = year_vals[0].split("/")[0].strip()
            try:
                doc["year"] = int(year_str)
                break
            except ValueError:
                logger.warning(f"RIS: could not parse year '{year_vals[0]}' for '{title}'")

    # Abstract — concatenate if split across multiple AB lines
    ab_parts = tags.get("AB", [])
    if ab_parts:
        doc["abstract"] = _trunc(" ".join(ab_parts), "abstract")

    # DOI
    doi_vals = tags.get("DO", [])
    if doi_vals:
        doc["doi"] = doi_vals[0].strip()

    # Keywords → tags list
    kws = tags.get("KW", [])
    if kws:
        doc["tags"] = kws

    # Build notes from journal/volume/issue/page/publisher + user notes
    notes_parts: List[str] = []

    journal_names = tags.get("JO") or tags.get("JF") or tags.get("T2") or []
    if journal_names:
        notes_parts.append(f"Journal: {journal_names[0]}")

    volume = (tags.get("VL") or [""])[0]
    if volume:
        notes_parts.append(f"Vol: {volume}")

    issue = (tags.get("IS") or [""])[0]
    if issue:
        notes_parts.append(f"Issue: {issue}")

    sp = (tags.get("SP") or [""])[0]
    ep = (tags.get("EP") or [""])[0]
    if sp and ep:
        notes_parts.append(f"Pages: {sp}-{ep}")
    elif sp:
        notes_parts.append(f"Page: {sp}")

    publisher = (tags.get("PB") or [""])[0]
    if publisher:
        notes_parts.append(f"Publisher: {publisher}")

    notes_parts.extend(tags.get("N1", []))

    if notes_parts:
        doc["notes"] = _trunc("\n".join(notes_parts), "notes")

    doc["apa7_reference"] = _trunc(_build_apa7_rough(doc, raw_authors, tags), "apa7_reference")

    return doc


def _build_apa7_rough(
    doc: Dict[str, Any],
    raw_authors: List[str],
    tags: Dict[str, List[str]],
) -> str:
    """Rough APA7 citation from RIS fields. CrossRef enrichment will replace this when available."""
    parts: List[str] = []

    if raw_authors:
        parts.append("; ".join(raw_authors))
    if doc.get("year"):
        parts.append(f"({doc['year']})")
    if doc.get("title"):
        parts.append(f"{doc['title']}.")

    journal_names = tags.get("JO") or tags.get("JF") or tags.get("T2") or []
    if journal_names:
        volume = (tags.get("VL") or [""])[0]
        issue = (tags.get("IS") or [""])[0]
        sp = (tags.get("SP") or [""])[0]
        ep = (tags.get("EP") or [""])[0]
        jref = journal_names[0]
        if volume:
            jref += f", {volume}"
            if issue:
                jref += f"({issue})"
        if sp and ep:
            jref += f", {sp}-{ep}"
        elif sp:
            jref += f", {sp}"
        parts.append(f"{jref}.")

    if doc.get("doi"):
        parts.append(f"https://doi.org/{doc['doi']}")

    return " ".join(parts)
