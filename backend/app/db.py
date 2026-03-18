from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://skolky:skolky@localhost:5432/skolky")


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


SCHEMA_SQL = """
create table if not exists school_places (
    external_key text primary key,
    entity_ico text,
    red_izo text,
    school_izo text,
    place_izo text,
    entity_name text,
    school_name text,
    school_kind_code text,
    address_point_code text,
    municipality text,
    municipality_part text,
    street text,
    house_number text,
    orientation_number text,
    postal_code text,
    x_jtsk double precision,
    y_jtsk double precision,
    lon double precision,
    lat double precision,
    website text,
    website_checked_at timestamptz,
    data_box_id text,
    data_box_type text,
    data_box_subtype text,
    data_box_name text,
    legal_form_code text,
    founder_type_code text,
    source_year integer,
    raw_source jsonb,
    email text,
    phone text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists ix_school_places_entity_ico on school_places(entity_ico);
create index if not exists ix_school_places_address_point_code on school_places(address_point_code);
create index if not exists ix_school_places_lat_lon on school_places(lat, lon);
"""


UPSERT_SQL = """
insert into school_places (
    external_key,
    entity_ico,
    red_izo,
    school_izo,
    place_izo,
    entity_name,
    school_name,
    school_kind_code,
    address_point_code,
    municipality,
    municipality_part,
    street,
    house_number,
    orientation_number,
    postal_code,
    x_jtsk,
    y_jtsk,
    lon,
    lat,
    website,
    data_box_id,
    data_box_type,
    data_box_subtype,
    data_box_name,
    legal_form_code,
    founder_type_code,
    source_year,
    raw_source,
    email,
    phone,
    updated_at
)
values (
    %(external_key)s,
    %(entity_ico)s,
    %(red_izo)s,
    %(school_izo)s,
    %(place_izo)s,
    %(entity_name)s,
    %(school_name)s,
    %(school_kind_code)s,
    %(address_point_code)s,
    %(municipality)s,
    %(municipality_part)s,
    %(street)s,
    %(house_number)s,
    %(orientation_number)s,
    %(postal_code)s,
    %(x_jtsk)s,
    %(y_jtsk)s,
    %(lon)s,
    %(lat)s,
    %(website)s,
    %(data_box_id)s,
    %(data_box_type)s,
    %(data_box_subtype)s,
    %(data_box_name)s,
    %(legal_form_code)s,
    %(founder_type_code)s,
    %(source_year)s,
    %(raw_source)s,
    %(email)s,
    %(phone)s,
    now()
)
on conflict (external_key)
do update set
    entity_ico = excluded.entity_ico,
    red_izo = excluded.red_izo,
    school_izo = excluded.school_izo,
    place_izo = excluded.place_izo,
    entity_name = excluded.entity_name,
    school_name = excluded.school_name,
    school_kind_code = excluded.school_kind_code,
    address_point_code = excluded.address_point_code,
    municipality = excluded.municipality,
    municipality_part = excluded.municipality_part,
    street = excluded.street,
    house_number = excluded.house_number,
    orientation_number = excluded.orientation_number,
    postal_code = excluded.postal_code,
    x_jtsk = excluded.x_jtsk,
    y_jtsk = excluded.y_jtsk,
    lon = excluded.lon,
    lat = excluded.lat,
    data_box_id = excluded.data_box_id,
    data_box_type = excluded.data_box_type,
    data_box_subtype = excluded.data_box_subtype,
    data_box_name = excluded.data_box_name,
    legal_form_code = excluded.legal_form_code,
    founder_type_code = excluded.founder_type_code,
    source_year = excluded.source_year,
    raw_source = excluded.raw_source,
    email = excluded.email,
    phone = excluded.phone,
    updated_at = now();
"""


def init_schema() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
