from auth.apps.api.app import app as api_app
from auth.apps.auth.app import app as auth_app
from auth.apps.dashboard.app import app as dashboard_app

__all__ = ["api_app", "auth_app", "dashboard_app"]
