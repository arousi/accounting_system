from datetime import datetime

from flask import g, jsonify, request
from sqlalchemy import select

from app.api import api_bp
from app.api_modules.common import get_request_json, json_error
from app.api_modules.serializers import company_to_dict
from app.auth import create_user_session, find_user_by_email, make_password_hash, password_matches, require_api_session
from app.authorization import set_active_company
from app.models import Company, CompanyMembership, Project, User


@api_bp.post("/auth/login")
def login():
    try:
        payload = get_request_json()
    except ValueError as exc:
        return json_error(str(exc))
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or not password:
        return json_error("email_and_password_required")
    user = find_user_by_email(email)
    if user is None or not password_matches(password, user.password_hash):
        return json_error("invalid_credentials", 401)
    membership = None
    lookup_session = None
    try:
        from app.database import SessionLocal

        lookup_session = SessionLocal()
        membership = lookup_session.scalar(
            select(CompanyMembership)
            .where(CompanyMembership.user_id == user.id, CompanyMembership.is_active.is_(True))
            .order_by(CompanyMembership.id)
        )
    finally:
        if lookup_session is not None:
            lookup_session.close()

    token, session = create_user_session(
        user,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        active_company_id=membership.company_id if membership is not None else None,
    )
    return jsonify(
        {
            "token": token,
            "session": {
                "id": session.id,
                "expires_at": session.expires_at.isoformat(),
                "active": True,
                "active_company_id": session.active_company_id,
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "preferred_locale": user.preferred_locale,
            },
        }
    )


@api_bp.post("/auth/register")
def register():
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

    from app.database import SessionLocal

    db_session = SessionLocal()
    try:
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
        db_session.commit()
        db_session.refresh(user)
    finally:
        db_session.close()

    token, session = create_user_session(
        user,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )

    return jsonify(
        {
            "token": token,
            "session": {
                "id": session.id,
                "expires_at": session.expires_at.isoformat(),
                "active": True,
                "active_company_id": session.active_company_id,
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "preferred_locale": user.preferred_locale,
            },
            "needs_onboarding": True,
        }
    ), 201


@api_bp.get("/auth/session")
@require_api_session
def session_status():
    current_session = g.current_session
    user = g.current_user
    db_session = g.db_session
    company_memberships = db_session.scalars(
        select(CompanyMembership)
        .where(CompanyMembership.user_id == user.id, CompanyMembership.is_active.is_(True))
        .order_by(CompanyMembership.id)
    ).all()
    companies = [company_to_dict(item.company, membership=item) for item in company_memberships]
    return jsonify(
        {
            "active": True,
            "session": {
                "id": current_session.id,
                "issued_at": current_session.issued_at.isoformat(),
                "expires_at": current_session.expires_at.isoformat(),
                "last_seen_at": current_session.last_seen_at.isoformat(),
                "active_company_id": current_session.active_company_id,
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "preferred_locale": user.preferred_locale,
            },
            "companies": companies,
        }
    )


@api_bp.get("/onboarding/status")
@require_api_session
def onboarding_status():
    db_session = g.db_session
    user = g.current_user
    company_memberships = db_session.scalars(
        select(CompanyMembership)
        .where(CompanyMembership.user_id == user.id, CompanyMembership.is_active.is_(True))
        .order_by(CompanyMembership.id)
    ).all()
    companies = [item.company for item in company_memberships]

    active_company_id = g.current_session.active_company_id
    if active_company_id is None and companies:
        active_company_id = companies[0].id

    has_company = len(companies) > 0
    has_project = False
    if active_company_id is not None:
        has_project = (
            db_session.scalar(
                select(Project.id).where(Project.company_id == active_company_id).limit(1)
            )
            is not None
        )

    return jsonify(
        {
            "has_company": has_company,
            "has_project": has_project,
            "active_company_id": active_company_id,
            "companies": [company_to_dict(item.company, membership=item) for item in company_memberships],
            "onboarding_complete": has_company and has_project,
        }
    )


@api_bp.post("/companies")
@require_api_session
def create_company():
    db_session = g.db_session
    try:
        payload = get_request_json()
    except ValueError as exc:
        return json_error(str(exc))

    code = (payload.get("code") or "").strip().upper()
    name = (payload.get("name") or "").strip()
    if not code or not name:
        return json_error("missing_required_fields", details=["code", "name"])
    if db_session.scalar(select(Company).where(Company.code == code)) is not None:
        return json_error("company_code_already_exists", 409)

    company = Company(code=code, name=name, owner_user_id=g.current_user.id, is_active=True)
    db_session.add(company)
    db_session.flush()
    membership = CompanyMembership(
        user_id=g.current_user.id,
        company_id=company.id,
        role="company_owner",
        department=payload.get("department") or "management",
        is_active=True,
    )
    db_session.add(membership)
    set_active_company(g.current_session, company.id)
    db_session.commit()
    db_session.refresh(company)
    db_session.refresh(membership)
    return jsonify({"item": company_to_dict(company, membership=membership)}), 201


@api_bp.get("/companies")
@require_api_session
def list_companies():
    db_session = g.db_session
    memberships = db_session.scalars(
        select(CompanyMembership)
        .where(
            CompanyMembership.user_id == g.current_user.id,
            CompanyMembership.is_active.is_(True),
        )
        .order_by(CompanyMembership.id)
    ).all()
    return jsonify({"items": [company_to_dict(item.company, membership=item) for item in memberships]})


@api_bp.post("/companies/<int:company_id>/switch")
@require_api_session
def switch_company(company_id):
    db_session = g.db_session
    membership = db_session.scalar(
        select(CompanyMembership).where(
            CompanyMembership.user_id == g.current_user.id,
            CompanyMembership.company_id == company_id,
            CompanyMembership.is_active.is_(True),
        )
    )
    if membership is None:
        return json_error("company_access_denied", 403)
    set_active_company(g.current_session, company_id)
    db_session.commit()
    return jsonify({"active_company_id": company_id})


@api_bp.post("/auth/logout")
@require_api_session
def logout():
    current_session = g.current_session
    db_session = g.db_session
    current_session.revoked_at = datetime.utcnow()
    db_session.commit()
    return jsonify({"logged_out": True})