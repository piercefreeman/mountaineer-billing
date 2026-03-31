from unittest.mock import patch

import pytest
import stripe
from iceaxe import DBConnection, select

from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.sync import (
    INTERNAL_FREQUENCY_KEY,
    INTERNAL_PRICE_ID_KEY,
    INTERNAL_PRODUCT_ID_KEY,
    BillingSync,
    RemotePrice,
    RemoteProduct,
    SyncDiff,
)


@pytest.mark.parametrize(
    "product_a, product_b, expected_equality",
    [
        (
            RemoteProduct(id="1", name="product_a"),
            RemoteProduct(id=None, name="product_a"),
            True,
        ),
        (
            RemoteProduct(id="1", name="product_a"),
            RemoteProduct(id="5", name="product_a"),
            True,
        ),
        (
            RemoteProduct(id="1", name="product_a"),
            RemoteProduct(id="1", name="product_b"),
            False,
        ),
    ],
)
def test_product_equality_ignores_id(
    product_a: RemoteProduct, product_b: RemoteProduct, expected_equality: bool
):
    """
    We use equality override operators to determine whether we need
    to update an object.

    """
    assert (product_a == product_b) is expected_equality


@pytest.mark.parametrize(
    "price_a, price_b, expected_equality",
    [
        (
            RemotePrice(
                id="1",
                product="product_a",
                unit_amount=1,
                currency="usd",
            ),
            RemotePrice(
                id=None,
                product="product_a",
                unit_amount=1,
                currency="usd",
            ),
            True,
        ),
        (
            RemotePrice(
                id="1",
                product="product_a",
                unit_amount=1,
                currency="usd",
            ),
            RemotePrice(
                id="5",
                product="product_a",
                unit_amount=1,
                currency="usd",
            ),
            True,
        ),
        (
            RemotePrice(
                id="1",
                product="product_a",
                unit_amount=1,
                currency="usd",
            ),
            RemotePrice(
                id="1",
                product="product_b",
                unit_amount=1,
                currency="usd",
            ),
            False,
        ),
        (
            RemotePrice(
                id="1",
                product="product_a",
                recurring=RemotePrice.RecurringDefinition(
                    interval="day", usage_type="licensed"
                ),
                unit_amount=1,
                currency="usd",
            ),
            RemotePrice(
                id="1",
                product="product_a",
                recurring=RemotePrice.RecurringDefinition(
                    interval="day", usage_type="metered"
                ),
                unit_amount=1,
                currency="usd",
            ),
            False,
        ),
    ],
)
def test_price_equality_ignores_id(
    price_a: RemotePrice, price_b: RemotePrice, expected_equality: bool
):
    """
    We use equality override operators to determine whether we need
    to update an object.

    """
    assert (price_a == price_b) is expected_equality


@pytest.mark.asyncio
async def test_calculate_sync_diff_empty_remote(
    config: models.AppConfig,
    db_connection: DBConnection,
):
    """
    Test calculating sync diff when we have no remote stripe products.
    """
    with (
        patch("stripe.Product.list") as mock_product_list,
        patch("stripe.Price.list") as mock_price_list,
    ):
        mock_product_list.return_value.auto_paging_iter.return_value = []
        mock_price_list.return_value.auto_paging_iter.return_value = []

        syncer = BillingSync(config=config)
        sync_diff = await syncer.calculate_sync_diff(
            products=config.BILLING_PRODUCTS,
            db_connection=db_connection,
        )

    # All local products should be marked for creation
    assert len(sync_diff.products_to_create) == len(config.BILLING_PRODUCTS)
    assert len(sync_diff.products_to_update) == 0

    # All prices should be marked for creation
    total_prices = sum(len(product.prices) for product in config.BILLING_PRODUCTS)
    assert len(sync_diff.prices_to_create) == total_prices
    assert len(sync_diff.prices_to_store_locally) == 0


@pytest.mark.asyncio
async def test_calculate_sync_diff_existing_remote(
    config: models.AppConfig,
    db_connection: DBConnection,
):
    """
    Test calculating sync diff when remote products already exist.
    """
    # Mock existing remote products
    existing_products = []
    existing_prices = []

    for i, product in enumerate(config.BILLING_PRODUCTS):
        remote_product = stripe.Product.construct_from(
            {
                "id": f"product_{i + 1}",
                "name": product.name,
                "metadata": {"internal_id": product.id},
                "marketing_features": [
                    {"name": feature} for feature in product.marketing_features
                ],
            },
            key="test_stripe_key",
        )
        existing_products.append(remote_product)

        # Create matching prices for each product
        for j, price in enumerate(product.prices):
            remote_price = stripe.Price.construct_from(
                {
                    "id": f"price_{i + 1}_{j + 1}",
                    "product": f"product_{i + 1}",
                    "unit_amount": price.cost,
                    "currency": price.currency.lower(),
                    "recurring": {
                        "interval": price.frequency.value.lower(),
                        "usage_type": "licensed",
                    }
                    if price.frequency.value.lower() != "onetime"
                    else None,
                    "metadata": {
                        INTERNAL_PRODUCT_ID_KEY: str(product.id),
                        INTERNAL_PRICE_ID_KEY: str(price.id),
                        INTERNAL_FREQUENCY_KEY: price.frequency.value,
                    },
                },
                key="test_stripe_key",
            )
            existing_prices.append(remote_price)

    with (
        patch("stripe.Product.list") as mock_product_list,
        patch("stripe.Price.list") as mock_price_list,
    ):
        mock_product_list.return_value.auto_paging_iter.return_value = existing_products
        mock_price_list.return_value.auto_paging_iter.return_value = existing_prices

        syncer = BillingSync(config=config)
        sync_diff = await syncer.calculate_sync_diff(
            products=config.BILLING_PRODUCTS,
            db_connection=db_connection,
        )

    # No products should need creation or updates since they match
    assert len(sync_diff.products_to_create) == 0
    assert len(sync_diff.products_to_update) == 0

    # No prices should need creation, all should be stored locally
    assert len(sync_diff.prices_to_create) == 0
    total_prices = sum(len(product.prices) for product in config.BILLING_PRODUCTS)
    assert len(sync_diff.prices_to_store_locally) == total_prices


@pytest.mark.asyncio
async def test_sync_products_dry_run(
    config: models.AppConfig,
    db_connection: DBConnection,
):
    """
    Test that dry run mode doesn't make any changes.
    """
    with (
        patch("stripe.Product.create") as mock_product_create,
        patch("stripe.Price.create") as mock_price_create,
        patch("stripe.Product.list") as mock_product_list,
        patch("stripe.Price.list") as mock_price_list,
    ):
        mock_product_list.return_value.auto_paging_iter.return_value = []
        mock_price_list.return_value.auto_paging_iter.return_value = []

        syncer = BillingSync(config=config)
        sync_diff = await syncer.sync_products(
            products=config.BILLING_PRODUCTS,
            db_connection=db_connection,
            dry_run=True,
        )

    # Should calculate diffs but not make any API calls
    assert len(sync_diff.products_to_create) == len(config.BILLING_PRODUCTS)
    mock_product_create.assert_not_called()
    mock_price_create.assert_not_called()

    # No products should be stored in database
    product_query = select(models.ProductPrice)
    products = await db_connection.exec(product_query)
    assert len(products) == 0


@pytest.mark.asyncio
async def test_sync_products_with_confirmation(
    config: models.AppConfig,
    db_connection: DBConnection,
):
    """
    Test sync with user confirmation.
    """
    current_product_id = 0
    current_price_id = 0

    def create_product_side_effect(name: str, metadata: dict[str, str], **kwargs):
        nonlocal current_product_id
        current_product_id += 1

        return stripe.Product.construct_from(
            {
                "id": f"product_{current_product_id}",
                "name": name,
                "metadata": metadata,
            },
            key="test_stripe_key",
        )

    def create_price_side_effect(
        product: str,
        unit_amount: int,
        currency: str,
        recurring: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        **kwargs,
    ):
        nonlocal current_price_id
        current_price_id += 1

        price_obj = {
            "id": f"price_{current_price_id}",
            "product": product,
            "unit_amount": unit_amount,
            "currency": currency,
        }
        if recurring:
            price_obj["recurring"] = recurring
        if metadata:
            price_obj["metadata"] = metadata

        return stripe.Price.construct_from(
            price_obj,
            key="test_stripe_key",
        )

    with (
        patch("stripe.Product.create") as mock_product_create,
        patch("stripe.Price.create") as mock_price_create,
        patch("stripe.Product.list") as mock_product_list,
        patch("stripe.Price.list") as mock_price_list,
        patch("builtins.input") as mock_input,
    ):
        mock_product_create.side_effect = create_product_side_effect
        mock_price_create.side_effect = create_price_side_effect
        mock_product_list.return_value.auto_paging_iter.return_value = []
        mock_price_list.return_value.auto_paging_iter.return_value = []
        mock_input.return_value = "y"  # User confirms changes

        syncer = BillingSync(config=config)
        sync_diff = await syncer.sync_products(
            products=config.BILLING_PRODUCTS,
            db_connection=db_connection,
        )

    # Should have created the products and prices
    assert len(sync_diff.products_to_create) == len(config.BILLING_PRODUCTS)
    assert mock_product_create.call_count == len(config.BILLING_PRODUCTS)

    total_prices = sum(len(product.prices) for product in config.BILLING_PRODUCTS)
    assert mock_price_create.call_count == total_prices

    # We should have prices stored in the database
    product_query = select(models.ProductPrice)
    products = await db_connection.exec(product_query)
    assert len(products) == total_prices


@pytest.mark.asyncio
async def test_sync_products_user_cancels(
    config: models.AppConfig,
    db_connection: DBConnection,
):
    """
    Test that sync is cancelled when user declines.
    """
    with (
        patch("stripe.Product.create") as mock_product_create,
        patch("stripe.Price.create") as mock_price_create,
        patch("stripe.Product.list") as mock_product_list,
        patch("stripe.Price.list") as mock_price_list,
        patch("builtins.input") as mock_input,
    ):
        mock_product_list.return_value.auto_paging_iter.return_value = []
        mock_price_list.return_value.auto_paging_iter.return_value = []
        mock_input.return_value = "n"  # User declines changes

        syncer = BillingSync(config=config)
        sync_diff = await syncer.sync_products(
            products=config.BILLING_PRODUCTS,
            db_connection=db_connection,
        )

    # Should calculate diffs but not make any API calls
    assert len(sync_diff.products_to_create) == len(config.BILLING_PRODUCTS)
    mock_product_create.assert_not_called()
    mock_price_create.assert_not_called()

    # No products should be stored in database
    product_query = select(models.ProductPrice)
    products = await db_connection.exec(product_query)
    assert len(products) == 0


@pytest.mark.asyncio
async def test_store_price_mapping_avoids_duplicates(
    config: models.AppConfig,
    db_connection: DBConnection,
):
    """
    Test that price mappings aren't duplicated when they already exist.
    """
    syncer = BillingSync(config=config)

    # Create a sample product and price
    product = config.BILLING_PRODUCTS[0]
    price = product.prices[0]
    remote_price = RemotePrice(
        id="price_123",
        product="product_123",
        unit_amount=price.cost,
        currency=price.currency.lower(),
    )

    # Store the mapping once
    await syncer._store_price_mapping(product, price, remote_price, db_connection)

    # Try to store it again
    await syncer._store_price_mapping(product, price, remote_price, db_connection)

    # Should only have one entry
    product_query = select(models.ProductPrice).where(
        models.ProductPrice.product_id == product.id,
        models.ProductPrice.price_id == price.id,
    )
    products = await db_connection.exec(product_query)
    assert len(products) == 1
    assert products[0].stripe_price_id == "price_123"


@pytest.mark.asyncio
async def test_sync_diff_model():
    """
    Test that the SyncDiff model works correctly.
    """
    diff = SyncDiff()
    assert len(diff.products_to_create) == 0
    assert len(diff.products_to_update) == 0
    assert len(diff.prices_to_create) == 0
    assert len(diff.prices_to_store_locally) == 0

    # Test that we can add items - use a product from the billing config
    from mountaineer_billing.__tests__.conf_models import (
        ProductID,
    )
    from mountaineer_billing.products import LicensedProduct

    product = LicensedProduct(
        id=ProductID.SUBSCRIPTION_SILVER,
        name="Test Product",
        entitlements=[],
        prices=[],
    )
    diff.products_to_create.append(product)
    assert len(diff.products_to_create) == 1
