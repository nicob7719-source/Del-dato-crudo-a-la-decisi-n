"""Tests de las funciones puras de src/extract.py (sin red).

La descarga real (integracion) se ejecuta con `python -m src.extract`, no
aqui, para que estos tests corran siempre, incluso sin conexion.
"""
from src.extract import (
    _guess_delimiter,
    _guess_encoding,
    _guess_filename,
    _inspect_csv,
    _looks_like_html,
    _sha256_hex,
)

SAMPLE_CSV = '"Año";"Trimestre";"Mes";"GGR"\n2013;"2013.T1";"Enero";1000\n2013;"2013.T1";"Febrero";2000\n'.encode("utf-8-sig")


def test_looks_like_html_detects_html():
    assert _looks_like_html(b"<!DOCTYPE html><html><body>error</body></html>")
    assert _looks_like_html(b"  <html><head></head></html>")


def test_looks_like_html_rejects_csv():
    assert not _looks_like_html(SAMPLE_CSV)


def test_sha256_hex_is_64_hex_chars_and_deterministic():
    digest = _sha256_hex(SAMPLE_CSV)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    assert digest == _sha256_hex(SAMPLE_CSV)


def test_guess_filename_extracts_from_content_disposition():
    header = 'attachment; filename="JUEGO_ONLINE_2025.T3_GGR_CANT_JUGADAS.csv"'
    assert _guess_filename(header) == "JUEGO_ONLINE_2025.T3_GGR_CANT_JUGADAS.csv"


def test_guess_filename_handles_missing_header():
    assert _guess_filename(None) is None


def test_guess_encoding_reads_utf8_sig():
    assert _guess_encoding(SAMPLE_CSV) in {"utf-8-sig", "utf-8"}


def test_guess_delimiter_detects_semicolon():
    text = SAMPLE_CSV.decode("utf-8-sig")
    assert _guess_delimiter(text) == ";"


def test_inspect_csv_reports_rows_and_columns():
    result = _inspect_csv(SAMPLE_CSV)
    assert result["rows"] == 2
    assert result["columns"] == 4
    assert result["column_names"] == ["Año", "Trimestre", "Mes", "GGR"]
