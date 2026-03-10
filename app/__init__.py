from flask import Flask

from app.bootstrap import seed_reference_data
from app.config import Config
from app.database import init_database, remove_session


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    init_database(app)
    app.teardown_appcontext(remove_session)

    from app.api import api_bp
    from app.web import web_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    seed_reference_data()
    return app
