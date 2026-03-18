from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
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
    kind_filter = ""
    if kinds:
        kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
        if kind_list:
            kind_filter = "and school_kind_code = any(%(kinds)s)"
            params["kinds"] = kind_list

    query = f"""
        select
            external_key,
            coalesce(school_name, entity_name) as name,
            school_kind_code,
            lat,
            lon,
            municipality,
            data_box_id,
            website,
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
    kind_filter = ""
    if kinds:
        kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
        if kind_list:
            kind_filter = "and school_kind_code = any(%(kinds)s)"
            params["kinds"] = kind_list

    query = f"""
        select
            external_key,
            entity_ico,
            red_izo,
            school_izo,
            place_izo,
            entity_name,
            school_name,
            school_kind_code,
            municipality,
            municipality_part,
            street,
            house_number,
            orientation_number,
            postal_code,
            lat,
            lon,
            website,
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
