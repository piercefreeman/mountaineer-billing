from warnings import filterwarnings

import asyncpg
import pytest
import pytest_asyncio
from iceaxe import DBConnection
from iceaxe.mountaineer import DatabaseConfig
from iceaxe.schemas.cli import create_all

from mountaineer_auth.authorize import authorize_user

from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.config import BillingModels


async def reset_public_schema(db_connection: DBConnection) -> None:
    await db_connection.conn.execute(
        """
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
    """
    )

    await db_connection.conn.execute(
        """
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT typname FROM pg_type WHERE typtype = 'e' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')) LOOP
                EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r.typname) || ' CASCADE';
            END LOOP;
        END $$;
    """
    )


@pytest.fixture(autouse=True)
def config():
    """
    Test-time configuration. Set to auto-use the fixture so that the configuration
    is mounted and exposed to the dependency injection framework in all tests.

    """
    common_db = DatabaseConfig(
        POSTGRES_HOST="localhost",
        POSTGRES_USER="mountaineer_billing",
        POSTGRES_PASSWORD="mysecretpassword",
        POSTGRES_DB="mountaineer_billing_test_db",
        POSTGRES_PORT=5436,
    )

    return models.AppConfig(
        **common_db.model_dump(),
        API_SECRET_KEY="",
        AUTH_USER=models.User,
        AUTH_VERIFICATION_STATE=models.VerificationState,
        BILLING_MODELS=BillingModels(
            USER=models.User,
            RESOURCE_ACCESS=models.ResourceAccess,
            SUBSCRIPTION=models.Subscription,
            METERED_USAGE=models.MeteredUsage,
            PAYMENT=models.Payment,
            PRODUCT_PRICE=models.ProductPrice,
            CHECKOUT_SESSION=models.CheckoutSession,
            STRIPE_EVENT=models.StripeEvent,
            STRIPE_OBJECT=models.StripeObject,
            PROJECTION_STATE=models.BillingProjectionState,
        ),
        BILLING_PRODUCTS=models.BILLING_PRODUCTS,
        BILLING_METERED=models.BILLING_METERED,
        STRIPE_API_KEY="",
        STRIPE_WEBHOOK_SECRET="",
        # Ignore the actual defaults
        _env_file=".env.test",  # pyright: ignore
    )


@pytest_asyncio.fixture
async def db_connection(config: models.AppConfig):
    db_connection = DBConnection(
        await asyncpg.connect(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD,
            database=config.POSTGRES_DB,
        )
    )

    await reset_public_schema(db_connection)
    await create_all(db_connection)

    try:
        yield db_connection
    finally:
        await db_connection.close()


@pytest_asyncio.fixture
async def user(db_connection: DBConnection):
    # Setup the resource allocation objects to grant the user permission to access
    # a particular resource
    user = models.User(
        email="test@example.com",
        hashed_password="testing",
    )
    await db_connection.insert([user])
    return user


@pytest.fixture
def user_api(config: models.AppConfig, user: models.User):
    raw_key = authorize_user(
        user_id=user.id,
        auth_config=config,
        token_expiration_minutes=60,
    )
    return f"Bearer {raw_key}"


@pytest.fixture(autouse=True)
def ignore_warnings():
    # Fix for:
    # ResourceWarning: unclosed <socket.socket fd=19, family=30, type=1, proto=6, laddr=('::1', 55296, 0, 0), raddr=('::1', 5434, 0, 0)>
    # Sometimes caused by hanging sqlalchemy connections
    filterwarnings("ignore", category=ResourceWarning)
