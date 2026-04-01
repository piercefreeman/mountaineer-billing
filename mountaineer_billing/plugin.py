
from pathlib import Path

from mountaineer.client_compiler.postcss import PostCSSBundler
from mountaineer.plugin import BuildConfig, MountaineerPlugin

from mountaineer_billing.webhook import router


def create_plugin() -> MountaineerPlugin:
    return MountaineerPlugin(
        name="mountaineer-billing",
        controllers=[],
        view_root=Path(""),
        router=router,
        build_config=BuildConfig(custom_builders=[PostCSSBundler()]),
    )


plugin = create_plugin()
