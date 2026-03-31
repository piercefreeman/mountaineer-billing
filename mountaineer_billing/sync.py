from collections import defaultdict
from typing import Literal, Sequence

import stripe
from iceaxe import DBConnection, select
from pydantic import BaseModel, field_validator

from mountaineer.logging import LOGGER

from mountaineer_billing.config import BillingConfig
from mountaineer_billing.enums import PriceBillingInterval
from mountaineer_billing.products import (
    MeteredProduct,
    Price,
    ProductBase,
)

INTERNAL_ID_KEY = "internal_id"
INTERNAL_PRODUCT_ID_KEY = "internal_product_id"
INTERNAL_PRICE_ID_KEY = "internal_price_id"
INTERNAL_FREQUENCY_KEY = "internal_frequency"


class MarketingFeature(BaseModel):
    name: str


class RemoteProduct(BaseModel):
    """
    Subset of the Stripe Product model that allows us to calculate the diff
    between the local and remote definitions.

    """

    id: str | None = None
    name: str
    metadata: dict[str, str] = {}
    marketing_features: list[MarketingFeature] = []

    model_config = {
        "frozen": True,
    }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RemoteProduct):
            return False
        self_dict = self.model_dump(exclude={"id"})
        other_dict = other.model_dump(exclude={"id"})
        return self_dict == other_dict


class RemotePrice(BaseModel):
    """
    Subset of the Stripe Price model that allows us to calculate the diff
    between the local and remote definitions.
    """

    class RecurringDefinition(BaseModel):
        interval: Literal["day", "week", "month", "year"]
        usage_type: Literal["licensed", "metered"]

    id: str | None = None

    product: str
    # If set to None, the server-side type will be set to "one_time"
    recurring: RecurringDefinition | None = None

    unit_amount: int | None
    currency: str
    metadata: dict[str, str] = {}

    model_config = {
        "frozen": True,
    }

    @field_validator("currency")
    def requires_lowercase_currency(cls, value: str) -> str:
        if value != value.lower():
            raise ValueError("Currency must be lowercase")
        return value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RemotePrice):
            return False
        self_dict = self.model_dump(exclude={"id"})
        other_dict = other.model_dump(exclude={"id"})
        return self_dict == other_dict


class SyncDiff(BaseModel):
    """
    Represents the differences between local and remote billing objects.
    """

    products_to_create: list[ProductBase] = []
    products_to_update: list[tuple[ProductBase, RemoteProduct]] = []
    prices_to_create: list[
        tuple[ProductBase, Price, str]
    ] = []  # (product, price, remote_product_id)
    prices_to_store_locally: list[tuple[ProductBase, Price, RemotePrice]] = []


class BillingSync:
    """
    Sync local definitions to the remote billing system.

    TODO: Verify there aren't remote objects that are undefined locally.
    TODO: Sync other persistent objects in case we missed the local
        webhook notification.

    """

    def __init__(self, config: BillingConfig):
        self.config = config
        self.pagination_limit = 50

    async def sync_products(
        self,
        products: Sequence[ProductBase],
        db_connection: DBConnection,
        dry_run: bool = False,
    ):
        """
        Sync products with optional dry run mode and user confirmation.

        :param products: Local products to sync
        :param db_connection: Database connection
        :param dry_run: If True, only calculate and log differences without making changes
        """
        LOGGER.info("Starting billing sync process...")

        # Calculate the diff between local and remote
        sync_diff = await self.calculate_sync_diff(products, db_connection)

        # Log the differences
        self._log_sync_diff(sync_diff)

        if dry_run:
            LOGGER.info("Dry run mode - no changes will be made")
            return sync_diff

        # Ask for user confirmation before making changes
        if not await self._confirm_changes(sync_diff):
            LOGGER.info("Sync cancelled by user")
            return sync_diff

        # Apply the changes
        await self._apply_sync_changes(sync_diff, db_connection)

        LOGGER.info("Billing sync completed successfully")
        return sync_diff

    async def calculate_sync_diff(
        self,
        products: Sequence[ProductBase],
        db_connection: DBConnection,
    ) -> SyncDiff:
        """
        Calculate the differences between local and remote billing objects.
        """
        LOGGER.info("Fetching remote products and prices from Stripe...")

        # Get all remote objects
        all_remote_products = self.get_remote_products()
        all_remote_prices = self.get_remote_prices()

        LOGGER.info(
            f"Found {len(all_remote_products)} remote products and {sum(len(prices) for prices in all_remote_prices.values())} remote prices"
        )

        sync_diff = SyncDiff()

        for product in products:
            LOGGER.info(f"Processing local product: {product.id}")

            existing_remote_product = all_remote_products.get(product.id)
            desired_remote_product = RemoteProduct(
                name=product.name,
                metadata={
                    INTERNAL_ID_KEY: product.id,
                },
                marketing_features=[
                    MarketingFeature(name=feature)
                    for feature in product.marketing_features
                ],
            )

            if not existing_remote_product:
                LOGGER.info(
                    f"Product {product.id} not found remotely - will be created"
                )
                sync_diff.products_to_create.append(product)
                # We'll need to create prices after creating the product
                # For now, we'll assume the product will be created and add prices to create list
                # The actual remote_product_id will be populated after creation
                for price in product.prices:
                    sync_diff.prices_to_create.append((product, price, ""))
            else:
                LOGGER.info(
                    f"Product {product.id} found remotely with ID: {existing_remote_product.id}"
                )

                if existing_remote_product != desired_remote_product:
                    LOGGER.info(
                        f"Product {product.id} differs from remote - will be updated"
                    )
                    sync_diff.products_to_update.append(
                        (product, existing_remote_product)
                    )
                else:
                    LOGGER.info(f"Product {product.id} matches remote definition")

                # Check prices for this product
                # Ensure we have a valid product ID before looking up prices
                if existing_remote_product.id is None:
                    raise ValueError(f"Remote product {product.id} has no ID")

                existing_remote_prices = all_remote_prices.get(
                    existing_remote_product.id, []
                )
                LOGGER.info(
                    f"Found {len(existing_remote_prices)} remote prices for product {product.id}"
                )

                for price in product.prices:
                    desired_remote_price = self.build_new_remote_price(
                        product, price, existing_remote_product
                    )

                    existing_remote_price = next(
                        (
                            remote_price
                            for remote_price in existing_remote_prices
                            if remote_price == desired_remote_price
                        ),
                        None,
                    )

                    if not existing_remote_price:
                        LOGGER.info(
                            f"Price {price.id} for product {product.id} not found remotely - will be created"
                        )
                        sync_diff.prices_to_create.append(
                            (product, price, existing_remote_product.id)
                        )
                    else:
                        LOGGER.info(
                            f"Price {price.id} for product {product.id} found remotely with ID: {existing_remote_price.id}"
                        )
                        # Price exists and matches - we'll store it locally if not already stored
                        sync_diff.prices_to_store_locally.append(
                            (product, price, existing_remote_price)
                        )

        return sync_diff

    def _log_sync_diff(self, sync_diff: SyncDiff) -> None:
        """
        Log a detailed summary of the sync differences.
        """
        LOGGER.info("=== SYNC SUMMARY ===")

        if sync_diff.products_to_create:
            LOGGER.info(
                f"Products to CREATE remotely ({len(sync_diff.products_to_create)}):"
            )
            for product in sync_diff.products_to_create:
                LOGGER.info(f"  - {product.id}: {product.name}")

        if sync_diff.products_to_update:
            LOGGER.info(
                f"Products to UPDATE remotely ({len(sync_diff.products_to_update)}):"
            )
            for product, remote_product in sync_diff.products_to_update:
                LOGGER.info(f"  - {product.id}: {product.name}")

        if sync_diff.prices_to_create:
            LOGGER.info(
                f"Prices to CREATE remotely ({len(sync_diff.prices_to_create)}):"
            )
            for product, price, remote_product_id in sync_diff.prices_to_create:
                LOGGER.info(
                    f"  - {product.id}.{price.id}: {price.cost} {price.currency} ({price.frequency.value})"
                )

        if sync_diff.prices_to_store_locally:
            LOGGER.info(
                f"Prices to STORE locally ({len(sync_diff.prices_to_store_locally)}):"
            )
            for product, price, remote_price in sync_diff.prices_to_store_locally:
                LOGGER.info(f"  - {product.id}.{price.id}: {remote_price.id}")

        if not any(
            [
                sync_diff.products_to_create,
                sync_diff.products_to_update,
                sync_diff.prices_to_create,
                sync_diff.prices_to_store_locally,
            ]
        ):
            LOGGER.info("No changes required - all products and prices are in sync")

        LOGGER.info("=== END SYNC SUMMARY ===")

    async def _confirm_changes(self, sync_diff: SyncDiff) -> bool:
        """
        Ask user for confirmation before making changes.
        Batch the requests to minimize user interactions.
        """
        changes_needed = []

        if sync_diff.products_to_create:
            changes_needed.append(
                f"Create {len(sync_diff.products_to_create)} products in Stripe"
            )

        if sync_diff.products_to_update:
            changes_needed.append(
                f"Update {len(sync_diff.products_to_update)} products in Stripe"
            )

        if sync_diff.prices_to_create:
            changes_needed.append(
                f"Create {len(sync_diff.prices_to_create)} prices in Stripe"
            )

        if sync_diff.prices_to_store_locally:
            changes_needed.append(
                f"Store {len(sync_diff.prices_to_store_locally)} price mappings in local database"
            )

        if not changes_needed:
            return True

        LOGGER.info("The following changes will be made:")
        for change in changes_needed:
            LOGGER.info(f"  - {change}")

        response = (
            input("\nDo you want to proceed with these changes? (y/N): ")
            .strip()
            .lower()
        )
        return response in ["y", "yes"]

    async def _apply_sync_changes(
        self,
        sync_diff: SyncDiff,
        db_connection: DBConnection,
    ) -> None:
        """
        Apply the calculated changes to Stripe and local database.
        """
        # Track created product IDs for prices that need them
        created_product_ids: dict[str, str] = {}

        # Create products
        for product in sync_diff.products_to_create:
            LOGGER.info(f"Creating product in Stripe: {product.id}")
            remote_product = self._create_remote_product(product)
            if remote_product.id:
                created_product_ids[product.id] = remote_product.id

        # Update products
        for product, existing_remote_product in sync_diff.products_to_update:
            LOGGER.info(f"Updating product in Stripe: {product.id}")
            self._update_remote_product(product, existing_remote_product)

        # Create prices
        for product, price, remote_product_id in sync_diff.prices_to_create:
            # Use the created product ID if the product was just created
            if not remote_product_id:
                remote_product_id = created_product_ids.get(product.id)
                if not remote_product_id:
                    raise ValueError(
                        f"No remote product ID found for product {product.id}"
                    )

            LOGGER.info(f"Creating price in Stripe: {product.id}.{price.id}")
            remote_price = self._create_remote_price(product, price, remote_product_id)

            # Store the price mapping locally
            await self._store_price_mapping(product, price, remote_price, db_connection)

        # Store existing price mappings locally
        for product, price, remote_price in sync_diff.prices_to_store_locally:
            LOGGER.info(
                f"Storing price mapping locally: {product.id}.{price.id} -> {remote_price.id}"
            )
            await self._store_price_mapping(product, price, remote_price, db_connection)

    def _create_remote_product(self, product: ProductBase) -> RemoteProduct:
        """Create a product in Stripe."""
        desired_remote = RemoteProduct(
            name=product.name,
            metadata={
                INTERNAL_ID_KEY: product.id,
            },
            marketing_features=[
                MarketingFeature(name=feature) for feature in product.marketing_features
            ],
        )

        created_product = stripe.Product.create(
            api_key=self.config.STRIPE_API_KEY,
            **desired_remote.model_dump(exclude_none=True),
        )

        return RemoteProduct.model_validate(created_product)

    def _update_remote_product(
        self, product: ProductBase, existing_remote_product: RemoteProduct
    ) -> None:
        """Update a product in Stripe."""
        desired_remote = RemoteProduct(
            name=product.name,
            metadata={
                INTERNAL_ID_KEY: product.id,
            },
            marketing_features=[
                MarketingFeature(name=feature) for feature in product.marketing_features
            ],
        )

        if not existing_remote_product.id:
            raise ValueError("Remote product does not have an ID")

        stripe.Product.modify(
            existing_remote_product.id,
            api_key=self.config.STRIPE_API_KEY,
            **desired_remote.model_dump(exclude_none=True),
        )

    def _create_remote_price(
        self, product: ProductBase, price: Price, remote_product_id: str
    ) -> RemotePrice:
        """Create a price in Stripe."""
        # Create a temporary remote product object for the build method
        temp_remote_product = RemoteProduct(id=remote_product_id, name="")
        desired_remote = self.build_new_remote_price(
            product, price, temp_remote_product
        )

        created_price = stripe.Price.create(
            api_key=self.config.STRIPE_API_KEY,
            **desired_remote.model_dump(exclude_none=True),
        )

        return RemotePrice.model_validate(created_price)

    async def _store_price_mapping(
        self,
        product: ProductBase,
        price: Price,
        remote_price: RemotePrice,
        db_connection: DBConnection,
    ) -> None:
        """Store a price mapping in the local database."""
        if not remote_price.id:
            raise ValueError("Remote price does not have an ID")

        # Check if this mapping already exists
        billing_product_price_class = self.config.BILLING_PRODUCT_PRICE
        existing_query = select(billing_product_price_class).where(
            billing_product_price_class.product_id == product.id,  # type: ignore
            billing_product_price_class.price_id == price.id,  # type: ignore
            billing_product_price_class.frequency == price.frequency,
        )
        existing_mappings = await db_connection.exec(existing_query)

        if existing_mappings:
            LOGGER.info(f"Price mapping already exists for {product.id}.{price.id}")
            return

        product_price = self.config.BILLING_PRODUCT_PRICE(
            product_id=product.id,
            price_id=price.id,
            frequency=price.frequency,
            stripe_price_id=remote_price.id,
        )
        await db_connection.insert([product_price])

    def get_remote_products(self) -> dict[str, RemoteProduct]:
        """
        :returns: A mapping of internal_id to the remote Stripe product
        """
        internal_id_to_existing_product: dict[str, RemoteProduct] = {}

        existing_products = stripe.Product.list(
            limit=self.pagination_limit,
            api_key=self.config.STRIPE_API_KEY,
        )

        for product in existing_products.auto_paging_iter():
            wrapped_product = RemoteProduct.model_validate(product)

            if INTERNAL_ID_KEY not in wrapped_product.metadata:
                LOGGER.warning(f"Product {wrapped_product.id} has no {INTERNAL_ID_KEY}")
                continue

            internal_id_to_existing_product[
                wrapped_product.metadata[INTERNAL_ID_KEY]
            ] = RemoteProduct.model_validate(wrapped_product)

        return internal_id_to_existing_product

    def get_remote_prices(self) -> dict[str, list[RemotePrice]]:
        """
        :returns: A mapping of remote Stripe product id to a list of prices for that product
        """
        product_to_prices: defaultdict[str, list[RemotePrice]] = defaultdict(list)

        existing_prices = stripe.Price.list(
            limit=self.pagination_limit,
            api_key=self.config.STRIPE_API_KEY,
        )

        for price in existing_prices.auto_paging_iter():
            wrapped_price = RemotePrice.model_validate(price)
            product_to_prices[wrapped_price.product].append(wrapped_price)

        return dict(product_to_prices)

    def build_new_remote_price(
        self,
        product: ProductBase,
        price: Price,
        remote_product: RemoteProduct,
    ) -> RemotePrice:
        if not remote_product.id:
            raise ValueError("Remote product does not have an ID")

        remote_recurring: RemotePrice.RecurringDefinition | None = None

        if price.frequency in {
            PriceBillingInterval.DAY,
            PriceBillingInterval.WEEK,
            PriceBillingInterval.MONTH,
            PriceBillingInterval.YEAR,
        }:
            remote_recurring = RemotePrice.RecurringDefinition(
                interval=price.frequency.value.lower(),  # type: ignore
                usage_type=(
                    "metered" if isinstance(product, MeteredProduct) else "licensed"
                ),
            )
        elif price.frequency == PriceBillingInterval.ONETIME:
            remote_recurring = None
        else:
            raise ValueError(f"Unknown billing interval: {price.frequency}")

        return RemotePrice(
            product=remote_product.id,
            recurring=remote_recurring,
            unit_amount=price.cost,
            currency=price.currency.lower(),
            metadata={
                INTERNAL_PRODUCT_ID_KEY: str(product.id),
                INTERNAL_PRICE_ID_KEY: str(price.id),
                INTERNAL_FREQUENCY_KEY: price.frequency.value,
            },
        )
