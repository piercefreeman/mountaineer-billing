from fastapi.testclient import TestClient

from mountaineer import AppController

from mountaineer_billing.plugin import create_plugin


def test_plugin_boots_with_mountaineer(tmp_path) -> None:
    component = AppController(view_root=tmp_path)
    component.register(create_plugin())

    with TestClient(component.app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/external/billing/webhooks/stripe" in response.json()["paths"]
