def project_to_dict(project, readiness=None):
    payload = {
        "id": project.id,
        "company_id": project.company_id,
        "code": project.code,
        "name_ar": project.name_ar,
        "name_en": project.name_en,
        "currency_code": project.currency_code,
        "is_active": project.is_active,
    }
    if readiness is not None:
        payload["readiness"] = readiness
    return payload


def user_to_dict(user):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "preferred_locale": user.preferred_locale,
        "is_active": user.is_active,
    }


def membership_to_dict(membership):
    return {
        "id": membership.id,
        "role": membership.role,
        "user": user_to_dict(membership.user),
        "project_id": membership.project_id,
    }


def fiscal_year_to_dict(fiscal_year):
    return {
        "id": fiscal_year.id,
        "project_id": fiscal_year.project_id,
        "code": fiscal_year.code,
        "name": fiscal_year.name,
        "start_date": fiscal_year.start_date.isoformat(),
        "end_date": fiscal_year.end_date.isoformat(),
        "is_closed": fiscal_year.is_closed,
    }


def account_to_dict(account):
    return {
        "id": account.id,
        "project_id": account.project_id,
        "parent_id": account.parent_id,
        "code": account.code,
        "name_ar": account.name_ar,
        "name_en": account.name_en,
        "account_type": account.account_type.code,
        "statement_type": account.statement_type.code,
        "allows_posting": account.allows_posting,
    }


def budget_to_dict(budget):
    return {
        "id": budget.id,
        "project_id": budget.project_id,
        "fiscal_year_id": budget.fiscal_year_id,
        "name": budget.name,
        "lines": [
            {
                "id": line.id,
                "account_id": line.account_id,
                "cost_center_id": line.cost_center_id,
                "period_number": line.period_number,
                "amount": float(line.amount),
            }
            for line in budget.lines
        ],
    }


def journal_to_dict(journal):
    return {
        "id": journal.id,
        "project_id": journal.project_id,
        "fiscal_year_id": journal.fiscal_year_id,
        "journal_number": journal.journal_number,
        "entry_date": journal.entry_date.isoformat(),
        "description": journal.description,
        "debit_total": float(sum(line.debit for line in journal.lines)),
        "credit_total": float(sum(line.credit for line in journal.lines)),
        "lines": [
            {
                "id": line.id,
                "line_number": line.line_number,
                "account_id": line.account_id,
                "account_code": line.account.code,
                "account_name_ar": line.account.name_ar,
                "account_name_en": line.account.name_en,
                "description": line.description,
                "debit": float(line.debit),
                "credit": float(line.credit),
            }
            for line in journal.lines
        ],
    }


def transfer_to_dict(transfer, current_project_id=None):
    direction = "outgoing"
    if current_project_id is not None and transfer.destination_project_id == current_project_id:
        direction = "incoming"
    total_amount = float(sum(line.amount for line in transfer.lines))
    return {
        "id": transfer.id,
        "source_project_id": transfer.source_project_id,
        "source_project_code": transfer.source_project.code,
        "source_project_name_ar": transfer.source_project.name_ar,
        "source_project_name_en": transfer.source_project.name_en,
        "destination_project_id": transfer.destination_project_id,
        "destination_project_code": transfer.destination_project.code,
        "destination_project_name_ar": transfer.destination_project.name_ar,
        "destination_project_name_en": transfer.destination_project.name_en,
        "source_fiscal_year_id": transfer.source_fiscal_year_id,
        "destination_fiscal_year_id": transfer.destination_fiscal_year_id,
        "transfer_date": transfer.transfer_date.isoformat(),
        "description": transfer.description,
        "direction": direction,
        "total_amount": total_amount,
        "lines": [
            {
                "id": line.id,
                "line_number": line.line_number,
                "source_account_id": line.source_account_id,
                "source_account_code": line.source_account.code,
                "source_account_name_ar": line.source_account.name_ar,
                "source_account_name_en": line.source_account.name_en,
                "destination_account_id": line.destination_account_id,
                "destination_account_code": line.destination_account.code,
                "destination_account_name_ar": line.destination_account.name_ar,
                "destination_account_name_en": line.destination_account.name_en,
                "amount": float(line.amount),
                "description": line.description,
            }
            for line in transfer.lines
        ],
    }


def company_to_dict(company, membership=None):
    payload = {
        "id": company.id,
        "code": company.code,
        "name": company.name,
        "owner_user_id": company.owner_user_id,
        "is_active": company.is_active,
    }
    if membership is not None:
        payload["membership"] = {
            "id": membership.id,
            "role": membership.role,
            "department": membership.department,
            "is_active": membership.is_active,
        }
    return payload