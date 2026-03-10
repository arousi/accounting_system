from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy import text

from app.auth import make_password_hash
from app.database import SessionLocal
from app.finance import ensure_transfer_clearing_accounts, ensure_transfer_journals
from app.models import Account, AccountType, Budget, BudgetLine, Company, CompanyMembership, Currency, FiscalYear, JournalHeader, JournalLine, Project, ProjectMembership, ProjectTransfer, ProjectTransferLine, StatementType, User


def seed_reference_data():
    db_session = SessionLocal()
    try:
        upgrade_legacy_schema(db_session)
        seed_currencies(db_session)
        seed_reference_lookups(db_session)
        admin_user = seed_admin_user(db_session)
        field_manager = seed_field_manager_user(db_session)
        default_company = seed_default_company(db_session, admin_user)
        ensure_company_membership(db_session, admin_user.id, default_company.id, role="company_owner")
        main_project = seed_demo_project(db_session, admin_user)
        branch_project = seed_field_service_project(db_session, admin_user)
        seed_unconfigured_project(db_session, admin_user)
        if branch_project is not None and field_manager is not None:
            ensure_company_membership(db_session, field_manager.id, default_company.id, role="employee")
            ensure_membership(db_session, field_manager.id, branch_project.id, role="member")
        assign_projects_to_company(db_session, default_company.id)
        if main_project is not None:
            seed_demo_accounts_budgets_and_journals(db_session, admin_user, main_project)
        if branch_project is not None:
            seed_demo_accounts_budgets_and_journals(db_session, admin_user, branch_project, variant="branch")
        if main_project is not None and branch_project is not None:
            seed_demo_project_transfers(db_session, admin_user, main_project, branch_project)
        db_session.commit()
    finally:
        db_session.close()


def upgrade_legacy_schema(db_session):
    # Add missing columns for incremental schema evolution on existing SQLite files.
    table_columns = {}
    for table in ["projects", "user_sessions"]:
        rows = db_session.execute(text(f"PRAGMA table_info({table})")).all()
        table_columns[table] = {row[1] for row in rows}

    if "company_id" not in table_columns.get("projects", set()):
        db_session.execute(text("ALTER TABLE projects ADD COLUMN company_id INTEGER"))
    if "active_company_id" not in table_columns.get("user_sessions", set()):
        db_session.execute(text("ALTER TABLE user_sessions ADD COLUMN active_company_id INTEGER"))
    db_session.flush()


def seed_currencies(db_session):
    rows = [("USD", "دولار أمريكي", "US Dollar", "$"), ("EUR", "يورو", "Euro", "€"), ("SAR", "ريال سعودي", "Saudi Riyal", "ر.س"), ("LYD", "دينار ليبي", "Libyan Dinar", "LD")]
    for code, name_ar, name_en, symbol in rows:
        if db_session.scalar(select(Currency).where(Currency.code == code)) is None:
            db_session.add(Currency(code=code, name_ar=name_ar, name_en=name_en, symbol=symbol))


def seed_reference_lookups(db_session):
    account_type_rows = [("asset", "أصول", "Assets", "debit"), ("liability", "خصوم", "Liabilities", "credit"), ("equity", "حقوق ملكية", "Equity", "credit"), ("revenue", "إيرادات", "Revenue", "credit"), ("expense", "مصروفات", "Expense", "debit")]
    for code, name_ar, name_en, normal_balance in account_type_rows:
        if db_session.scalar(select(AccountType).where(AccountType.code == code)) is None:
            db_session.add(AccountType(code=code, name_ar=name_ar, name_en=name_en, normal_balance=normal_balance))
    statement_type_rows = [("balance_sheet", "الميزانية العمومية", "Balance Sheet"), ("income_statement", "قائمة الدخل", "Income Statement")]
    for code, name_ar, name_en in statement_type_rows:
        if db_session.scalar(select(StatementType).where(StatementType.code == code)) is None:
            db_session.add(StatementType(code=code, name_ar=name_ar, name_en=name_en))
    db_session.flush()


def seed_admin_user(db_session):
    admin_user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    if admin_user is None:
        admin_user = User(email="admin@example.com", full_name="System Administrator", password_hash=make_password_hash("Admin@12345"), preferred_locale="ar")
        db_session.add(admin_user)
        db_session.flush()
    return admin_user


def seed_field_manager_user(db_session):
    user = db_session.scalar(select(User).where(User.email == "field.manager@example.com"))
    if user is None:
        user = User(email="field.manager@example.com", full_name="Field Finance Manager", password_hash=make_password_hash("Manager@12345"), preferred_locale="en")
        db_session.add(user)
        db_session.flush()
    return user


def seed_demo_project(db_session, admin_user):
    return seed_ready_project(db_session, admin_user, code="MAIN", name_ar="المشروع الرئيسي", name_en="Main Project", currency_code="USD")


def seed_field_service_project(db_session, admin_user):
    return seed_ready_project(db_session, admin_user, code="FIELD-SVC", name_ar="مشروع الخدمات الميدانية", name_en="Field Services Project", currency_code="USD")


def seed_ready_project(db_session, admin_user, *, code, name_ar, name_en, currency_code):
    project = db_session.scalar(select(Project).where(Project.code == code))
    if project is None:
        project = Project(code=code, name_ar=name_ar, name_en=name_en, currency_code=currency_code)
        db_session.add(project)
        db_session.flush()
    ensure_membership(db_session, admin_user.id, project.id)
    fiscal_year = db_session.scalar(select(FiscalYear).where(FiscalYear.project_id == project.id, FiscalYear.code == str(date.today().year)))
    if fiscal_year is None:
        db_session.add(FiscalYear(project_id=project.id, code=str(date.today().year), name=f"Fiscal Year {date.today().year}", start_date=date(date.today().year, 1, 1), end_date=date(date.today().year, 12, 31)))
        db_session.flush()
    return project


def seed_unconfigured_project(db_session, admin_user):
    project = db_session.scalar(select(Project).where(Project.code == "BUILD-OPS"))
    if project is None:
        project = Project(code="BUILD-OPS", name_ar="مشروع التشغيل الجديد", name_en="New Operations Project", currency_code="SAR")
        db_session.add(project)
        db_session.flush()
    ensure_membership(db_session, admin_user.id, project.id)


def seed_default_company(db_session, admin_user):
    company = db_session.scalar(select(Company).where(Company.code == "DEFAULT"))
    if company is None:
        company = Company(
            code="DEFAULT",
            name="Default Organization",
            owner_user_id=admin_user.id,
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()
    return company


def ensure_company_membership(db_session, user_id, company_id, role="employee", department=None):
    membership = db_session.scalar(
        select(CompanyMembership).where(
            CompanyMembership.user_id == user_id,
            CompanyMembership.company_id == company_id,
        )
    )
    if membership is None:
        db_session.add(
            CompanyMembership(
                user_id=user_id,
                company_id=company_id,
                role=role,
                department=department,
                is_active=True,
            )
        )
        db_session.flush()
        return
    changed = False
    if membership.role != role:
        membership.role = role
        changed = True
    if department is not None and membership.department != department:
        membership.department = department
        changed = True
    if not membership.is_active:
        membership.is_active = True
        changed = True
    if changed:
        db_session.flush()


def assign_projects_to_company(db_session, company_id):
    projects = db_session.scalars(select(Project).where(Project.company_id.is_(None))).all()
    for project in projects:
        project.company_id = company_id
    if projects:
        db_session.flush()


def ensure_membership(db_session, user_id, project_id, role="owner"):
    membership = db_session.scalar(select(ProjectMembership).where(ProjectMembership.user_id == user_id, ProjectMembership.project_id == project_id))
    if membership is None:
        db_session.add(ProjectMembership(user_id=user_id, project_id=project_id, role=role))
        db_session.flush()
    elif membership.role != role:
        membership.role = role
        db_session.flush()


def seed_demo_accounts_budgets_and_journals(db_session, admin_user, project, variant="main"):
    fiscal_year = db_session.scalar(select(FiscalYear).where(FiscalYear.project_id == project.id).order_by(FiscalYear.start_date))
    if fiscal_year is None:
        return
    account_types = {item.code: item for item in db_session.scalars(select(AccountType)).all()}
    statement_types = {item.code: item for item in db_session.scalars(select(StatementType)).all()}
    account_rows = [("1000", "الصندوق", "Cash on Hand", "asset", "balance_sheet"), ("1100", "البنك", "Bank", "asset", "balance_sheet"), ("1200", "ذمم بين المشاريع المدينة", "Due From Projects", "asset", "balance_sheet"), ("2100", "ذمم بين المشاريع الدائنة", "Due To Projects", "liability", "balance_sheet"), ("3000", "رأس المال", "Owner Capital", "equity", "balance_sheet"), ("4000", "إيرادات الخدمات", "Service Revenue", "revenue", "income_statement"), ("5000", "مصروفات تشغيلية", "Operating Expense", "expense", "income_statement")]
    account_map = {}
    for code, name_ar, name_en, account_type_code, statement_type_code in account_rows:
        account = db_session.scalar(select(Account).where(Account.project_id == project.id, Account.code == code))
        if account is None:
            account = Account(project_id=project.id, account_type_id=account_types[account_type_code].id, statement_type_id=statement_types[statement_type_code].id, code=code, name_ar=name_ar, name_en=name_en, allows_posting=True)
            db_session.add(account)
            db_session.flush()
        account_map[code] = account
    ensure_transfer_clearing_accounts(db_session, project.id)
    budget_name = "Annual Operating Budget" if variant == "main" else "Field Delivery Budget"
    budget = db_session.scalar(select(Budget).where(Budget.project_id == project.id, Budget.fiscal_year_id == fiscal_year.id, Budget.name == budget_name))
    if budget is None:
        budget = Budget(project_id=project.id, fiscal_year_id=fiscal_year.id, name=budget_name, created_by_user_id=admin_user.id)
        db_session.add(budget)
        db_session.flush()
        lines = [BudgetLine(budget_id=budget.id, account_id=account_map["4000"].id, amount=Decimal("120000.00" if variant == "main" else "76000.00"), period_number=1), BudgetLine(budget_id=budget.id, account_id=account_map["5000"].id, amount=Decimal("45000.00" if variant == "main" else "28000.00"), period_number=1)]
        db_session.add_all(lines)
    existing_journal = db_session.scalar(select(JournalHeader).where(JournalHeader.project_id == project.id, JournalHeader.fiscal_year_id == fiscal_year.id))
    if existing_journal is not None:
        return
    journals = build_seed_journals(fiscal_year, account_map, variant)
    for journal_payload in journals:
        journal = JournalHeader(project_id=project.id, fiscal_year_id=fiscal_year.id, journal_number=journal_payload["number"], entry_date=journal_payload["date"], description=journal_payload["description"], created_by_user_id=admin_user.id)
        db_session.add(journal)
        db_session.flush()
        for index, (account_id, debit, credit, description) in enumerate(journal_payload["lines"], start=1):
            db_session.add(JournalLine(journal_id=journal.id, line_number=index, account_id=account_id, description=description, debit=debit, credit=credit))


def build_seed_journals(fiscal_year, account_map, variant):
    if variant == "main":
        return [
            {"number": 1, "date": date(fiscal_year.start_date.year, 1, 3), "description": "Initial capital funding", "lines": [(account_map["1100"].id, Decimal("80000.00"), Decimal("0.00"), "Capital deposited to bank"), (account_map["3000"].id, Decimal("0.00"), Decimal("80000.00"), "Owner contribution")]},
            {"number": 2, "date": date(fiscal_year.start_date.year, 2, 10), "description": "Service revenue receipt", "lines": [(account_map["1100"].id, Decimal("18500.00"), Decimal("0.00"), "Cash receipt from customer"), (account_map["4000"].id, Decimal("0.00"), Decimal("18500.00"), "Service revenue recognized")]},
            {"number": 3, "date": date(fiscal_year.start_date.year, 2, 18), "description": "Operational expense payment", "lines": [(account_map["5000"].id, Decimal("4200.00"), Decimal("0.00"), "Operations cost"), (account_map["1100"].id, Decimal("0.00"), Decimal("4200.00"), "Bank payment")]},
        ]
    return [
        {"number": 1, "date": date(fiscal_year.start_date.year, 1, 7), "description": "Initial branch funding", "lines": [(account_map["1100"].id, Decimal("42000.00"), Decimal("0.00"), "Opening branch cash"), (account_map["3000"].id, Decimal("0.00"), Decimal("42000.00"), "Owner allocation")]},
        {"number": 2, "date": date(fiscal_year.start_date.year, 2, 13), "description": "Field maintenance revenue", "lines": [(account_map["1000"].id, Decimal("9800.00"), Decimal("0.00"), "Cash collection"), (account_map["4000"].id, Decimal("0.00"), Decimal("9800.00"), "Revenue recognized")]},
    ]


def get_project_account_map(db_session, project_id):
    accounts = db_session.scalars(select(Account).where(Account.project_id == project_id)).all()
    return {account.code: account for account in accounts}


def seed_demo_project_transfers(db_session, admin_user, source_project, destination_project):
    source_fiscal_year = db_session.scalar(select(FiscalYear).where(FiscalYear.project_id == source_project.id).order_by(FiscalYear.start_date))
    destination_fiscal_year = db_session.scalar(select(FiscalYear).where(FiscalYear.project_id == destination_project.id).order_by(FiscalYear.start_date))
    if source_fiscal_year is None or destination_fiscal_year is None:
        return
    existing_transfer = db_session.scalar(select(ProjectTransfer).where(ProjectTransfer.source_project_id == source_project.id, ProjectTransfer.destination_project_id == destination_project.id))
    if existing_transfer is not None:
        ensure_transfer_journals(db_session, existing_transfer)
        return
    source_accounts = get_project_account_map(db_session, source_project.id)
    destination_accounts = get_project_account_map(db_session, destination_project.id)
    if "1100" not in source_accounts or "1100" not in destination_accounts:
        return
    transfer = ProjectTransfer(source_project_id=source_project.id, destination_project_id=destination_project.id, source_fiscal_year_id=source_fiscal_year.id, destination_fiscal_year_id=destination_fiscal_year.id, transfer_date=date(source_fiscal_year.start_date.year, 3, 5), description="Transfer of operating cash to field services project", created_by_user_id=admin_user.id)
    db_session.add(transfer)
    db_session.flush()
    db_session.add(ProjectTransferLine(transfer_id=transfer.id, line_number=1, source_account_id=source_accounts["1100"].id, destination_account_id=destination_accounts["1100"].id, amount=Decimal("12000.00"), description="Initial operating float for field services"))
    db_session.flush()
    ensure_transfer_journals(db_session, transfer)