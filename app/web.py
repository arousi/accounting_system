import json

from flask import Blueprint, current_app, make_response, render_template

from app.i18n import get_locale, get_texts, normalize_locale


web_bp = Blueprint("web", __name__)


def render_screen(template_name, page_title):
    locale = get_locale(current_app.config["DEFAULT_LOCALE"])
    response = make_response(
        render_template(
            template_name,
            locale=locale,
            texts=get_texts(locale),
            texts_json=json.dumps(get_texts(locale), ensure_ascii=False),
            page_title=page_title,
        )
    )
    response.set_cookie("locale", locale, max_age=60 * 60 * 24 * 365)
    return response


@web_bp.get("/")
def login_screen():
    return render_screen("login.html", "Login")


@web_bp.get("/register")
def register_screen():
    return render_screen("register.html", "Register")


@web_bp.get("/onboarding")
def onboarding_screen():
    return render_screen("onboarding.html", "Onboarding")


@web_bp.get("/projects")
def projects_screen():
    return render_screen("projects.html", "Projects")


@web_bp.get("/projects/<int:project_id>/config")
def project_config_screen(project_id):
    response = render_screen("project_config.html", "Project Configuration")
    response.set_cookie("selected_project_id", str(project_id), max_age=60 * 60 * 24 * 365)
    return response


@web_bp.get("/projects/<int:project_id>/workspace")
def project_workspace_screen(project_id):
    response = render_screen("project_workspace.html", "Project Workspace")
    response.set_cookie("selected_project_id", str(project_id), max_age=60 * 60 * 24 * 365)
    return response


@web_bp.post("/locale/<locale>")
def set_locale(locale):
    locale = normalize_locale(locale)
    response = make_response({"locale": locale})
    response.set_cookie("locale", locale, max_age=60 * 60 * 24 * 365)
    return response
