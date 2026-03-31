import pytest
from fastapi import Request
from starlette.datastructures import Headers

from mountaineer_auth import AuthDependencies


@pytest.fixture
def mock_request(user_api: str):
    """
    In practice, capacity requests will come from the client side
    We need a fake request to pass the user state via API key
    """
    cookie_header = f"{AuthDependencies.access_token_cookie_key()}={user_api}"

    return Request(
        scope={
            "type": "http",
            "path": "/",
            "path_params": {},
            "query_string": "",
            "headers": Headers(
                {
                    "cookie": cookie_header,
                }
            ).raw,
        }
    )
