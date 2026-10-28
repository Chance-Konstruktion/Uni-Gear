"""Compatibility shim; install the packaged add-on from dist/uni_gear.zip."""

try:
    from uni_gear import *  # noqa: F403
    from uni_gear import bl_info
except ImportError as exc:
    raise ImportError(
        "Install dist/uni_gear.zip so the uni_gear package and pure math module are present."
    ) from exc

if __name__ == "__main__":
    register()
