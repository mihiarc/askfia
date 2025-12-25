# Backwards compatibility shim for Render deployment
# The package was renamed from pyfia_api to askfia_api
# Re-export everything from the new package location
from askfia_api.main import app

__all__ = ["app"]
