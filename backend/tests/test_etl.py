"""
ETL unit tests — pure functions, no DB or network required.

Run:  pytest tests/test_etl.py -v
"""
import pytest
from pathlib import Path

from etl.load import (
    normalize_header,
    parse_address,
    find_column,
    normalized_exact,
    flatten_leaf_nodes,
)
import xml.etree.ElementTree as ET


# ── normalize_header ──────────────────────────────────────

class TestNormalizeHeader:
    def test_ascii_lowercase(self):
        assert normalize_header("hello") == "hello"

    def test_spaces_become_underscores(self):
        assert normalize_header("Kód ADM") == "kod_adm"

    def test_diacritics_stripped(self):
        assert normalize_header("Souřadnice X") == "souradnice_x"
        assert normalize_header("Souřadnice Y") == "souradnice_y"
        assert normalize_header("Název obce")   == "nazev_obce"

    def test_multiple_separators_collapsed(self):
        assert normalize_header("foo--bar") == "foo_bar"
        assert normalize_header("  leading spaces  ") == "leading_spaces"

    def test_empty_string(self):
        assert normalize_header("") == ""


# ── parse_address ─────────────────────────────────────────

class TestParseAddress:
    def test_extracts_municipality(self):
        result = parse_address({"obec": "Praha"})
        assert result["municipality"] == "Praha"

    def test_extracts_street(self):
        result = parse_address({"ulice": "Kapradová"})
        assert result["street"] == "Kapradová"

    def test_extracts_address_point_code(self):
        result = parse_address({"kodRUIAN": "12345678"})
        assert result["address_point_code"] == "12345678"

    def test_falls_back_to_alternative_keys(self):
        result = parse_address({"nazevObce": "Brno"})
        assert result["municipality"] == "Brno"

    def test_returns_none_for_missing_keys(self):
        result = parse_address({})
        assert result["municipality"] is None
        assert result["street"] is None
        assert result["address_point_code"] is None

    def test_none_input_is_safe(self):
        result = parse_address(None)
        assert result["municipality"] is None

    def test_whitespace_only_value_is_none(self):
        result = parse_address({"obec": "   "})
        assert result["municipality"] is None


# ── find_column ───────────────────────────────────────────

class TestFindColumn:
    FIELDS = ["Kód ADM", "Souřadnice X", "Souřadnice Y", "Platí Od"]

    def test_exact_normalized_match(self):
        col = find_column(self.FIELDS, "kod_adm")
        assert col == "Kód ADM"

    def test_tuple_hint_match(self):
        col = find_column(self.FIELDS, ("kod", "adm"))
        assert col == "Kód ADM"

    def test_first_alternative_wins(self):
        col = find_column(self.FIELDS, "souradnice_x", "souradnice_y")
        assert col == "Souřadnice X"

    def test_raises_when_not_found(self):
        with pytest.raises(KeyError, match="Could not find column"):
            find_column(self.FIELDS, "nonexistent_column")

    def test_coordinate_columns_found(self):
        x = find_column(self.FIELDS, "souradnice_x", "x")
        y = find_column(self.FIELDS, "souradnice_y", "y")
        assert x == "Souřadnice X"
        assert y == "Souřadnice Y"


# ── normalized_exact ──────────────────────────────────────

class TestNormalizedExact:
    FIELDS = ["Kód ADM", "Souřadnice X", "Souřadnice Y"]

    def test_finds_by_normalized_name(self):
        assert normalized_exact(self.FIELDS, "kod_adm") == "Kód ADM"

    def test_multiple_alternatives_first_wins(self):
        col = normalized_exact(self.FIELDS, "souradnice_x", "x")
        assert col == "Souřadnice X"

    def test_falls_through_to_second_alternative(self):
        # 'x' normalizes to 'x'; none of our FIELDS normalize to just 'x'
        # so this should fall through — unless we add a plain 'x' field
        fields_with_x = self.FIELDS + ["X"]
        col = normalized_exact(fields_with_x, "nonexistent", "x")
        assert col == "X"

    def test_raises_when_nothing_found(self):
        with pytest.raises(KeyError):
            normalized_exact(self.FIELDS, "totally_missing")


# ── flatten_leaf_nodes ────────────────────────────────────

class TestFlattenLeafNodes:
    def _elem(self, xml_str: str) -> ET.Element:
        return ET.fromstring(xml_str)

    def test_flat_element(self):
        elem = self._elem("<box><id>abc123</id><ico>12345678</ico></box>")
        result = flatten_leaf_nodes(elem)
        assert result["id"] == "abc123"
        assert result["ico"] == "12345678"

    def test_nested_element(self):
        elem = self._elem(
            "<box><id>z6m9</id><info><ico>87654321</ico></info></box>"
        )
        result = flatten_leaf_nodes(elem)
        assert result["id"] == "z6m9"
        assert result["ico"] == "87654321"

    def test_empty_text_not_included(self):
        elem = self._elem("<box><id>abc</id><empty></empty></box>")
        result = flatten_leaf_nodes(elem)
        assert "empty" not in result
        assert result["id"] == "abc"

    def test_namespaced_tags_stripped(self):
        xml = (
            '<box xmlns:ns="http://example.com/ns">'
            '<ns:id>xyz</ns:id>'
            '<ns:ico>11223344</ns:ico>'
            '</box>'
        )
        elem = self._elem(xml)
        result = flatten_leaf_nodes(elem)
        assert result["id"] == "xyz"
        assert result["ico"] == "11223344"

    def test_short_name_also_exposed(self):
        """flatten_leaf_nodes should expose both the full prefixed key and the short tag name."""
        elem = self._elem("<outer><inner><id>test</id></inner></outer>")
        result = flatten_leaf_nodes(elem)
        # short name 'id' must be present
        assert result.get("id") == "test"
