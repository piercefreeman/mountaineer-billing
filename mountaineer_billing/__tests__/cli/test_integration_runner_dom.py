from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

RUNNER_PROJECT_ROOT = Path(__file__).resolve().parents[3] / "integration-runner"
if str(RUNNER_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNNER_PROJECT_ROOT))

browser_module = importlib.import_module("integration_runner.browser")
dom_module = importlib.import_module("integration_runner.dom")

BrowserActionTimeoutError = browser_module.BrowserActionTimeoutError
_select_card_payment_method = browser_module._select_card_payment_method
_type_into_first_visible_locator = browser_module._type_into_first_visible_locator
summarize_html_document = dom_module.summarize_html_document
summarize_page_dom = dom_module.summarize_page_dom


class FakeFrame:
    def __init__(
        self,
        *,
        html_content: str,
        url: str,
        name: str = "",
    ) -> None:
        self._html_content = html_content
        self.url = url
        self.name = name

    async def content(self) -> str:
        return self._html_content


class FakePage:
    def __init__(self, frames: list[FakeFrame]) -> None:
        self.frames = frames
        self.main_frame = frames[0]


def test_summarize_html_document_includes_actionable_xpaths() -> None:
    summary = summarize_html_document(
        html_content="""
        <html>
          <body>
            <h1>Checkout</h1>
            <p>Choose your plan.</p>
            <form>
              <input type="email" name="email" placeholder="Email" />
              <button type="submit">Pay now</button>
              <a href="/terms">Terms</a>
            </form>
          </body>
        </html>
        """,
        frame_id="main",
        url="https://example.com/checkout",
    )

    assert "FRAME main url=https://example.com/checkout" in summary
    assert 'heading level=1 text="Checkout"' in summary
    assert 'input xpath="' in summary
    assert 'name="email"' in summary
    assert 'button xpath="' in summary
    assert 'text="Pay now"' in summary
    assert 'a xpath="' in summary
    assert 'href="/terms"' in summary


@pytest.mark.asyncio
async def test_summarize_page_dom_includes_iframes() -> None:
    summary = await summarize_page_dom(
        FakePage(
            [
                FakeFrame(
                    html_content="<html><body><button>Pay</button></body></html>",
                    url="https://example.com/checkout",
                ),
                FakeFrame(
                    html_content=(
                        "<html><body><input name='cardnumber' "
                        "placeholder='1234 1234 1234 1234'></body></html>"
                    ),
                    url="https://js.stripe.com/frame",
                    name="card-frame",
                ),
            ]
        )
    )

    assert "FRAME main url=https://example.com/checkout" in summary
    assert (
        'FRAME iframe[1] name="card-frame" url=https://js.stripe.com/frame' in summary
    )
    assert 'button xpath="' in summary
    assert 'input xpath="' in summary
    assert 'name="cardnumber"' in summary


@pytest.mark.asyncio
async def test_type_into_first_visible_locator_raises_timeout_error() -> None:
    with patch(
        "integration_runner.browser._find_first_visible_locator",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(BrowserActionTimeoutError, match="card number input"):
            await _type_into_first_visible_locator(
                object(),
                locator_factories=[],
                value="4242424242424242",
                description="card number",
            )


@pytest.mark.asyncio
async def test_select_card_payment_method_clicks_card_option_button() -> None:
    fake_page = SimpleNamespace(wait_for_timeout=AsyncMock())
    fake_locator = SimpleNamespace(click=AsyncMock())

    with patch(
        "integration_runner.browser._find_first_visible_locator",
        new=AsyncMock(side_effect=[None, fake_locator]),
    ) as mock_find_locator:
        await _select_card_payment_method(fake_page)

    assert mock_find_locator.await_count == 2
    fake_locator.click.assert_awaited_once_with()
    fake_page.wait_for_timeout.assert_awaited_once_with(250)
