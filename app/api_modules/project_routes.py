from flask import g, jsonify
from sqlalchemy import func, select

from app.api import api_bp
from app.api_modules.common import get_request_json, json_error, parse_decimal, parse_iso_date
from app.api_modules.serializers import account_to_dict, budget_to_dict, fiscal_year_to_dict, membership_to_dict, project_to_dict
from app.api_modules.services import (
    get_active_company_membership,
    get_account_for_project,
    get_fiscal_year_for_project,
    get_project_and_membership,
    get_project_readiness,
    require_owner_membership,
)
from app.auth import require_api_session
from app.authorization import require_company_permission
from app.models import Account, AccountType, Budget, BudgetLine, CompanyMembership, FiscalYear, Project, ProjectMembership, StatementType, User


def resolve_active_company(db_session):
    company_id = g.current_session.active_company_id
    if company_id:
        membership = get_active_company_membership(db_session, g.current_user.id, company_id)
        if membership is not None:
            return company_id, membership
    membership = db_session.scalar(
        select(CompanyMembership)
        .where(
            CompanyMembership.user_id == g.current_user.id,
            CompanyMembership.is_active.is_(True),
        )
        .order_by(CompanyMembership.id)
    )
    if membership is None:
        return None, None
    g.current_session.active_company_id = membership.company_id
    db_session.flush()
    return membership.company_id, membership


def ensure_project_manage_permission(db_session, project):
    _, permission_error = require_company_permission(
        db_session,
        g.current_user.id,
        project.company_id,
        "project.manage",
    )
    if permission_error is not None:
        return json_error(permission_error, 403)
    return None


@api_bp.get("/projects")
@require_api_session
def list_projects():
    db_session = g.db_session
    company_id, company_membership = resolve_active_company(db_session)
    if company_id is None or company_membership is None:
        return jsonify({"items": []})
    memberships = db_session.scalars(
        select(ProjectMembership)
        .join(ProjectMembership.project)
        .where(ProjectMembership.user_id == g.current_user.id, Project.company_id == company_id)
    ).all()
    items = [project_to_dict(membership.project, readiness=get_project_readiness(db_session, membership.project.id)) for membership in memberships]
    return jsonify({"items": items})


@api_bp.post("/projects")
@require_api_session
def create_project():
    db_session = g.db_session
    active_company_id = g.current_session.active_company_id
    if not active_company_id:
        return json_error("active_company_required", 409)
    company_membership, permission_error = require_company_permission(
        db_session,
        g.current_user.id,
        active_company_id,
        "project.manage",
    )
    if permission_error is not None:
        return json_error(permission_error, 403)
    try:
        payload = get_request_json()
    except ValueError as exc:
        return json_error(str(exc))
    code = (payload.get("code") or "").strip().upper()
    name_ar = (payload.get("name_ar") or "").strip()
    name_en = (payload.get("name_en") or "").strip()
    currency_code = (payload.get("currency_code") or "").strip().upper()
    fiscal_year_payload = payload.get("fiscal_year") or {}
    missing = [field for field, value in {"code": code, "name_ar": name_ar, "name_en": name_en, "currency_code": currency_code}.items() if not value]
    if missing:
        return json_error("missing_required_fields", details=missing)
    if db_session.scalar(select(Project).where(Project.code == code)) is not None:
        return json_error("project_code_already_exists", 409)
    project = Project(
        company_id=active_company_id,
        code=code,
        name_ar=name_ar,
        name_en=name_en,
        currency_code=currency_code,
    )
    db_session.add(project)
    db_session.flush()
    db_session.add(ProjectMembership(user_id=g.current_user.id, project_id=project.id, role="owner"))
    fiscal_year = None
    if fiscal_year_payload:
        try:
            fiscal_year = FiscalYear(
                project_id=project.id,
                code=(fiscal_year_payload.get("code") or "").strip(),
                name=(fiscal_year_payload.get("name") or "").strip(),
                start_date=parse_iso_date(fiscal_year_payload.get("start_date"), "start_date"),
                end_date=parse_iso_date(fiscal_year_payload.get("end_date"), "end_date"),
            )
        except Exception:
            return json_error("invalid_fiscal_year_payload")
        db_session.add(fiscal_year)
    db_session.commit()
    response = {"project": project_to_dict(project, readiness=get_project_readiness(db_session, project.id))}
    if fiscal_year is not None:
        response["fiscal_year"] = fiscal_year_to_dict(fiscal_year)
    return jsonify(response), 201


@api_bp.get("/projects/<int:project_id>")
@require_api_session
def get_project(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    return jsonify({"project": project_to_dict(project, readiness=get_project_readiness(db_session, project.id))})


@api_bp.get("/projects/<int:project_id>/memberships")
@require_api_session
def list_project_memberships(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    memberships = db_session.scalars(select(ProjectMembership).where(ProjectMembership.project_id == project.id).order_by(ProjectMembership.id)).all()
    return jsonify({"items": [membership_to_dict(item) for item in memberships]})


@api_bp.post("/projects/<int:project_id>/memberships")
@require_api_session
def create_project_membership(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    if not require_owner_membership(membership):
        return json_error("owner_role_required", 403)
    permission_error = ensure_project_manage_permission(db_session, project)
    if permission_error is not None:
        return permission_error
    try:
        payload = get_request_json()
    except ValueError as exc:
        return json_error(str(exc))
    user_id = payload.get("user_id")
    role = (payload.get("role") or "member").strip().lower() or "member"
    if not isinstance(user_id, int):
        return json_error("user_id_required")
    user = db_session.get(User, user_id)
    if user is None:
        return json_error("invalid_user")
    company_membership = db_session.scalar(
        select(CompanyMembership).where(
            CompanyMembership.user_id == user.id,
            CompanyMembership.company_id == project.company_id,
            CompanyMembership.is_active.is_(True),
        )
    )
    if company_membership is None:
        return json_error("user_not_in_company", 409)
    existing = db_session.scalar(select(ProjectMembership).where(ProjectMembership.project_id == project.id, ProjectMembership.user_id == user.id))
    if existing is not None:
        existing.role = role
        db_session.commit()
        db_session.refresh(existing)
        return jsonify({"item": membership_to_dict(existing)})
    new_membership = ProjectMembership(user_id=user.id, project_id=project.id, role=role)
    db_session.add(new_membership)
    db_session.commit()
    db_session.refresh(new_membership)
    return jsonify({"item": membership_to_dict(new_membership)}), 201


@api_bp.delete("/projects/<int:project_id>/memberships/<int:membership_id>")
@require_api_session
def delete_project_membership(project_id, membership_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    if not require_owner_membership(membership):
        return json_error("owner_role_required", 403)
    permission_error = ensure_project_manage_permission(db_session, project)
    if permission_error is not None:
        return permission_error
    target = db_session.scalar(select(ProjectMembership).where(ProjectMembership.project_id == project.id, ProjectMembership.id == membership_id))
    if target is None:
        return json_error("membership_not_found", 404)
    if target.user_id == g.current_user.id and target.role == "owner":
        owner_count = db_session.scalar(select(func.count(ProjectMembership.id)).where(ProjectMembership.project_id == project.id, ProjectMembership.role == "owner")) or 0
        if owner_count <= 1:
            return json_error("cannot_remove_last_owner", 409)
    db_session.delete(target)
    db_session.commit()
    return jsonify({"deleted": True})


@api_bp.get("/projects/<int:project_id>/readiness")
@require_api_session
def project_readiness(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    return jsonify({"project": project_to_dict(project), "readiness": get_project_readiness(db_session, project.id)})


@api_bp.get("/projects/<int:project_id>/dashboard")
@require_api_session
def project_dashboard(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    readiness = get_project_readiness(db_session, project.id)
    budget_total = db_session.scalar(select(func.coalesce(func.sum(BudgetLine.amount), 0)).join(Budget).where(Budget.project_id == project.id)) or 0
    return jsonify({
        "project": project_to_dict(project, readiness=readiness),
        "metrics": {
            "fiscal_year_count": readiness["counts"]["fiscal_years"],
            "account_count": readiness["counts"]["accounts"],
            "budget_count": readiness["counts"]["budgets"],
            "budget_total": float(budget_total),
        },
    })


@api_bp.get("/projects/<int:project_id>/fiscal-years")
@require_api_session
def list_fiscal_years(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    fiscal_years = db_session.scalars(select(FiscalYear).where(FiscalYear.project_id == project.id).order_by(FiscalYear.start_date)).all()
    return jsonify({"items": [fiscal_year_to_dict(item) for item in fiscal_years]})


@api_bp.post("/projects/<int:project_id>/fiscal-years")
@require_api_session
def create_fiscal_year(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    permission_error = ensure_project_manage_permission(db_session, project)
    if permission_error is not None:
        return permission_error
    try:
        payload = get_request_json()
        fiscal_year = FiscalYear(
            project_id=project.id,
            code=(payload.get("code") or "").strip(),
            name=(payload.get("name") or "").strip(),
            start_date=parse_iso_date(payload.get("start_date"), "start_date"),
            end_date=parse_iso_date(payload.get("end_date"), "end_date"),
        )
    except Exception:
        return json_error("invalid_fiscal_year_payload")
    db_session.add(fiscal_year)
    db_session.commit()
    return jsonify({"item": fiscal_year_to_dict(fiscal_year)}), 201


@api_bp.get("/projects/<int:project_id>/accounts")
@require_api_session
def list_accounts(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    accounts = db_session.scalars(select(Account).where(Account.project_id == project.id).order_by(Account.code)).all()
    return jsonify({"items": [account_to_dict(item) for item in accounts]})


@api_bp.post("/projects/<int:project_id>/accounts")
@require_api_session
def create_account(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    permission_error = ensure_project_manage_permission(db_session, project)
    if permission_error is not None:
        return permission_error
    try:
        payload = get_request_json()
    except ValueError as exc:
        return json_error(str(exc))
    account_type_code = (payload.get("account_type") or "").strip().lower()
    statement_type_code = (payload.get("statement_type") or "").strip().lower()
    account_type = db_session.scalar(select(AccountType).where(AccountType.code == account_type_code))
    statement_type = db_session.scalar(select(StatementType).where(StatementType.code == statement_type_code))
    if account_type is None or statement_type is None:
        return json_error("invalid_account_lookup")
    account = Account(
        project_id=project.id,
        parent_id=payload.get("parent_id"),
        account_type_id=account_type.id,
        statement_type_id=statement_type.id,
        code=(payload.get("code") or "").strip(),
        name_ar=(payload.get("name_ar") or "").strip(),
        name_en=(payload.get("name_en") or "").strip(),
        allows_posting=bool(payload.get("allows_posting", True)),
    )
    if not account.code or not account.name_ar or not account.name_en:
        return json_error("missing_required_fields", details=["code", "name_ar", "name_en"])
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return jsonify({"item": account_to_dict(account)}), 201


@api_bp.get("/projects/<int:project_id>/budgets")
@require_api_session
def list_budgets(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    budgets = db_session.scalars(select(Budget).where(Budget.project_id == project.id)).all()
    return jsonify({"items": [budget_to_dict(item) for item in budgets]})


@api_bp.post("/projects/<int:project_id>/budgets")
@require_api_session
def create_budget(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    permission_error = ensure_project_manage_permission(db_session, project)
    if permission_error is not None:
        return permission_error
    try:
        payload = get_request_json()
    except ValueError as exc:
        return json_error(str(exc))
    fiscal_year = get_fiscal_year_for_project(db_session, project.id, payload.get("fiscal_year_id"))
    if fiscal_year is None:
        return json_error("invalid_fiscal_year")
    budget = Budget(project_id=project.id, fiscal_year_id=fiscal_year.id, name=(payload.get("name") or "").strip(), created_by_user_id=g.current_user.id)
    if not budget.name:
        return json_error("missing_required_fields", details=["name"])
    db_session.add(budget)
    db_session.flush()
    for line_payload in payload.get("lines") or []:
        account = get_account_for_project(db_session, project.id, line_payload.get("account_id"))
        if account is None:
            return json_error("invalid_budget_account")
        db_session.add(
            BudgetLine(
                budget_id=budget.id,
                account_id=account.id,
                cost_center_id=line_payload.get("cost_center_id"),
                period_number=line_payload.get("period_number"),
                amount=parse_decimal(line_payload.get("amount"), "amount"),
            )
        )
    db_session.commit()
    db_session.refresh(budget)
    return jsonify({"item": budget_to_dict(budget)}), 201