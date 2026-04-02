from __future__ import annotations

from decimal import Decimal

from mountaineer_billing.webhook import _json_safe_webhook_value


def test_json_safe_webhook_value_normalizes_decimal_values() -> None:
    payload = {
        "object": "invoice",
        "amount_decimal": Decimal("29.99"),
        "nested": {"fee_decimal": Decimal("1.25")},
        "line_items": [Decimal("5.00")],
    }

    assert _json_safe_webhook_value(payload) == {
        "object": "invoice",
        "amount_decimal": "29.99",
        "nested": {"fee_decimal": "1.25"},
        "line_items": ["5.00"],
    }
