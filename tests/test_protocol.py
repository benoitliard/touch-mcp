"""Unit tests for touch_mcp.bridge.protocol."""

from __future__ import annotations

import json

import pytest

from touch_mcp.bridge.protocol import is_error, make_batch, make_request, parse_response


# ---------------------------------------------------------------------------
# make_request
# ---------------------------------------------------------------------------


class TestMakeRequest:
    """Tests for :func:`make_request`."""

    def test_returns_valid_json_string(self) -> None:
        raw = make_request("par.set", {"node": "/p", "name": "tx", "value": 1.0}, 1)
        # Must be deserializable without error.
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_contains_required_keys(self) -> None:
        raw = make_request("par.set", {"node": "/p"}, 42)
        parsed = json.loads(raw)
        assert "id" in parsed
        assert "method" in parsed
        assert "params" in parsed

    def test_id_matches_argument(self) -> None:
        raw = make_request("system.ping", {}, 7)
        parsed = json.loads(raw)
        assert parsed["id"] == 7

    def test_method_matches_argument(self) -> None:
        raw = make_request("node.create", {}, 1)
        parsed = json.loads(raw)
        assert parsed["method"] == "node.create"

    def test_params_matches_argument(self) -> None:
        params = {"path": "/project1/noise1", "values": {"tx": 1.5}}
        raw = make_request("par.set", params, 1)
        parsed = json.loads(raw)
        assert parsed["params"] == params

    def test_empty_params_serialized(self) -> None:
        raw = make_request("system.ping", {}, 1)
        parsed = json.loads(raw)
        assert parsed["params"] == {}

    def test_numeric_param_types_preserved(self) -> None:
        raw = make_request("par.set", {"value": 3.14}, 1)
        parsed = json.loads(raw)
        assert isinstance(parsed["params"]["value"], float)

    def test_different_ids_produce_different_json(self) -> None:
        raw1 = make_request("m", {}, 1)
        raw2 = make_request("m", {}, 2)
        assert raw1 != raw2


# ---------------------------------------------------------------------------
# make_batch
# ---------------------------------------------------------------------------


class TestMakeBatch:
    """Tests for :func:`make_batch`."""

    def test_returns_json_array_string(self) -> None:
        raw = make_batch([])
        parsed = json.loads(raw)
        assert isinstance(parsed, list)

    def test_empty_list_produces_empty_array(self) -> None:
        raw = make_batch([])
        assert json.loads(raw) == []

    def test_single_request_preserved(self) -> None:
        req = {"id": 1, "method": "system.ping", "params": {}}
        raw = make_batch([req])
        parsed = json.loads(raw)
        assert len(parsed) == 1
        assert parsed[0] == req

    def test_multiple_requests_all_present(self) -> None:
        reqs = [
            {"id": 1, "method": "par.set", "params": {"path": "/p", "values": {"tx": 0}}},
            {"id": 2, "method": "par.set", "params": {"path": "/p", "values": {"ty": 1}}},
        ]
        raw = make_batch(reqs)
        parsed = json.loads(raw)
        assert len(parsed) == 2

    def test_order_preserved(self) -> None:
        reqs = [
            {"id": 10, "method": "a", "params": {}},
            {"id": 20, "method": "b", "params": {}},
            {"id": 30, "method": "c", "params": {}},
        ]
        parsed = json.loads(make_batch(reqs))
        assert [r["id"] for r in parsed] == [10, 20, 30]

    def test_nested_params_roundtrip(self) -> None:
        inner = {"values": {"roughness": 0.7, "active": True}}
        req = {"id": 1, "method": "par.set", "params": inner}
        parsed = json.loads(make_batch([req]))
        assert parsed[0]["params"] == inner


# ---------------------------------------------------------------------------
# parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    """Tests for :func:`parse_response`."""

    def test_single_success_response(self) -> None:
        raw = '{"id": 1, "ok": true, "result": {"pong": true}}'
        result = parse_response(raw)
        assert isinstance(result, dict)
        assert result["id"] == 1
        assert result["ok"] is True
        assert result["result"] == {"pong": True}

    def test_batch_response_returns_list(self) -> None:
        raw = json.dumps([
            {"id": 1, "ok": True, "result": {"pong": True}},
            {"id": 2, "ok": True, "result": {"path": "/project1/noise1"}},
        ])
        result = parse_response(raw)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_batch_response_ids_correct(self) -> None:
        raw = json.dumps([
            {"id": 5, "ok": True, "result": {}},
            {"id": 6, "ok": True, "result": {}},
        ])
        result = parse_response(raw)
        assert isinstance(result, list)
        assert result[0]["id"] == 5
        assert result[1]["id"] == 6

    def test_error_response_parsed(self) -> None:
        raw = json.dumps({
            "id": 1,
            "ok": False,
            "error": {"code": -32601, "message": "Method not found: 'unknown'"},
        })
        result = parse_response(raw)
        assert isinstance(result, dict)
        assert result["ok"] is False
        assert "error" in result

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(Exception):  # json.JSONDecodeError
            parse_response("not valid json {{{")

    def test_missing_ok_key_allowed(self) -> None:
        """parse_response does not enforce schema; missing 'ok' is fine."""
        raw = '{"id": 99, "result": "anything"}'
        result = parse_response(raw)
        assert isinstance(result, dict)
        assert result["id"] == 99


# ---------------------------------------------------------------------------
# is_error
# ---------------------------------------------------------------------------


class TestIsError:
    """Tests for :func:`is_error`."""

    def test_false_when_ok_true(self) -> None:
        assert is_error({"id": 1, "ok": True, "result": {}}) is False

    def test_true_when_ok_false(self) -> None:
        assert is_error({"id": 1, "ok": False, "error": {"code": -1}}) is True

    def test_false_when_ok_key_absent(self) -> None:
        """A missing 'ok' key is treated as success, not an error."""
        assert is_error({"id": 1, "result": {}}) is False

    def test_false_when_ok_none(self) -> None:
        """Explicit None is not the same as False — treated as non-error."""
        assert is_error({"ok": None}) is False

    def test_true_requires_exactly_false(self) -> None:
        """Truthy-but-not-True values should not be treated as errors."""
        assert is_error({"ok": 0}) is False
        assert is_error({"ok": ""}) is False

    def test_empty_response_is_not_error(self) -> None:
        assert is_error({}) is False
