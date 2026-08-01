from mountaineer.plugin import MountaineerPlugin

from mountaineer_billing.webhook import router


def create_plugin() -> MountaineerPlugin:
    return MountaineerPlugin(
        name="mountaineer-billing",
        router=router,
    )


plugin = create_plugin()
