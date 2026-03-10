from decimal import Decimal

from sqlalchemy import func, select

from app.models import Account, Budget, CompanyMembership, FiscalYear, JournalHeader, JournalLine, ProjectMembership, ProjectTransfer
from app.api_modules.serializers import transfer_to_dict


def get_active_company_membership(db_session, user_id, company_id):
    if not company_id:
        return None
    return db_session.scalar(
        select(CompanyMembership).where(
            CompanyMembership.user_id == user_id,
            CompanyMembership.company_id == company_id,
            CompanyMembership.is_active.is_(True),
        )
    )


def require_project_access(db_session, user_id, project_id, active_company_id=None):
    return db_session.scalar(
        select(ProjectMembership)
        .join(ProjectMembership.project)
        .where(
            ProjectMembership.user_id == user_id,
            ProjectMembership.project_id == project_id,
            *([
                ProjectMembership.project.has(company_id=active_company_id),
            ] if active_company_id else []),
        )
    )


def get_project_and_membership(db_session, user_id, project_id, active_company_id=None):
    membership = require_project_access(db_session, user_id, project_id, active_company_id=active_company_id)
    if membership is None or membership.project is None:
        return None, None
    return membership.project, membership


def require_owner_membership(membership):
    return membership is not None and membership.role == "owner"


def get_project_readiness(db_session, project_id):
    fiscal_year_count = db_session.scalar(select(func.count(FiscalYear.id)).where(FiscalYear.project_id == project_id)) or 0
    account_count = db_session.scalar(select(func.count(Account.id)).where(Account.project_id == project_id)) or 0
    budget_count = db_session.scalar(select(func.count(Budget.id)).where(Budget.project_id == project_id)) or 0
    return {
        "has_fiscal_years": fiscal_year_count > 0,
        "has_accounts": account_count > 0,
        "has_budgets": budget_count > 0,
        "ready_for_finance": fiscal_year_count > 0 and budget_count > 0,
        "counts": {
            "fiscal_years": fiscal_year_count,
            "accounts": account_count,
            "budgets": budget_count,
        },
    }


def get_fiscal_year_for_project(db_session, project_id, fiscal_year_id):
    return db_session.scalar(select(FiscalYear).where(FiscalYear.id == fiscal_year_id, FiscalYear.project_id == project_id))


def get_account_for_project(db_session, project_id, account_id):
    return db_session.scalar(select(Account).where(Account.id == account_id, Account.project_id == project_id))


def get_transfer_rows(db_session, project_id, fiscal_year_id):
    transfers = db_session.scalars(
        select(ProjectTransfer)
        .where(
            ((ProjectTransfer.source_project_id == project_id) & (ProjectTransfer.source_fiscal_year_id == fiscal_year_id))
            | ((ProjectTransfer.destination_project_id == project_id) & (ProjectTransfer.destination_fiscal_year_id == fiscal_year_id))
        )
        .order_by(ProjectTransfer.transfer_date.desc(), ProjectTransfer.id.desc())
    ).all()
    return [transfer_to_dict(item, current_project_id=project_id) for item in transfers]


def get_trial_balance_rows(db_session, project_id, fiscal_year_id):
    accounts = db_session.scalars(select(Account).where(Account.project_id == project_id).order_by(Account.code)).all()
    rows = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for account in accounts:
        debit_sum = db_session.scalar(
            select(func.coalesce(func.sum(JournalLine.debit), 0))
            .join(JournalHeader, JournalHeader.id == JournalLine.journal_id)
            .where(JournalHeader.project_id == project_id)
            .where(JournalHeader.fiscal_year_id == fiscal_year_id)
            .where(JournalLine.account_id == account.id)
        ) or Decimal("0.00")
        credit_sum = db_session.scalar(
            select(func.coalesce(func.sum(JournalLine.credit), 0))
            .join(JournalHeader, JournalHeader.id == JournalLine.journal_id)
            .where(JournalHeader.project_id == project_id)
            .where(JournalHeader.fiscal_year_id == fiscal_year_id)
            .where(JournalLine.account_id == account.id)
        ) or Decimal("0.00")
        if debit_sum == 0 and credit_sum == 0:
            continue
        total_debit += Decimal(debit_sum)
        total_credit += Decimal(credit_sum)
        rows.append(
            {
                "account_id": account.id,
                "account_code": account.code,
                "account_name_ar": account.name_ar,
                "account_name_en": account.name_en,
                "debit": float(debit_sum),
                "credit": float(credit_sum),
                "balance": float(Decimal(debit_sum) - Decimal(credit_sum)),
            }
        )
    return rows, float(total_debit), float(total_credit)


def get_ledger_rows(db_session, project_id, fiscal_year_id, account_id):
    journal_lines = db_session.scalars(
        select(JournalLine)
        .join(JournalHeader, JournalHeader.id == JournalLine.journal_id)
        .where(JournalHeader.project_id == project_id)
        .where(JournalHeader.fiscal_year_id == fiscal_year_id)
        .where(JournalLine.account_id == account_id)
        .order_by(JournalHeader.entry_date, JournalHeader.journal_number, JournalLine.line_number)
    ).all()
    balance = Decimal("0.00")
    rows = []
    for line in journal_lines:
        balance += Decimal(line.debit) - Decimal(line.credit)
        rows.append(
            {
                "entry_date": line.journal.entry_date.isoformat(),
                "journal_number": line.journal.journal_number,
                "description": line.description or line.journal.description,
                "debit": float(line.debit),
                "credit": float(line.credit),
                "balance": float(balance),
            }
        )
    return rows