-- Initial schema: school_places table with all original columns.
create table school_places (
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
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index ix_school_places_entity_ico on school_places(entity_ico);
create index ix_school_places_address_point_code on school_places(address_point_code);
create index ix_school_places_lat_lon on school_places(lat, lon);
