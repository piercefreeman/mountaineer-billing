from collections import defaultdict
from datetime import datetime, timezone

from fastapi import Depends
from iceaxe import DBConnection, and_, or_, select
from iceaxe.mountaineer import DatabaseDependencies
from pydantic import BaseModel

from mountaineer.dependencies import CoreDependencies
from mountaineer_auth import AuthDependencies

from mountaineer_billing import models
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.products import (
    LicensedProduct,
    MeteredIDBase,
    ProductIDBase,
)


async def get_user_resources(
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    db_connection: DBConnection = Depends(DatabaseDependencies.get_db_connection),
    user: models.UserBillingMixin = Depends(AuthDependencies.require_valid_user),
):
    # Get all of the allowed resources for this user
    # We only count active resources
    resource_query = (
        select(config.BILLING_RESOURCE_ACCESS)
        .where(
            config.BILLING_RESOURCE_ACCESS.user_id == user.id,
        )
        .where(
            or_(
                (
                    config.BILLING_RESOURCE_ACCESS.ended_datetime == None  # noqa
                ),
                and_(
                    config.BILLING_RESOURCE_ACCESS.ended_datetime != None,  # noqa
                    config.BILLING_RESOURCE_ACCESS.ended_datetime  # type: ignore
                    > datetime.now(timezone.utc),
                ),
            )
        )
    )
    return await db_connection.exec(resource_query)


class CapacityAllocation(BaseModel):
    # Once a value is billed to a perpetual metered type, it is not reset
    # It is drawn down over time until it reaches zero
    perpetual: int = 0

    # Variable quota resets at the start of each billing cycle
    variable: int = 0

    @property
    def total(self):
        return self.perpetual + self.variable


def get_user_allocation_metered(
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    resources: list[models.ResourceAccess] = Depends(get_user_resources),
):
    """
    MeteredIDs can be shared across multiple resources that the user currently has
    access to, for instance the credits provided by their baseline subscription plus
    additional credits that are purchased as one-offs. This function aggregates the total
    number of meteredids that the user has access to at the present moment.

    """
    # Determine the resources that are relevant to this metered type
    # The unit of the resource effectively equates to the amount of relevant products
    product_id_units: defaultdict[ProductIDBase, float] = defaultdict(float)
    for resource in resources:
        product_id_units[resource.product_id] += resource.prorated_usage

    # Now we determine what their overall metered object allocation is
    # The only types of products with count-down allocations are LicensedProducts
    metered_allocation: defaultdict[MeteredIDBase, float] = defaultdict(float)
    for product in config.BILLING_PRODUCTS:
        if product.id not in product_id_units:
            continue
        if not isinstance(product, LicensedProduct):
            continue
        for metered in product.entitlements:
            metered_allocation[metered.asset] += (
                product_id_units[product.id] * metered.quantity
            )

    return {
        metered_id: CapacityAllocation(
            perpetual=0,
            variable=int(
                metered_allocation.get(metered_id, 0),
            ),
        )
        for metered_id in config.BILLING_METERED
    }
