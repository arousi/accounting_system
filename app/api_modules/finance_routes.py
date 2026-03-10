from decimal import Decimal

from flask import g, jsonify, request
from sqlalchemy import func, select

from app.api import api_bp
from app.api_modules.common import get_request_json, json_error, parse_decimal, parse_iso_date
from app.api_modules.serializers import account_to_dict, fiscal_year_to_dict, journal_to_dict, transfer_to_dict
from app.api_modules.services import (
    get_account_for_project,
    get_fiscal_year_for_project,
    get_ledger_rows,
    get_project_and_membership,
    get_transfer_rows,
    get_trial_balance_rows,
)
from app.auth import require_api_session
from app.authorization import can_post_finance, require_company_permission
from app.finance import ensure_transfer_journals
from app.models import JournalHeader, JournalLine, ProjectTransfer, ProjectTransferLine


@api_bp.get("/projects/<int:project_id>/journals")
@require_api_session
def list_journals(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    fiscal_year_id = request.args.get("fiscal_year_id", type=int)
    if not fiscal_year_id:
        return json_error("fiscal_year_id_required")
    fiscal_year = get_fiscal_year_for_project(db_session, project.id, fiscal_year_id)
    if fiscal_year is None:
        return json_error("invalid_fiscal_year")
    journals = db_session.scalars(
        select(JournalHeader)
        .where(JournalHeader.project_id == project.id, JournalHeader.fiscal_year_id == fiscal_year.id)
        .order_by(JournalHeader.entry_date.desc(), JournalHeader.journal_number.desc())
    ).all()
    return jsonify({"items": [journal_to_dict(item) for item in journals]})


@api_bp.post("/projects/<int:project_id>/journals")
@require_api_session
def create_journal(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    try:
        payload = get_request_json()
    except ValueError as exc:
        return json_error(str(exc))
    fiscal_year = get_fiscal_year_for_project(db_session, project.id, payload.get("fiscal_year_id"))
    if fiscal_year is None:
        return json_error("invalid_fiscal_year")
    company_membership, permission_error = require_company_permission(
        db_session,
        g.current_user.id,
        project.company_id,
        "project.finance.write",
    )
    if permission_error is not None or not can_post_finance(company_membership, membership, fiscal_year):
        return json_error("permission_denied", 403)
    try:
        entry_date = parse_iso_date(payload.get("entry_date"), "entry_date")
    except ValueError:
        return json_error("invalid_entry_date")
    if entry_date < fiscal_year.start_date or entry_date > fiscal_year.end_date:
        return json_error("entry_date_outside_fiscal_year")
    line_payloads = payload.get("lines") or []
    if len(line_payloads) < 2:
        return json_error("journal_requires_multiple_lines")
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    prepared_lines = []
    for index, line_payload in enumerate(line_payloads, start=1):
        account = get_account_for_project(db_session, project.id, line_payload.get("account_id"))
        if account is None:
            return json_error("invalid_journal_account")
        debit = parse_decimal(line_payload.get("debit", 0), "debit")
        credit = parse_decimal(line_payload.get("credit", 0), "credit")
        if debit < 0 or credit < 0 or (debit == 0 and credit == 0):
            return json_error("invalid_journal_amount")
        total_debit += debit
        total_credit += credit
        prepared_lines.append((index, account.id, debit, credit, line_payload.get("description")))
    if total_debit != total_credit:
        return json_error("journal_not_balanced")
    journal_number = payload.get("journal_number")
    if not journal_number:
        current_max = db_session.scalar(
            select(func.max(JournalHeader.journal_number)).where(
                JournalHeader.project_id == project.id,
                JournalHeader.fiscal_year_id == fiscal_year.id,
            )
        ) or 0
        journal_number = current_max + 1
    journal = JournalHeader(
        project_id=project.id,
        fiscal_year_id=fiscal_year.id,
        journal_number=journal_number,
        entry_date=entry_date,
        description=(payload.get("description") or "").strip() or "General journal entry",
        created_by_user_id=g.current_user.id,
    )
    db_session.add(journal)
    db_session.flush()
    for line_number, account_id, debit, credit, description in prepared_lines:
        db_session.add(
            JournalLine(
                journal_id=journal.id,
                line_number=line_number,
                account_id=account_id,
                description=description,
                debit=debit,
                credit=credit,
            )
        )
    db_session.commit()
    db_session.refresh(journal)
    return jsonify({"item": journal_to_dict(journal)}), 201


@api_bp.get("/projects/<int:project_id>/ledger")
@require_api_session
def general_ledger(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    fiscal_year_id = request.args.get("fiscal_year_id", type=int)
    account_id = request.args.get("account_id", type=int)
    if not fiscal_year_id or not account_id:
        return json_error("fiscal_year_id_and_account_id_required")
    fiscal_year = get_fiscal_year_for_project(db_session, project.id, fiscal_year_id)
    account = get_account_for_project(db_session, project.id, account_id)
    if fiscal_year is None or account is None:
        return json_error("invalid_ledger_scope")
    return jsonify({
        "account": account_to_dict(account),
        "fiscal_year": fiscal_year_to_dict(fiscal_year),
        "items": get_ledger_rows(db_session, project.id, fiscal_year.id, account.id),
    })


@api_bp.get("/projects/<int:project_id>/trial-balance")
@require_api_session
def trial_balance(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    fiscal_year_id = request.args.get("fiscal_year_id", type=int)
    if not fiscal_year_id:
        return json_error("fiscal_year_id_required")
    fiscal_year = get_fiscal_year_for_project(db_session, project.id, fiscal_year_id)
    if fiscal_year is None:
        return json_error("invalid_fiscal_year")
    rows, total_debit, total_credit = get_trial_balance_rows(db_session, project.id, fiscal_year.id)
    return jsonify({
        "fiscal_year": fiscal_year_to_dict(fiscal_year),
        "items": rows,
        "totals": {"debit": total_debit, "credit": total_credit},
    })


@api_bp.get("/projects/<int:project_id>/transfers")
@require_api_session
def list_project_transfers(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    fiscal_year_id = request.args.get("fiscal_year_id", type=int)
    if not fiscal_year_id:
        return json_error("fiscal_year_id_required")
    fiscal_year = get_fiscal_year_for_project(db_session, project.id, fiscal_year_id)
    if fiscal_year is None:
        return json_error("invalid_fiscal_year")
    return jsonify({"items": get_transfer_rows(db_session, project.id, fiscal_year.id)})


@api_bp.post("/projects/<int:project_id>/transfers")
@require_api_session
def create_project_transfer(project_id):
    db_session = g.db_session
    project, membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if membership is None or project is None:
        return json_error("project_access_denied", 403)
    try:
        payload = get_request_json()
    except ValueError as exc:
        return json_error(str(exc))
    destination_project_id = payload.get("destination_project_id")
    if not isinstance(destination_project_id, int):
        return json_error("destination_project_id_required")
    if destination_project_id == project.id:
        return json_error("destination_project_must_be_different")
    destination_project, destination_membership = get_project_and_membership(
        db_session,
        g.current_user.id,
        destination_project_id,
        active_company_id=g.current_session.active_company_id,
    )
    if destination_membership is None or destination_project is None:
        return json_error("destination_project_access_denied", 403)
    source_fiscal_year = get_fiscal_year_for_project(db_session, project.id, payload.get("source_fiscal_year_id"))
    destination_fiscal_year = get_fiscal_year_for_project(db_session, destination_project.id, payload.get("destination_fiscal_year_id"))
    if source_fiscal_year is None or destination_fiscal_year is None:
        return json_error("invalid_transfer_fiscal_year")
    company_membership, permission_error = require_company_permission(
        db_session,
        g.current_user.id,
        project.company_id,
        "project.finance.write",
    )
    if permission_error is not None or not can_post_finance(company_membership, membership, source_fiscal_year):
        return json_error("permission_denied", 403)
    try:
        transfer_date = parse_iso_date(payload.get("transfer_date"), "transfer_date")
    except ValueError:
        return json_error("invalid_transfer_date")
    line_payloads = payload.get("lines") or []
    if not line_payloads:
        return json_error("transfer_requires_lines")
    prepared_lines = []
    for index, line_payload in enumerate(line_payloads, start=1):
        source_account = get_account_for_project(db_session, project.id, line_payload.get("source_account_id"))
        destination_account = get_account_for_project(db_session, destination_project.id, line_payload.get("destination_account_id"))
        if source_account is None or destination_account is None:
            return json_error("invalid_transfer_account")
        amount = parse_decimal(line_payload.get("amount"), "amount")
        if amount <= 0:
            return json_error("invalid_transfer_amount")
        prepared_lines.append({
            "line_number": index,
            "source_account_id": source_account.id,
            "destination_account_id": destination_account.id,
            "amount": amount,
            "description": (line_payload.get("description") or "").strip() or None,
        })
    transfer = ProjectTransfer(
        source_project_id=project.id,
        destination_project_id=destination_project.id,
        source_fiscal_year_id=source_fiscal_year.id,
        destination_fiscal_year_id=destination_fiscal_year.id,
        transfer_date=transfer_date,
        description=(payload.get("description") or "").strip() or "Project transfer",
        created_by_user_id=g.current_user.id,
    )
    db_session.add(transfer)
    db_session.flush()
    for line in prepared_lines:
        db_session.add(
            ProjectTransferLine(
                transfer_id=transfer.id,
                line_number=line["line_number"],
                source_account_id=line["source_account_id"],
                destination_account_id=line["destination_account_id"],
                amount=line["amount"],
                description=line["description"],
            )
        )
    db_session.flush()
    ensure_transfer_journals(db_session, transfer)
    db_session.commit()
    db_session.refresh(transfer)
    return jsonify({"item": transfer_to_dict(transfer, current_project_id=project.id)}), 201