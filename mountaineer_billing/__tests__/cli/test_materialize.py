from __future__ import annotations

from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from click.testing import CliRunner
from iceaxe import DBConnection

from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.cli.main import stripe_sync
from mountaineer_billing.cli.materialize import StripeSyncMaterialize


@pytest.mark.asyncio
async def test_materialize_users_runs_workflow_for_all_local_users_with_customer_ids(
    config: models.AppConfig,
    db_connection: DBConnection,
    user: models.User,
) -> None:
    first_materialized_user = models.User(
        email="first-materialized@example.com",
        hashed_password="testing",
        stripe_customer_id="cus_first",
    )
    second_materialized_user = models.User(
        email="second-materialized@example.com",
        hashed_password="testing",
        stripe_customer_id="cus_second",
    )
    await db_connection.insert([first_materialized_user, second_materialized_user])

    expected_users = sorted(
        [first_materialized_user, second_materialized_user],
        key=lambda candidate: str(candidate.id),
    )

    with patch(
        "mountaineer_billing.cli.materialize.MaterializeSubscriptions.run",
        new=AsyncMock(return_value=None),
    ) as mock_materialize:
        summary = await StripeSyncMaterialize(config=config).materialize_users(
            db_connection
        )

    assert user.stripe_customer_id is None
    assert summary.users_selected == 2
    assert summary.users_enqueued == 2
    assert summary.users_materialized == 2
    assert summary.users_failed == 0
    mock_materialize.assert_has_awaits(
        [
            call(
                stripe_customer_id=materialized_user.stripe_customer_id,
                internal_user_id=materialized_user.id,
                _blocking=False,
            )
            for materialized_user in expected_users
        ],
        any_order=False,
    )


@pytest.mark.asyncio
async def test_materialize_users_continues_after_workflow_failure(
    config: models.AppConfig,
    db_connection: DBConnection,
) -> None:
    failed_user = models.User(
        email="failed-materialized@example.com",
        hashed_password="testing",
        stripe_customer_id="cus_fail",
    )
    successful_user = models.User(
        email="successful-materialized@example.com",
        hashed_password="testing",
        stripe_customer_id="cus_success",
    )
    await db_connection.insert([failed_user, successful_user])

    async def mock_run(
        *,
        stripe_customer_id: str,
        internal_user_id,
        _blocking: bool,
    ) -> None:
        if stripe_customer_id == "cus_fail":
            raise RuntimeError(f"failed for {internal_user_id}")

    with patch(
        "mountaineer_billing.cli.materialize.MaterializeSubscriptions.run",
        new=AsyncMock(side_effect=mock_run),
    ):
        summary = await StripeSyncMaterialize(config=config).materialize_users(
            db_connection
        )

    assert summary.users_selected == 2
    assert summary.users_enqueued == 1
    assert summary.users_materialized == 1
    assert summary.users_failed == 1


def test_stripe_sync_materialize_command_invokes_batch_driver(
    config: models.AppConfig,
) -> None:
    fake_db_connection = object()
    batch_driver = Mock()
    batch_driver.materialize_users = AsyncMock(return_value=None)

    async def mock_run_with_db_connection(*, config, handler):
        return await handler(fake_db_connection)

    with (
        patch(
            "mountaineer_billing.cli.main.load_sync_config",
            return_value=config,
        ) as mock_load_config,
        patch(
            "mountaineer_billing.cli.main.run_with_db_connection",
            new=AsyncMock(side_effect=mock_run_with_db_connection),
        ) as mock_run_with_db,
        patch(
            "mountaineer_billing.cli.main.StripeSyncMaterialize",
            return_value=batch_driver,
        ) as mock_batch_driver,
    ):
        result = CliRunner().invoke(
            stripe_sync,
            ["materialize", "--config", "example.config:AppConfig"],
        )

    assert result.exit_code == 0
    mock_load_config.assert_called_once_with("example.config:AppConfig")
    mock_batch_driver.assert_called_once_with(config=config)
    batch_driver.materialize_users.assert_awaited_once_with(fake_db_connection)
    mock_run_with_db.assert_awaited_once()
