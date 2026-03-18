"""
API integration tests — run against the live local DB.
Requires the ETL to have been run at least once:
  python -m etl.load load

Run:  pytest tests/test_api.py -v
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=True)

PRAGUE_LAT = 50.0755
PRAGUE_LON = 14.4378

# Czech Republic bounding box (generous)
CZ = dict(min_lat=48.5, max_lat=51.2, min_lon=12.0, max_lon=18.9)


# ── /api/health ───────────────────────────────────────────

def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "time" in body


# ── /api/schools/map ──────────────────────────────────────

def test_map_returns_items():
    r = client.get("/api/schools/map?kinds=A00")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] > 0
    assert len(body["items"]) == body["total"]


def test_map_required_fields():
    r = client.get("/api/schools/map?kinds=A00")
    item = r.json()["items"][0]
    required = {
        "external_key", "name", "school_kind_code",
        "lat", "lon", "street", "municipality",
        "data_box_id", "address",
    }
    missing = required - item.keys()
    assert not missing, f"Missing fields: {missing}"


def test_map_street_present():
    """street must be returned so the frontend can build 'Mateřská škola Kapradová'."""
    r = client.get("/api/schools/map?kinds=A00")
    items = r.json()["items"]
    # Not every school has a street, but the key must be present
    assert all("street" in i for i in items[:50])


def test_map_kind_filter_respected():
    """When filtering by A00, all returned items must be A00."""
    r = client.get("/api/schools/map?kinds=A00")
    items = r.json()["items"]
    non_a00 = [i for i in items if i["school_kind_code"] != "A00"]
    assert non_a00 == [], f"Got non-A00 items: {non_a00[:3]}"


def test_map_multiple_kinds():
    r_a = client.get("/api/schools/map?kinds=A00")
    r_b = client.get("/api/schools/map?kinds=B00")
    r_ab = client.get("/api/schools/map?kinds=A00,B00")
    assert r_ab.json()["total"] == r_a.json()["total"] + r_b.json()["total"]


def test_map_no_filter_returns_all():
    r_all = client.get("/api/schools/map")
    r_a00 = client.get("/api/schools/map?kinds=A00")
    assert r_all.json()["total"] > r_a00.json()["total"]


def test_map_coords_in_czechia():
    """Every coordinate must fall within the Czech Republic bounding box."""
    r = client.get("/api/schools/map?kinds=A00,B00")
    bad = []
    for item in r.json()["items"]:
        lat, lon = item["lat"], item["lon"]
        if not (CZ["min_lat"] <= lat <= CZ["max_lat"] and CZ["min_lon"] <= lon <= CZ["max_lon"]):
            bad.append({"key": item["external_key"], "lat": lat, "lon": lon})
    assert not bad, f"Coordinates outside Czechia (first 3): {bad[:3]}"


def test_map_no_jtsk_leak():
    """
    Before the coordinate-transform fix, un-negated JTSK values were stored
    (x ~ 515 000, y ~ 1 166 000). Ensure that regression is gone.
    """
    r = client.get("/api/schools/map?kinds=A00")
    for item in r.json()["items"]:
        assert item["lat"] < 1000, f"lat looks like raw JTSK: {item['lat']}"
        assert item["lon"] < 1000, f"lon looks like raw JTSK: {item['lon']}"


def test_map_data_box_ids_present():
    """The vast majority of schools should have a data-box ID."""
    r = client.get("/api/schools/map?kinds=A00")
    items = r.json()["items"]
    with_ds = sum(1 for i in items if i.get("data_box_id"))
    pct = with_ds / len(items)
    assert pct > 0.95, f"Only {pct:.0%} of Mateřská škola records have a data-box ID"


# ── /api/schools/nearby ───────────────────────────────────

def test_nearby_returns_items():
    r = client.get(f"/api/schools/nearby?lat={PRAGUE_LAT}&lon={PRAGUE_LON}")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert len(body["items"]) > 0


def test_nearby_default_limit_is_10():
    r = client.get(f"/api/schools/nearby?lat={PRAGUE_LAT}&lon={PRAGUE_LON}")
    assert len(r.json()["items"]) == 10


def test_nearby_respects_limit():
    r = client.get(f"/api/schools/nearby?lat={PRAGUE_LAT}&lon={PRAGUE_LON}&limit=3")
    assert len(r.json()["items"]) == 3


def test_nearby_sorted_by_distance():
    r = client.get(f"/api/schools/nearby?lat={PRAGUE_LAT}&lon={PRAGUE_LON}&limit=20")
    distances = [i["distance_km"] for i in r.json()["items"]]
    assert distances == sorted(distances), "Items must be ordered by ascending distance"


def test_nearby_distance_is_small_for_prague():
    """Nearest school from Prague centre should be well under 1 km."""
    r = client.get(f"/api/schools/nearby?lat={PRAGUE_LAT}&lon={PRAGUE_LON}&limit=1")
    nearest = r.json()["items"][0]
    assert nearest["distance_km"] < 1.0, f"Expected < 1 km, got {nearest['distance_km']}"


def test_nearby_has_school_kind_code():
    r = client.get(f"/api/schools/nearby?lat={PRAGUE_LAT}&lon={PRAGUE_LON}&limit=5")
    for item in r.json()["items"]:
        assert "school_kind_code" in item


def test_nearby_kind_filter():
    r_all  = client.get(f"/api/schools/nearby?lat={PRAGUE_LAT}&lon={PRAGUE_LON}&limit=10")
    r_a00  = client.get(f"/api/schools/nearby?lat={PRAGUE_LAT}&lon={PRAGUE_LON}&limit=10&kinds=A00")
    kinds_all = {i["school_kind_code"] for i in r_all.json()["items"]}
    kinds_a00 = {i["school_kind_code"] for i in r_a00.json()["items"]}
    assert kinds_a00 == {"A00"}, f"Expected only A00, got {kinds_a00}"
    # unfiltered result should have more variety (Prague has multiple school types)
    assert len(kinds_all) > 1


def test_nearby_coords_in_czechia():
    r = client.get(f"/api/schools/nearby?lat={PRAGUE_LAT}&lon={PRAGUE_LON}&limit=10")
    for item in r.json()["items"]:
        lat, lon = item["lat"], item["lon"]
        assert CZ["min_lat"] <= lat <= CZ["max_lat"]
        assert CZ["min_lon"] <= lon <= CZ["max_lon"]


def test_nearby_missing_lat_returns_422():
    r = client.get(f"/api/schools/nearby?lon={PRAGUE_LON}")
    assert r.status_code == 422


def test_nearby_out_of_range_lat_returns_422():
    r = client.get("/api/schools/nearby?lat=91&lon=14")
    assert r.status_code == 422
