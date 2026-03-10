from flask import g

from app.models import CompanyMembership


ROLE_PERMISSIONS = {
    "company_owner": {
        "company.manage",
        "company.users.manage",
        "project.manage",
        "project.finance.write",
        "project.finance.read",
    },
    "finance_manager": {
        "company.users.manage",
        "project.manage",
        "project.finance.write",
        "project.finance.read",
    },
    "accountant": {
        "project.finance.write",
        "project.finance.read",
    },
    "employee": {
        "project.finance.read",
    },
    "viewer": {
        "project.finance.read",
    },
}


def normalize_role(role):
    return (role or "employee").strip().lower()


def role_has_permission(role, permission):
    return permission in ROLE_PERMISSIONS.get(normalize_role(role), set())


def get_user_company_membership(db_session, user_id, company_id):
    return db_session.query(CompanyMembership).filter(
        CompanyMembership.user_id == user_id,
        CompanyMembership.company_id == company_id,
        CompanyMembership.is_active.is_(True),
    ).one_or_none()


def require_company_permission(db_session, user_id, company_id, permission):
    membership = get_user_company_membership(db_session, user_id, company_id)
    if membership is None:
        return None, "company_access_denied"
    if not role_has_permission(membership.role, permission):
        return membership, "permission_denied"
    return membership, None


def can_post_finance(company_membership, project_membership, fiscal_year):
    if company_membership is None or project_membership is None:
        return False
    if fiscal_year is not None and fiscal_year.is_closed:
        return False
    if not role_has_permission(company_membership.role, "project.finance.write"):
        return False
    project_role = (project_membership.role or "member").strip().lower()
    return project_role in {"owner", "accountant", "member"}


def set_active_company(session, company_id):
    session.active_company_id = company_id
    g.current_company_membership = None
