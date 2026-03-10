from flask import g, jsonify
from sqlalchemy import select

from app.api import api_bp
from app.api_modules.common import get_request_json, json_error
from app.api_modules.serializers import user_to_dict
from app.auth import make_password_hash, require_api_session
from app.authorization import require_company_permission
from app.models import AccountType, CompanyMembership, StatementType, User


@api_bp.get("/metadata/accounting")
@require_api_session
def get_accounting_metadata():
    db_session = g.db_session
    account_types = db_session.scalars(select(AccountType).order_by(AccountType.id)).all()
    statement_types = db_session.scalars(select(StatementType).order_by(StatementType.id)).all()
    return jsonify(
        {
            "account_types": [
                {
                    "code": item.code,
                    "name_ar": item.name_ar,
                    "name_en": item.name_en,
                    "normal_balance": item.normal_balance,
                }
                for item in account_types
            ],
            "statement_types": [
                {"code": item.code, "name_ar": item.name_ar, "name_en": item.name_en}
                for item in statement_types
            ],
        }
    )


@api_bp.get("/users")
@require_api_session
def list_users():
    db_session = g.db_session
    company_id = g.current_session.active_company_id
    if not company_id:
        return json_error("active_company_required", 409)
    _, permission_error = require_company_permission(
        db_session,
        g.current_user.id,
        company_id,
        "company.users.manage",
    )
    if permission_error is not None:
        return json_error(permission_error, 403)
    users = db_session.scalars(
        select(User)
        .join(CompanyMembership, CompanyMembership.user_id == User.id)
        .where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.is_active.is_(True),
        )
        .order_by(User.full_name, User.email)
    ).all()
    return jsonify({"items": [user_to_dict(user) for user in users]})


@api_bp.post("/users")
@require_api_session
def create_user():
    db_session = g.db_session
    company_id = g.current_session.active_company_id
    if not company_id:
        return json_error("active_company_required", 409)
    _, permission_error = require_company_permission(
        db_session,
        g.current_user.id,
        company_id,
        "company.users.manage",
    )
    if permission_error is not None:
        return json_error(permission_error, 403)
    try:
        payload = get_request_json()
    except ValueError as exc:
        return json_error(str(exc))
    email = (payload.get("email") or "").strip().lower()
    full_name = (payload.get("full_name") or "").strip()
    password = payload.get("password") or ""
    preferred_locale = (payload.get("preferred_locale") or "ar").strip().lower() or "ar"
    if not email or not full_name or not password:
        return json_error("missing_required_fields", details=["email", "full_name", "password"])
    if db_session.scalar(select(User).where(User.email == email)) is not None:
        return json_error("user_email_already_exists", 409)
    user = User(
        email=email,
        full_name=full_name,
        password_hash=make_password_hash(password),
        preferred_locale=preferred_locale,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        CompanyMembership(
            user_id=user.id,
            company_id=company_id,
            role=(payload.get("company_role") or "employee").strip().lower() or "employee",
            department=(payload.get("department") or None),
            is_active=True,
        )
    )
    db_session.commit()
    db_session.refresh(user)
    return jsonify({"item": user_to_dict(user)}), 201