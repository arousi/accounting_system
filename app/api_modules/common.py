from datetime import date
from decimal import Decimal, InvalidOperation

from flask import jsonify, request


def json_error(message, status=400, details=None):
    payload = {"error": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status


def get_request_json():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("invalid_json_payload")
    return payload


def parse_decimal(value, field_name):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(field_name)


def parse_iso_date(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field_name)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(field_name) from exc