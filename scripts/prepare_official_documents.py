#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "official_documents_inbox"
ORIGINAL = INBOX / "original"
CONVERTED = INBOX / "converted"
CORPUS = INBOX / "official_corpus.json"

import sys
sys.path.insert(0, str(ROOT))
from app import extract_uploaded_text

MONTHS = {
    "января": "январь", "февраля": "февраль", "марта": "март",
    "апреля": "апрель", "мая": "май", "июня": "июнь",
    "июля": "июль", "августа": "август", "сентября": "сентябрь",
    "октября": "октябрь", "ноября": "ноябрь", "декабря": "декабрь",
}

def convert_doc(path: Path) -> Path:
    CONVERTED.mkdir(parents=True, exist_ok=True)
    target = CONVERTED / (path.stem + ".docx")
    if target.exists() and target.stat().st_mtime >= path.stat().st_mtime:
        return target
    profile = Path(tempfile.mkdtemp(prefix="cps-lo-"))
    try:
        subprocess.run([
            "soffice", f"-env:UserInstallation=file://{profile}", "--headless",
            "--convert-to", "docx", "--outdir", str(CONVERTED), str(path),
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not target.exists():
        raise RuntimeError(f"LibreOffice did not create {target.name}")
    return target


def approval_period(lines: list[str]) -> str | None:
    for line in lines[:15]:
        match = re.search(r"(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(20\d{2})", line.lower())
        if match:
            return f"{MONTHS[match.group(1)]} {match.group(2)}"
    return None

def parse_document(path: Path) -> dict[str, object]:
    extracted = extract_uploaded_text(path.name, path.read_bytes())
    lines = [line.strip() for line in extracted["text"].splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"No text extracted from {path.name}")

    code = lines[0]
    try:
        marker = next(i for i, line in enumerate(lines) if line.upper() == "ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ")
    except StopIteration as exc:
        raise ValueError(f"Instruction heading not found in {path.name}") from exc

    position = lines[marker + 1] if marker + 1 < len(lines) else "Должность не указана"
    hierarchy: list[str] = []
    for line in lines[marker + 2:marker + 6]:
        if line.startswith("Настоящая должностная инструкция"):
            break
        hierarchy.append(line)
    department = " / ".join(hierarchy)
    period = approval_period(lines)
    title = f"{code} — {position}"
    if department:
        title += f" — {department}"

    section = "Общие положения"
    clauses: list[dict[str, str]] = []

    known_sections = {
        "общие положения", "должностные обязанности", "права",
        "ответственность", "заключительные положения",
    }
    for line in lines[marker + 1:]:
        normalized = line.strip().rstrip(".").lower()
        if normalized in known_sections:
            section = line.strip().rstrip(".")
            continue
        if len(line) < 25:
            continue
        if line.startswith("Настоящая должностная инструкция определяет"):
            continue
        clauses.append({
            "quote": line,
            "search_text": f"{code} {position} {department} {section} {line}",
            "section": section,
        })

    version = f"{period or 'дата утверждения не указана'}; номер версии не указан"
    return {
        "document_id": code,
        "title": title,
        "version": version,
        "effective_date": None,
        "status": "current",
        "priority": "Приоритет между инструкциями в пакете не задан",
        "source_file": path.name,
        "approval_period": period,
        "position": position,
        "department": department,
        "clauses": clauses,
        "text": extracted["text"],
    }

def main() -> None:
    ORIGINAL.mkdir(parents=True, exist_ok=True)
    docs = sorted(ORIGINAL.glob("*.doc"))
    docx = sorted(ORIGINAL.glob("*.docx"))
    if not docs and not docx:
        raise SystemExit(f"No .doc/.docx files in {ORIGINAL}")

    converted = [convert_doc(path) for path in docs]
    converted.extend(docx)
    corpus = [parse_document(path) for path in sorted(converted, key=lambda p: p.name)]
    CORPUS.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(corpus)} documents -> {CORPUS}")
    for item in corpus:
        print(f"- {item['document_id']}: {item['position']} ({item['approval_period'] or 'дата не указана'})")


if __name__ == "__main__":
    main()
