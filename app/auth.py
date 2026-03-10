import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, g, jsonify, request
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import SessionLocal
from app.models import CompanyMembership, User, UserSession


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def make_password_hash(password):
    return generate_password_hash(password)


def password_matches(password, password_hash):
    return check_password_hash(password_hash, password)


def is_session_active(user_session):
    return (
        user_session.user.is_active
        and user_session.revoked_at is None
        and user_session.expires_at > datetime.utcnow()
    )


def create_user_session(user, ip_address=None, user_agent=None, active_company_id=None):
    token = secrets.token_urlsafe(48)
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=current_app.config["SESSION_DURATION_MINUTES"])

    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        issued_at=now,
        expires_at=expires_at,
        last_seen_at=now,
        active_company_id=active_company_id,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:255] or None,
    )
    db_session = SessionLocal()
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    db_session.close()
    return token, session


def authenticate_api_request():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None

    db_session = SessionLocal()
    user_session = db_session.scalar(
        select(UserSession).join(User).where(UserSession.token_hash == hash_token(token))
    )
    if not user_session:
        db_session.close()
        return None

    now = datetime.utcnow()
    active = user_session.user.is_active and user_session.revoked_at is None and user_session.expires_at > now
    if not active:
        if user_session.revoked_at is None and user_session.expires_at <= now:
            user_session.revoked_at = now
            db_session.commit()
        db_session.close()
        return None

    user_session.last_seen_at = now
    db_session.commit()
    db_session.refresh(user_session)
    g.db_session = db_session
    g.current_session = user_session
    g.current_user = user_session.user
    g.current_token = token
    g.current_company_membership = None
    if user_session.active_company_id:
        g.current_company_membership = db_session.scalar(
            select(CompanyMembership).where(
                CompanyMembership.user_id == user_session.user_id,
                CompanyMembership.company_id == user_session.active_company_id,
                CompanyMembership.is_active.is_(True),
            )
        )
    return user_session


def require_api_session(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user_session = authenticate_api_request()
        if user_session is None:
            return jsonify({"error": "active_session_required"}), 401
        return view_func(*args, **kwargs)

    return wrapped


def find_user_by_email(email):
    db_session = SessionLocal()
    try:
        return db_session.scalar(select(User).where(User.email == email.lower().strip()))
    finally:
        db_session.close()
