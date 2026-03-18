from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .ares import fetch_website_for_ico
from .db import DATABASE_URL, get_conn

app = FastAPI(title="Skolky local API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://tompta1.github.io",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _distance_sql() -> str:
    return """
    6371.0 * 2 * asin(
        sqrt(
            power(sin(radians((lat - %(lat)s) / 2)), 2)
            + cos(radians(%(lat)s)) * cos(radians(lat))
            * power(sin(radians((lon - %(lon)s) / 2)), 2)
        )
    )
    """


_GYM_EXPR = "school_kind_code = 'C00' and lower(entity_name) like 'gymnázium%%'"


def _build_kind_filter(params: dict[str, Any], kinds: str | None) -> str:
    """Build a WHERE clause fragment for the kinds filter.

    'GYM' is a virtual code for gymnázia (stored as C00 but entity_name starts
    with 'Gymnázium').  The 'C' code matches non-gymnázium C00 rows only.
    All other codes match school_kind_code directly.
    """
    if not kinds:
        return ""
    kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
    if not kind_list:
        return ""

    include_gym = "GYM" in kind_list
    real_kinds = [k for k in kind_list if k != "GYM"]

    clauses: list[str] = []
    if real_kinds:
        params["kinds"] = real_kinds
        if "C" in real_kinds and not include_gym:
            # C requested without GYM: exclude gymnázia from C00 results
            other_kinds = [k for k in real_kinds if k != "C"]
            if other_kinds:
                params["other_kinds"] = other_kinds
                clauses.append(
                    "(school_kind_code = any(%(other_kinds)s)"
                    " or (school_kind_code = 'C00' and not (" + _GYM_EXPR + ")))"
                )
            else:
                clauses.append("(school_kind_code = 'C00' and not (" + _GYM_EXPR + "))")
        else:
            clauses.append("school_kind_code = any(%(kinds)s)")
    if include_gym:
        clauses.append("(" + _GYM_EXPR + ")")

    return "and (" + " or ".join(clauses) + ")" if clauses else ""


def _gym_name_sql(entity_col: str = "entity_name") -> str:
    """SQL expression: strip common legal suffixes from a gymnázium entity name."""
    return f"""regexp_replace({entity_col},
        '\\s*,?\\s*(příspěvková organizace|p\\.o\\.|s\\.r\\.o\\.|a\\.s\\.|o\\.p\\.s\\.)\\s*$',
        '', 'gi')"""


def _kind_code_sql() -> str:
    """Virtual kind code: remap gymnázia to 'GYM'."""
    return f"""case when {_GYM_EXPR} then 'GYM' else school_kind_code end"""


def _name_sql() -> str:
    """Display name: for gymnázia use entity_name (stripped), else school_name/entity_name."""
    return f"""case
        when {_GYM_EXPR} then {_gym_name_sql()}
        else coalesce(school_name, entity_name)
    end"""


def _format_address(row: dict[str, Any]) -> str:
    return ", ".join(
        part
        for part in [
            " ".join(x for x in [row.get("street"), row.get("house_number"), row.get("orientation_number")] if x),
            row.get("municipality_part"),
            row.get("municipality"),
            row.get("postal_code"),
        ]
        if part
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "database_url": DATABASE_URL.rsplit("@", 1)[-1],
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/schools/map")
def all_schools_for_map(
    kinds: str | None = Query(None, description="Comma-separated school_kind_code filter, e.g. A00,B00"),
) -> dict[str, Any]:
    """Lightweight endpoint for map display — returns all schools with coordinates."""
    params: dict[str, Any] = {}
    kind_filter = _build_kind_filter(params, kinds)

    name_sql = _name_sql()
    kind_code_sql = _kind_code_sql()
    query = f"""
        select
            external_key,
            {name_sql} as name,
            {kind_code_sql} as school_kind_code,
            lat,
            lon,
            municipality,
            data_box_id,
            website,
            email,
            street,
            house_number,
            orientation_number,
            municipality_part,
            postal_code
        from school_places
        where lat is not null and lon is not null
        {kind_filter}
        order by school_kind_code, external_key
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    for row in rows:
        row["address"] = _format_address(row)
        # keep street for "Mateřská škola Kapradová" style display names
        for f in ("house_number", "orientation_number", "municipality_part", "postal_code"):
            row.pop(f, None)

    return {"items": rows, "total": len(rows)}


@app.get("/api/schools/nearby")
def nearby_schools(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    limit: int = Query(10, ge=1, le=50),
    kinds: str | None = Query(None, description="Comma-separated school_kind_code filter"),
) -> dict[str, Any]:
    distance_sql = _distance_sql()

    params: dict[str, Any] = {"lat": lat, "lon": lon, "limit": limit}
    kind_filter = _build_kind_filter(params, kinds)

    kind_code_sql = _kind_code_sql()
    query = f"""
        select
            external_key,
            entity_ico,
            red_izo,
            school_izo,
            place_izo,
            entity_name,
            school_name,
            {kind_code_sql} as school_kind_code,
            municipality,
            municipality_part,
            street,
            house_number,
            orientation_number,
            postal_code,
            lat,
            lon,
            website,
            email,
            website_checked_at,
            data_box_id,
            data_box_type,
            data_box_subtype,
            data_box_name,
            {distance_sql} as distance_km
        from school_places
        where lat is not null and lon is not null
        {kind_filter}
        order by distance_km asc nulls last
        limit %(limit)s
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No schools found. Run the ETL first.")

        dirty_icos: set[str] = set()
        for row in rows:
            ico = row.get("entity_ico")
            if not row.get("website") and ico and row.get("website_checked_at") is None:
                dirty_icos.add(ico)

        for ico in dirty_icos:
            website = fetch_website_for_ico(ico)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update school_places
                    set website = coalesce(%s, website),
                        website_checked_at = now(),
                        updated_at = now()
                    where entity_ico = %s
                    """,
                    (website, ico),
                )
        if dirty_icos:
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

    for row in rows:
        row["address"] = _format_address(row)
        if isinstance(row.get("distance_km"), float):
            row["distance_km"] = round(row["distance_km"], 2)

    return {"items": rows, "count": len(rows)}


@app.post("/api/schools/enrich")
def enrich_schools(
    external_keys: Annotated[list[str], Body()],
) -> dict[str, Any]:
    """ARES-enrich up to 5 schools that have no website yet. Persists each result
    immediately so a Vercel timeout cannot roll back already-completed lookups."""
    keys = list(dict.fromkeys(external_keys))[:5]  # dedup, cap — fits Vercel 10 s limit
    if not keys:
        return {"updates": {}}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select external_key, entity_ico
                from school_places
                where external_key = any(%(keys)s)
                  and website is null
                  and website_checked_at is null
                  and entity_ico is not null
                """,
                {"keys": keys},
            )
            rows = cur.fetchall()

        if not rows:
            return {"updates": {}}

        # group by ICO — one ARES call covers all schools sharing an entity
        ico_to_keys: dict[str, list[str]] = {}
        for row in rows:
            ico_to_keys.setdefault(row["entity_ico"], []).append(row["external_key"])

        updates: dict[str, str] = {}
        for ico, school_keys in ico_to_keys.items():
            website = fetch_website_for_ico(ico, timeout=5)  # short timeout for serverless
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update school_places
                    set website = coalesce(%s, website),
                        website_checked_at = now(),
                        updated_at = now()
                    where entity_ico = %s
                    """,
                    (website, ico),
                )
            conn.commit()  # commit immediately — survives a mid-batch timeout
            if website:
                for key in school_keys:
                    updates[key] = website

    return {"updates": updates}
