from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Iterable

import requests
from pyproj import Transformer

from app.db import UPSERT_SQL, get_conn, init_schema

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
RAW_DIR = DATA_DIR / "raw"

SCHOOL_REGISTRY_URL = (
    "https://lkod-ftp.msmt.gov.cz/00022985/250d6b3f-71a2-4441-b8a0-4df141071f13/"
    "rssz-cela-cr-2026-01-01.jsonld"
)
DATABOX_PO_URL = "https://www.mojedatovaschranka.cz/sds/datafile?format=xml&service=seznam_ds_po"
DATABOX_OVM_URL = "https://www.mojedatovaschranka.cz/sds/datafile?format=xml&service=seznam_ds_ovm"
RUIAN_ATOM_FEED = "https://atom.cuzk.gov.cz/RUIAN-CSV-ADR-ST/RUIAN-CSV-ADR-ST.xml"

TRANSFORMER = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url: str, target: Path) -> None:
    print(f"Downloading {url} -> {target}")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with target.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)


def discover_latest_ruian_zip() -> str:
    response = requests.get(RUIAN_ATOM_FEED, timeout=60)
    response.raise_for_status()
    text = response.text
    urls = sorted(set(re.findall(r"https?://[^\s\"'<>()]+\.zip", text, flags=re.I)))
    if urls:
        return urls[-1]

    # Fallback to the public directory listing that exposes the latest monthly ZIP.
    listing_url = "https://services.cuzk.gov.cz/atom-index/RUIAN-CSV-ADR-ST/5513"
    listing = requests.get(listing_url, timeout=60)
    listing.raise_for_status()
    match = re.search(r"(https?://[^\s\"'<>()]+\.zip)", listing.text, flags=re.I)
    if match:
        return match.group(1)

    raise RuntimeError("Could not discover the latest RUIAN ZIP URL")


def normalize_header(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def recursively_find_entities(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        if "redIzo" in node and "skolyAZarizeni" in node:
            yield node
        for value in node.values():
            yield from recursively_find_entities(value)
    elif isinstance(node, list):
        for item in node:
            yield from recursively_find_entities(item)


def parse_address(data: dict[str, Any] | None) -> dict[str, Any]:
    data = data or {}

    def pick(*keys: str) -> str | None:
        for key in keys:
            value = data.get(key)
            if value is not None:
                text = str(value).strip()
                if text:
                    return text
        return None

    return {
        "address_point_code": pick("kodRUIAN", "kodAdm", "kodAdresnihoMista", "addressPoint"),
        "municipality": pick("obec", "nazevObce"),
        "municipality_part": pick("castObce", "nazevCastiObce"),
        "street": pick("ulice", "nazevUlice"),
        "house_number": pick("cisloDomovni"),
        "orientation_number": pick("cisloOrientacni"),
        "postal_code": pick("psc", "postCode"),
    }


def load_school_registry(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for entity in recursively_find_entities(payload):
        entity_ico = str(entity.get("ico") or "").zfill(8) if entity.get("ico") else None
        red_izo = str(entity.get("redIzo") or "").strip() or None
        entity_name = entity.get("uplnyNazev") or entity.get("zkracenyNazev")
        legal_form_code = str(entity.get("pravniForma") or "").strip() or None
        founder_type_code = str(entity.get("typZrizovatele") or "").strip() or None
        entity_email = (entity.get("emaily") or [None])[0]
        for school in entity.get("skolyAZarizeni") or []:
            if not isinstance(school, dict):
                continue
            school_izo = str(school.get("izo") or "").strip() or None
            school_name = school.get("uplnyNazev") or school.get("zkracenyNazev")
            places = school.get("mistaVyuky") or []
            if not places:
                places = [{"izo": school_izo, "typ": school.get("druh"), "adresa": entity.get("adresa") or school.get("adresa")}]
            for idx, place in enumerate(places, start=1):
                if not isinstance(place, dict):
                    continue
                address = parse_address(place.get("adresa") or school.get("adresa") or entity.get("adresa"))
                place_izo = str(place.get("izo") or "").strip() or None
                place_key = place_izo or address["address_point_code"] or str(idx)
                record = {
                    "external_key": ":".join(x for x in [entity_ico or "noico", school_izo or "noschool", place_key] if x),
                    "entity_ico": entity_ico,
                    "red_izo": red_izo,
                    "school_izo": school_izo,
                    "place_izo": place_izo,
                    "entity_name": entity_name,
                    "school_name": school_name,
                    "school_kind_code": str(school.get("druh") or "").strip() or None,
                    "legal_form_code": legal_form_code,
                    "founder_type_code": founder_type_code,
                    "source_year": 2026,
                    "raw_source": {
                        "entity": {
                            "ico": entity_ico,
                            "redIzo": red_izo,
                            "uplnyNazev": entity_name,
                            "pravniForma": legal_form_code,
                            "typZrizovatele": founder_type_code,
                        },
                        "school": {
                            "izo": school_izo,
                            "uplnyNazev": school_name,
                            "druh": school.get("druh"),
                        },
                        "place": place,
                    },
                    **address,
                    "x_jtsk": None,
                    "y_jtsk": None,
                    "lon": None,
                    "lat": None,
                    "website": None,
                    "data_box_id": None,
                    "data_box_type": None,
                    "data_box_subtype": None,
                    "data_box_name": None,
                    "email": entity_email,
                    "phone": None,
                }
                records.append(record)
    print(f"Parsed {len(records)} school workplaces from school registry")
    return records


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def flatten_leaf_nodes(elem: ET.Element, prefix: str = "") -> dict[str, str]:
    """
    Recursively flatten all leaf descendants into a simple dict.
    Keeps the last seen value for duplicate leaf names.
    """
    data: dict[str, str] = {}
    for child in list(elem):
        tag = strip_ns(child.tag)
        key = f"{prefix}_{tag}" if prefix else tag
        if list(child):
            data.update(flatten_leaf_nodes(child, key))
        else:
            value = (child.text or "").strip()
            if value:
                data[key] = value
                # also expose the leaf by its short name for easier matching
                data[tag] = value
    return data


def parse_databox_xml(path: Path) -> dict[str, dict[str, str | None]]:
    """Stream-parse a data-box XML export.

    Uses the root-clear pattern so leaf element text is intact when the
    record-level element fires its 'end' event.
    """
    mapping: dict[str, dict[str, str | None]] = {}

    context = ET.iterparse(path, events=("start", "end"))
    _, root = next(context)  # grab root; clear it after each record to free RAM

    for event, elem in context:
        if event != "end":
            continue

        record = flatten_leaf_nodes(elem)
        if not record:
            continue

        normalized = {normalize_header(k): v for k, v in record.items()}
        keys = set(normalized.keys())

        has_id = "id" in keys
        has_ico = "ico" in keys or any(k.endswith("_ico") for k in keys)

        if has_id and has_ico:
            def pick(*candidates: str) -> str | None:
                for cand in candidates:
                    if cand in normalized and normalized[cand]:
                        return normalized[cand]
                for key, value in normalized.items():
                    if any(key.endswith(c) for c in candidates) and value:
                        return value
                return None

            ico = (pick("ico") or "").strip()
            if ico:
                ico = ico.zfill(8)
                candidate = {
                    "data_box_id": pick("id"),
                    "data_box_type": pick("type", "boxtype"),
                    "data_box_subtype": pick("subtype", "boxsubtype"),
                    "data_box_name": pick("name"),
                    "address_point_code": pick("addresspoint"),
                }

                current = mapping.get(ico)
                if current is None or (
                    candidate.get("data_box_type") == "OVM"
                    and current.get("data_box_type") != "OVM"
                ):
                    mapping[ico] = candidate

            root.clear()  # release children; preserves root reference for next iteration

    print(f"Parsed {len(mapping)} data-box entities from {path.name}")
    return mapping


def find_column(fieldnames: list[str], *alternatives: tuple[str, ...] | str) -> str:
    """
    Flexible matcher.
    Each alternative can be:
      - a string: exact normalized field name
      - a tuple[str, ...]: all hints must be present in the normalized field name
    """
    normalized_map = {normalize_header(name): name for name in fieldnames}

    for alt in alternatives:
        if isinstance(alt, str):
            if alt in normalized_map:
                return normalized_map[alt]
        else:
            for norm, original in normalized_map.items():
                if all(hint in norm for hint in alt):
                    return original

    raise KeyError(f"Could not find column for alternatives={alternatives}; got={fieldnames}")


def normalized_exact(fieldnames: list[str], *wanted: str) -> str:
    normalized_map = {normalize_header(name): name for name in fieldnames}
    for item in wanted:
        if item in normalized_map:
            return normalized_map[item]
    raise KeyError(f"Could not find any of {wanted}; got={fieldnames}")


def _decode_csv_bytes(raw: bytes) -> tuple[str, str]:
    """Decode raw CSV bytes, returning (sample, full_text)."""
    for encoding in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            sample = raw[:8192].decode(encoding)
            text = raw.decode(encoding)
            return sample, text
        except UnicodeDecodeError:
            continue
    raise RuntimeError("Could not decode CSV bytes")


def load_ruian_points(zip_path: Path) -> dict[str, tuple[float, float, float, float]]:
    zf = zipfile.ZipFile(zip_path)
    csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not csv_names:
        raise RuntimeError(f"No CSV found inside {zip_path}")

    points: dict[str, tuple[float, float, float, float]] = {}
    code_col: str | None = None
    x_col: str | None = None
    y_col: str | None = None

    for csv_name in csv_names:
        raw = zf.read(csv_name)
        try:
            sample, text = _decode_csv_bytes(raw)
        except RuntimeError:
            continue

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"

        stream = io.StringIO(text)
        reader = csv.DictReader(stream, dialect=dialect)
        fieldnames = reader.fieldnames or []

        if code_col is None:
            code_col = find_column(fieldnames, "kod_adm", ("kod", "adres"), ("kod", "adm"))
            x_col = normalized_exact(fieldnames, "souradnice_x", "x")
            y_col = normalized_exact(fieldnames, "souradnice_y", "y")

        for row in reader:
            code = (row.get(code_col) or "").strip()
            x_raw = (row.get(x_col) or "").strip().replace(",", ".")
            y_raw = (row.get(y_col) or "").strip().replace(",", ".")
            if not code or not x_raw or not y_raw:
                continue
            try:
                x_jtsk = float(x_raw)
                y_jtsk = float(y_raw)
                # EPSG:5514 always_xy expects (Westing, Southing) = (-trad_Y, -trad_X)
                lon, lat = TRANSFORMER.transform(-y_jtsk, -x_jtsk)
            except Exception:
                continue
            points[code] = (x_jtsk, y_jtsk, lon, lat)

    print(f"Parsed {len(points)} RUIAN address points from {zip_path.name} ({len(csv_names)} files)")
    return points


def open_csv_from_zip(zip_path: Path) -> tuple[list[str], Iterable[dict[str, str]]]:
    zf = zipfile.ZipFile(zip_path)
    csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
    if not csv_names:
        raise RuntimeError(f"No CSV found inside {zip_path}")
    name = csv_names[0]
    raw = zf.read(name)
    sample, text = _decode_csv_bytes(raw)

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"

    stream = io.StringIO(text)
    reader = csv.DictReader(stream, dialect=dialect)
    return reader.fieldnames or [], reader




def download_sources() -> None:
    ensure_dirs()
    download_file(SCHOOL_REGISTRY_URL, RAW_DIR / "schools_2026.jsonld")
    download_file(DATABOX_PO_URL, RAW_DIR / "databox_po.xml")
    download_file(DATABOX_OVM_URL, RAW_DIR / "databox_ovm.xml")
    ruian_url = discover_latest_ruian_zip()
    print(f"Discovered latest RUIAN ZIP: {ruian_url}")
    download_file(ruian_url, RAW_DIR / "ruian_addresses.zip")


def load_db() -> None:
    ensure_dirs()
    init_schema()

    schools_path = RAW_DIR / "schools_2026.jsonld"
    databox_po_path = RAW_DIR / "databox_po.xml"
    databox_ovm_path = RAW_DIR / "databox_ovm.xml"
    ruian_path = RAW_DIR / "ruian_addresses.zip"

    missing = [p for p in [schools_path, databox_po_path, databox_ovm_path, ruian_path] if not p.exists()]
    if missing:
        raise RuntimeError(f"Missing source files: {missing}. Run `download` first.")

    school_rows = load_school_registry(schools_path)
    databox_map = parse_databox_xml(databox_po_path)
    databox_map.update(parse_databox_xml(databox_ovm_path))
    ruian_points = load_ruian_points(ruian_path)

    prepared: list[dict[str, Any]] = []
    for row in school_rows:
        ico = row.get("entity_ico")
        if ico and ico in databox_map:
            row.update({k: v for k, v in databox_map[ico].items() if k in {"data_box_id", "data_box_type", "data_box_subtype", "data_box_name"}})
            if not row.get("address_point_code"):
                row["address_point_code"] = databox_map[ico].get("address_point_code")
        ap = row.get("address_point_code")
        if ap and ap in ruian_points:
            x_jtsk, y_jtsk, lon, lat = ruian_points[ap]
            row["x_jtsk"] = x_jtsk
            row["y_jtsk"] = y_jtsk
            row["lon"] = lon
            row["lat"] = lat
        prepared.append(row)

    for row in prepared:
        if isinstance(row.get("raw_source"), dict):
            row["raw_source"] = json.dumps(row["raw_source"], ensure_ascii=False)

    batch_size = 500
    upserted = 0
    for i in range(0, len(prepared), batch_size):
        batch = prepared[i : i + batch_size]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(UPSERT_SQL, batch)
            conn.commit()
        upserted += len(batch)
        print(f"  upserted {upserted}/{len(prepared)}")
    print(f"Upserted {upserted} school workplaces into Postgres")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal ETL for Czech kindergarten workplaces")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="Download raw official datasets")
    sub.add_parser("load", help="Parse raw files and load Postgres")
    sub.add_parser("refresh", help="Download and load in one go")
    args = parser.parse_args()

    if args.command == "download":
        download_sources()
    elif args.command == "load":
        load_db()
    elif args.command == "refresh":
        download_sources()
        load_db()


if __name__ == "__main__":
    main()
