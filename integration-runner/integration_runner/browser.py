from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any, Callable

from integration_runner.dom import write_page_dom_summary

try:
    from playwright.async_api import (
        TimeoutError as PlaywrightTimeoutError,
        async_playwright,
    )
except ModuleNotFoundError:
    PlaywrightTimeoutError = TimeoutError
    async_playwright = None

FIELD_POLL_ATTEMPTS = 20
FIELD_POLL_INTERVAL_SECONDS = 0.25
PAYMENT_METHOD_SETTLE_DELAY_MS = 250
POST_SUBMIT_POLL_INTERVAL_MS = 250


@dataclass(frozen=True)
class CardDetails:
    email: str
    number: str
    expiry: str
    cvc: str
    cardholder_name: str
    postal_code: str | None = None


@dataclass(frozen=True)
class BrowserRunResult:
    final_url: str
    video_path: Path | None


LocatorFactory = Callable[[Any], Any]


class BrowserActionTimeoutError(TimeoutError):
    pass


def playwright_install_instructions() -> str:
    return (
        "Playwright is not installed. Run "
        "`uv sync --project integration-runner` and "
        "`uv run --project integration-runner playwright install chromium`."
    )


def _email_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.get_by_label(re.compile(r"^email$", re.I)),
        lambda scope: scope.get_by_placeholder(re.compile(r"email", re.I)),
        lambda scope: scope.locator("input[type='email']"),
        lambda scope: scope.locator("input[name='email']"),
    ]


def _card_number_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.get_by_placeholder(re.compile(r"1234 1234 1234 1234")),
        lambda scope: scope.get_by_label(
            re.compile(r"card number|card information", re.I)
        ),
        lambda scope: scope.locator("input[name='cardnumber']"),
        lambda scope: scope.locator(
            "input[data-elements-stable-field-name='cardNumber']"
        ),
    ]


def _expiry_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.get_by_placeholder(re.compile(r"MM\\s*/\\s*YY", re.I)),
        lambda scope: scope.get_by_label(re.compile(r"expiration|expiry", re.I)),
        lambda scope: scope.locator("input[name='exp-date']"),
        lambda scope: scope.locator(
            "input[data-elements-stable-field-name='cardExpiry']"
        ),
    ]


def _cvc_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.get_by_placeholder(re.compile(r"CVC|CVV", re.I)),
        lambda scope: scope.get_by_label(re.compile(r"CVC|CVV|security code", re.I)),
        lambda scope: scope.locator("input[name='cvc']"),
        lambda scope: scope.locator("input[data-elements-stable-field-name='cardCvc']"),
    ]


def _cardholder_name_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.get_by_label(re.compile(r"name on card|full name", re.I)),
        lambda scope: scope.get_by_placeholder(
            re.compile(r"name on card|full name", re.I)
        ),
        lambda scope: scope.locator("input[autocomplete='cc-name']"),
        lambda scope: scope.locator("input[name='billingName']"),
    ]


def _postal_code_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.get_by_label(re.compile(r"zip|postal code", re.I)),
        lambda scope: scope.get_by_placeholder(re.compile(r"zip|postal code", re.I)),
        lambda scope: scope.locator("input[autocomplete='postal-code']"),
        lambda scope: scope.locator("input[name='postalCode']"),
    ]


def _card_payment_method_button_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.locator("button[data-testid='card-accordion-item-button']"),
        lambda scope: scope.get_by_role(
            "button", name=re.compile(r"pay with card", re.I)
        ),
        lambda scope: scope.locator("button[aria-label='Pay with card']"),
    ]


def _card_payment_method_radio_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.get_by_label(re.compile(r"^card$", re.I)),
        lambda scope: scope.locator("#payment-method-accordion-item-title-card"),
        lambda scope: scope.locator(
            "input[name='payment-method-accordion-item-title'][value='card']"
        ),
    ]


def _submit_button_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.get_by_role(
            "button",
            name=re.compile(r"pay|subscribe|start trial|purchase|continue", re.I),
        ),
        lambda scope: scope.locator("button[type='submit']"),
    ]


def _save_information_checkbox_locator_factories() -> list[LocatorFactory]:
    return [
        lambda scope: scope.get_by_role(
            "checkbox",
            name=re.compile(r"save my information|save information", re.I),
        ),
        lambda scope: scope.get_by_label(
            re.compile(r"save my information|save information", re.I)
        ),
    ]


async def _all_scopes(page: Any) -> list[Any]:
    return [page, *page.frames]


async def _find_first_visible_locator(
    page: Any,
    locator_factories: list[LocatorFactory],
) -> Any | None:
    for _ in range(FIELD_POLL_ATTEMPTS):
        for scope in await _all_scopes(page):
            for locator_factory in locator_factories:
                locator = locator_factory(scope)
                try:
                    if await locator.count() == 0:
                        continue
                except Exception:
                    continue

                first_match = locator.first
                try:
                    if await first_match.is_visible():
                        return first_match
                except Exception:
                    continue

        await asyncio.sleep(FIELD_POLL_INTERVAL_SECONDS)

    return None


async def _type_into_first_visible_locator(
    page: Any,
    *,
    locator_factories: list[LocatorFactory],
    value: str,
    description: str,
    optional: bool = False,
) -> None:
    locator = await _find_first_visible_locator(page, locator_factories)
    if locator is None:
        if optional:
            return
        raise BrowserActionTimeoutError(
            f"Timed out while searching for a visible {description} input in checkout"
        )

    await locator.click()
    await locator.fill("")
    await locator.press_sequentially(value, delay=60)


async def _click_first_visible_locator(
    page: Any,
    *,
    locator_factories: list[LocatorFactory],
    description: str,
) -> None:
    locator = await _find_first_visible_locator(page, locator_factories)
    if locator is None:
        raise BrowserActionTimeoutError(
            f"Timed out while searching for a visible {description} button in checkout"
        )

    await locator.click()


async def _set_checkbox_state(
    page: Any,
    *,
    locator_factories: list[LocatorFactory],
    checked: bool,
) -> None:
    locator = await _find_first_visible_locator(page, locator_factories)
    if locator is None:
        return

    try:
        is_checked = await locator.is_checked()
    except Exception:
        is_checked = None

    if is_checked is checked:
        return

    try:
        if checked:
            await locator.check(force=True)
        else:
            await locator.uncheck(force=True)
        return
    except Exception:
        pass

    await locator.click(force=True)


async def _maybe_uncheck_save_information(page: Any) -> None:
    await _set_checkbox_state(
        page,
        locator_factories=_save_information_checkbox_locator_factories(),
        checked=False,
    )


def _strip_fragment(url: str) -> str:
    return url.split("#", 1)[0]


def _is_checkout_complete(
    *,
    current_url: str,
    checkout_url: str,
    success_url: str | None,
    cancel_url: str | None,
) -> bool:
    if success_url and current_url.startswith(success_url):
        return True
    if cancel_url and current_url.startswith(cancel_url):
        return True

    return (
        _strip_fragment(current_url) != _strip_fragment(checkout_url)
        and "checkout.stripe.com" not in current_url
    )


async def _wait_for_checkout_completion(
    page: Any,
    *,
    checkout_url: str,
    success_url: str | None,
    cancel_url: str | None,
    timeout_ms: int,
) -> None:
    deadline = monotonic() + (timeout_ms / 1000)
    while monotonic() < deadline:
        if _is_checkout_complete(
            current_url=page.url,
            checkout_url=checkout_url,
            success_url=success_url,
            cancel_url=cancel_url,
        ):
            return

        await page.wait_for_timeout(POST_SUBMIT_POLL_INTERVAL_MS)

    raise BrowserActionTimeoutError(
        "Timed out waiting for Stripe Checkout to redirect after submit"
    )


async def _write_dom_timeout_artifact(
    *,
    page: Any,
    video_dir: Path,
) -> Path | None:
    try:
        return await write_page_dom_summary(
            page=page,
            output_dir=video_dir.parent / "dom",
        )
    except Exception:
        return None


async def _select_card_payment_method(page: Any) -> None:
    existing_card_field = await _find_first_visible_locator(
        page,
        _card_number_locator_factories(),
    )
    if existing_card_field is not None:
        return

    button_locator = await _find_first_visible_locator(
        page,
        _card_payment_method_button_locator_factories(),
    )
    if button_locator is not None:
        await button_locator.click(force=True)
        await page.wait_for_timeout(PAYMENT_METHOD_SETTLE_DELAY_MS)
        return

    radio_locator = await _find_first_visible_locator(
        page,
        _card_payment_method_radio_locator_factories(),
    )
    if radio_locator is None:
        return

    await radio_locator.click(force=True)
    await page.wait_for_timeout(PAYMENT_METHOD_SETTLE_DELAY_MS)


async def run_checkout_browser(
    *,
    checkout_url: str,
    card: CardDetails,
    video_dir: Path,
    success_url: str | None = None,
    cancel_url: str | None = None,
    slow_mo_ms: int = 250,
    timeout_ms: int = 30_000,
    pause_after_ms: int = 5_000,
    submit: bool = False,
    uncheck_save_information: bool = False,
) -> BrowserRunResult:
    if async_playwright is None:
        raise RuntimeError(playwright_install_instructions())

    video_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=slow_mo_ms,
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1080},
            record_video_dir=str(video_dir),
            record_video_size={"width": 1440, "height": 1080},
        )
        context.set_default_timeout(timeout_ms)
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            await page.goto(
                checkout_url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            await page.wait_for_load_state("load", timeout=timeout_ms)
            await _select_card_payment_method(page)

            await _type_into_first_visible_locator(
                page,
                locator_factories=_email_locator_factories(),
                value=card.email,
                description="email",
                optional=True,
            )
            await _type_into_first_visible_locator(
                page,
                locator_factories=_card_number_locator_factories(),
                value=card.number,
                description="card number",
            )
            await _type_into_first_visible_locator(
                page,
                locator_factories=_expiry_locator_factories(),
                value=card.expiry,
                description="expiry",
            )
            await _type_into_first_visible_locator(
                page,
                locator_factories=_cvc_locator_factories(),
                value=card.cvc,
                description="CVC",
            )
            await _type_into_first_visible_locator(
                page,
                locator_factories=_cardholder_name_locator_factories(),
                value=card.cardholder_name,
                description="cardholder name",
                optional=True,
            )
            if card.postal_code:
                await _type_into_first_visible_locator(
                    page,
                    locator_factories=_postal_code_locator_factories(),
                    value=card.postal_code,
                    description="postal code",
                    optional=True,
                )

            if uncheck_save_information:
                await _maybe_uncheck_save_information(page)

            if submit:
                await _click_first_visible_locator(
                    page,
                    locator_factories=_submit_button_locator_factories(),
                    description="submit",
                )
                await _wait_for_checkout_completion(
                    page,
                    checkout_url=checkout_url,
                    success_url=success_url,
                    cancel_url=cancel_url,
                    timeout_ms=timeout_ms,
                )
                await page.wait_for_load_state("load", timeout=timeout_ms)

            await page.wait_for_timeout(pause_after_ms)
        except (BrowserActionTimeoutError, PlaywrightTimeoutError) as exc:
            dom_summary_path = await _write_dom_timeout_artifact(
                page=page,
                video_dir=video_dir,
            )
            details = (
                f" DOM summary written to {dom_summary_path}."
                if dom_summary_path is not None
                else " Failed to capture a DOM summary artifact."
            )
            raise RuntimeError(f"{exc}{details}") from exc
        finally:
            video = page.video
            final_url = page.url
            await context.close()
            video_path = Path(await video.path()) if video is not None else None
            await browser.close()

    return BrowserRunResult(final_url=final_url, video_path=video_path)
