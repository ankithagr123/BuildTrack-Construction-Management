"""BuildTrack HTTP API package."""


def create_app(*args, **kwargs):
    """Import the application factory lazily so ``python -m api.app`` is clean."""
    from .app import create_app as factory
    return factory(*args, **kwargs)


__all__ = ["create_app"]
