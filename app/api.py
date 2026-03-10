from flask import Blueprint


api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


from app.api_modules import auth_routes  # noqa: F401,E402
from app.api_modules import export_routes  # noqa: F401,E402
from app.api_modules import finance_routes  # noqa: F401,E402
from app.api_modules import project_routes  # noqa: F401,E402
from app.api_modules import reference_routes  # noqa: F401,E402
