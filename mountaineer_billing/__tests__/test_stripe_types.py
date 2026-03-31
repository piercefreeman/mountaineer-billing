from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from time import perf_counter

from mountaineer_billing.stripe.types import (
    VERSION_DISCRIMINATOR_FIELD,
    StripeCheckoutSessionAdapter,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "stripe_flows"
    / "subscription"
    / "4_checkout.session.completed.json"
)
WARM_ITERATIONS = 100
COLD_ROUND_TRIP_MAX_SECONDS = 3.0
WARM_DESERIALIZE_MEDIAN_MAX_SECONDS = 0.005
WARM_SERIALIZE_MEDIAN_MAX_SECONDS = 0.005


def _load_checkout_session_payload() -> tuple[str, dict]:
    raw_event = json.loads(FIXTURE_PATH.read_text())
    return raw_event["api_version"], raw_event["data"]["object"]


def test_checkout_session_round_trip_is_fast() -> None:
    api_version, payload = _load_checkout_session_payload()

    cold_started = perf_counter()
    model = StripeCheckoutSessionAdapter.validate_python(
        payload,
        api_version=api_version,
    )
    serialized = model.model_dump(mode="json")
    cold_elapsed = perf_counter() - cold_started

    deserialize_timings: list[float] = []
    serialize_timings: list[float] = []

    for _ in range(WARM_ITERATIONS):
        deserialize_started = perf_counter()
        model = StripeCheckoutSessionAdapter.validate_python(
            payload,
            api_version=api_version,
        )
        deserialize_timings.append(perf_counter() - deserialize_started)

        serialize_started = perf_counter()
        serialized = model.model_dump(mode="json")
        serialize_timings.append(perf_counter() - serialize_started)

    assert model.id == payload["id"]
    assert serialized["id"] == payload["id"]
    assert (
        serialized["customer_details"]["email"] == payload["customer_details"]["email"]
    )
    assert serialized[VERSION_DISCRIMINATOR_FIELD] == api_version
    assert cold_elapsed < COLD_ROUND_TRIP_MAX_SECONDS, (
        f"cold round trip took {cold_elapsed:.3f}s, "
        f"expected under {COLD_ROUND_TRIP_MAX_SECONDS:.3f}s"
    )
    assert median(deserialize_timings) < WARM_DESERIALIZE_MEDIAN_MAX_SECONDS, (
        "warm deserialize median took "
        f"{median(deserialize_timings):.6f}s, "
        f"expected under {WARM_DESERIALIZE_MEDIAN_MAX_SECONDS:.6f}s"
    )
    assert median(serialize_timings) < WARM_SERIALIZE_MEDIAN_MAX_SECONDS, (
        "warm serialize median took "
        f"{median(serialize_timings):.6f}s, "
        f"expected under {WARM_SERIALIZE_MEDIAN_MAX_SECONDS:.6f}s"
    )
