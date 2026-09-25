"""Extraccion reproducible de los CSV publicos de la DGOJ.

Contrato de esta fase:
- Se guardan exactamente los bytes recibidos en data/raw, sin renombrar
  columnas, cambiar tipos ni reserializar el CSV.
- Encoding y delimitador se detectan solo para fines de inspeccion; no se
  usan para transformar el contenido guardado.
- Cada descarga queda registrada en data/raw/manifest.json con URL, fecha,
  codigo HTTP, tamano, hash SHA-256 y estructura observada.
- Repetir la descarga (--refresh) no debe sobrescribir en silencio una copia
  congelada con contenido distinto: por defecto, si el hash cambia, se avisa
  y no se sobrescribe salvo que se pase --refresh explicitamente.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from src.config import (
    DATA_RAW_DIR,
    MANIFEST_PATH,
    REQUEST_TIMEOUT_SECONDS,
    SOURCES,
)

HTML_MARKERS = (b"<!doctype html", b"<html")


@dataclass
class ExtractionRecord:
    name: str
    source_url: str
    resolved_url: str
    source_filename: Optional[str]
    retrieved_at_utc: str
    http_status: int
    bytes: int
    sha256: str
    encoding_guess: Optional[str]
    delimiter_guess: Optional[str]
    rows: Optional[int]
    columns: Optional[int]
    column_names: Optional[list]
    local_path: str
    status: str  # "written" | "skipped_unchanged" | "skipped_conflict"
    note: Optional[str] = None


def _looks_like_html(content: bytes) -> bool:
    head = content[:512].lstrip().lower()
    return any(head.startswith(marker) for marker in HTML_MARKERS)


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _guess_filename(content_disposition: Optional[str]) -> Optional[str]:
    if not content_disposition:
        return None
    match = re.search(r'filename="?([^";]+)"?', content_disposition)
    return match.group(1) if match else None


def _guess_encoding(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            content.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin-1"  # decodifica cualquier byte; ultimo recurso


def _guess_delimiter(sample_text: str) -> Optional[str]:
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=";,\t|")
        return dialect.delimiter
    except csv.Error:
        return None


def _inspect_csv(content: bytes) -> dict:
    """Inspecciona (sin modificar) el CSV para el manifiesto."""
    encoding = _guess_encoding(content)
    text = content.decode(encoding, errors="replace")
    delimiter = _guess_delimiter(text[:5000]) or ";"

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return {
            "encoding_guess": encoding,
            "delimiter_guess": delimiter,
            "rows": 0,
            "columns": 0,
            "column_names": [],
        }
    header = rows[0]
    return {
        "encoding_guess": encoding,
        "delimiter_guess": delimiter,
        "rows": len(rows) - 1,
        "columns": len(header),
        "column_names": header,
    }


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def fetch_bytes(url: str, timeout: int = REQUEST_TIMEOUT_SECONDS) -> requests.Response:
    """Descarga una URL siguiendo redirects, con timeout explicito."""
    response = requests.get(url, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response


def extract_one(name: str, url: str, refresh: bool, manifest: dict) -> ExtractionRecord:
    local_path = DATA_RAW_DIR / f"{name}.csv"
    existing_hash = manifest.get(name, {}).get("sha256")

    try:
        response = fetch_bytes(url)
    except requests.RequestException as exc:
        raise RuntimeError(
            f"No se pudo descargar '{name}' desde {url}. "
            f"Comprueba la conexion o si la URL ha cambiado. Detalle: {exc}"
        ) from exc

    content = response.content
    if _looks_like_html(content):
        raise RuntimeError(
            f"La respuesta de '{name}' ({url}) parece HTML, no un CSV. "
            "La URL puede haber cambiado o redirigir a una pagina de error. "
            "No se ha escrito ningun archivo para esta fuente."
        )

    new_hash = _sha256_hex(content)
    inspection = _inspect_csv(content)
    retrieved_at = datetime.now(timezone.utc).isoformat()

    status = "written"
    note = None
    if local_path.exists() and existing_hash and existing_hash != new_hash and not refresh:
        status = "skipped_conflict"
        note = (
            "El contenido remoto difiere del ya congelado en data/raw. "
            "No se sobrescribe sin --refresh explicito."
        )
    elif local_path.exists() and existing_hash == new_hash:
        status = "skipped_unchanged"
        note = "El contenido remoto es identico al ya congelado; no se reescribe."
    else:
        DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)

    return ExtractionRecord(
        name=name,
        source_url=url,
        resolved_url=response.url,
        source_filename=_guess_filename(response.headers.get("Content-Disposition")),
        retrieved_at_utc=retrieved_at,
        http_status=response.status_code,
        bytes=len(content),
        sha256=new_hash,
        encoding_guess=inspection["encoding_guess"],
        delimiter_guess=inspection["delimiter_guess"],
        rows=inspection["rows"],
        columns=inspection["columns"],
        column_names=inspection["column_names"],
        local_path=str(local_path.relative_to(DATA_RAW_DIR.parent.parent)),
        status=status,
        note=note,
    )


def run_extraction(refresh: bool = False) -> list[ExtractionRecord]:
    manifest = _load_manifest()
    records: list[ExtractionRecord] = []

    for name, url in SOURCES.items():
        record = extract_one(name, url, refresh=refresh, manifest=manifest)
        records.append(record)
        # The manifest describes the frozen local snapshot.
        # If the remote source has changed but --refresh was not explicitly
        # requested, preserve the existing manifest entry because the local
        # file has not changed either.
        if record.status != "skipped_conflict":
            manifest[name] = asdict(record)
        print(
            f"[{record.status}] {name}: {record.rows} filas x {record.columns} "
            f"columnas, {record.bytes} bytes, sha256={record.sha256[:12]}..."
        )
        if record.note:
            print(f"    nota: {record.note}")

    _save_manifest(manifest)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Permite sobrescribir una copia congelada cuyo hash remoto ha cambiado.",
    )
    args = parser.parse_args()

    try:
        run_extraction(refresh=args.refresh)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
