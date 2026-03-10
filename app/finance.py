from decimal import Decimal

from sqlalchemy import func, select

from app.models import Account, AccountType, JournalHeader, JournalLine, ProjectTransfer, StatementType


def get_or_create_project_account(
    db_session,
    *,
    project_id,
    code,
    name_ar,
    name_en,
    account_type_code,
    statement_type_code,
):
    account = db_session.scalar(select(Account).where(Account.project_id == project_id, Account.code == code))
    if account is not None:
        return account
    account_type = db_session.scalar(select(AccountType).where(AccountType.code == account_type_code))
    statement_type = db_session.scalar(select(StatementType).where(StatementType.code == statement_type_code))
    account = Account(
        project_id=project_id,
        account_type_id=account_type.id,
        statement_type_id=statement_type.id,
        code=code,
        name_ar=name_ar,
        name_en=name_en,
        allows_posting=True,
    )
    db_session.add(account)
    db_session.flush()
    return account


def ensure_transfer_clearing_accounts(db_session, project_id):
    due_from = get_or_create_project_account(
        db_session,
        project_id=project_id,
        code="1200",
        name_ar="ذمم بين المشاريع المدينة",
        name_en="Due From Projects",
        account_type_code="asset",
        statement_type_code="balance_sheet",
    )
    due_to = get_or_create_project_account(
        db_session,
        project_id=project_id,
        code="2100",
        name_ar="ذمم بين المشاريع الدائنة",
        name_en="Due To Projects",
        account_type_code="liability",
        statement_type_code="balance_sheet",
    )
    return due_from, due_to


def get_next_journal_number(db_session, project_id, fiscal_year_id):
    current_max = db_session.scalar(
        select(func.max(JournalHeader.journal_number)).where(
            JournalHeader.project_id == project_id,
            JournalHeader.fiscal_year_id == fiscal_year_id,
        )
    ) or 0
    return current_max + 1


def build_transfer_journal_descriptions(transfer_id, description):
    return (
        f"[TRANSFER:{transfer_id}:OUT] {description}",
        f"[TRANSFER:{transfer_id}:IN] {description}",
    )


def ensure_transfer_journals(db_session, transfer: ProjectTransfer):
    source_due_from, _ = ensure_transfer_clearing_accounts(db_session, transfer.source_project_id)
    _, destination_due_to = ensure_transfer_clearing_accounts(db_session, transfer.destination_project_id)
    source_description, destination_description = build_transfer_journal_descriptions(transfer.id, transfer.description)
    total_amount = sum((Decimal(line.amount) for line in transfer.lines), Decimal("0.00"))

    source_journal = db_session.scalar(
        select(JournalHeader).where(
            JournalHeader.project_id == transfer.source_project_id,
            JournalHeader.fiscal_year_id == transfer.source_fiscal_year_id,
            JournalHeader.description == source_description,
        )
    )
    if source_journal is None:
        source_journal = JournalHeader(
            project_id=transfer.source_project_id,
            fiscal_year_id=transfer.source_fiscal_year_id,
            journal_number=get_next_journal_number(db_session, transfer.source_project_id, transfer.source_fiscal_year_id),
            entry_date=transfer.transfer_date,
            description=source_description,
            created_by_user_id=transfer.created_by_user_id,
        )
        db_session.add(source_journal)
        db_session.flush()
        db_session.add(
            JournalLine(
                journal_id=source_journal.id,
                line_number=1,
                account_id=source_due_from.id,
                description=transfer.description,
                debit=total_amount,
                credit=Decimal("0.00"),
            )
        )
        for index, line in enumerate(transfer.lines, start=2):
            db_session.add(
                JournalLine(
                    journal_id=source_journal.id,
                    line_number=index,
                    account_id=line.source_account_id,
                    description=line.description or transfer.description,
                    debit=Decimal("0.00"),
                    credit=Decimal(line.amount),
                )
            )

    destination_journal = db_session.scalar(
        select(JournalHeader).where(
            JournalHeader.project_id == transfer.destination_project_id,
            JournalHeader.fiscal_year_id == transfer.destination_fiscal_year_id,
            JournalHeader.description == destination_description,
        )
    )
    if destination_journal is None:
        destination_journal = JournalHeader(
            project_id=transfer.destination_project_id,
            fiscal_year_id=transfer.destination_fiscal_year_id,
            journal_number=get_next_journal_number(db_session, transfer.destination_project_id, transfer.destination_fiscal_year_id),
            entry_date=transfer.transfer_date,
            description=destination_description,
            created_by_user_id=transfer.created_by_user_id,
        )
        db_session.add(destination_journal)
        db_session.flush()
        for index, line in enumerate(transfer.lines, start=1):
            db_session.add(
                JournalLine(
                    journal_id=destination_journal.id,
                    line_number=index,
                    account_id=line.destination_account_id,
                    description=line.description or transfer.description,
                    debit=Decimal(line.amount),
                    credit=Decimal("0.00"),
                )
            )
        db_session.add(
            JournalLine(
                journal_id=destination_journal.id,
                line_number=len(transfer.lines) + 1,
                account_id=destination_due_to.id,
                description=transfer.description,
                debit=Decimal("0.00"),
                credit=total_amount,
            )
        )