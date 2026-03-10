from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow():
    return datetime.utcnow()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_locale: Mapped[str] = mapped_column(String(10), default="ar", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")
    company_memberships: Mapped[list["CompanyMembership"]] = relationship(back_populates="user")
    memberships: Mapped[list["ProjectMembership"]] = relationship(back_populates="user")


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    memberships: Mapped[list["CompanyMembership"]] = relationship(back_populates="company")
    projects: Mapped[list["Project"]] = relationship(back_populates="company")


class CompanyMembership(TimestampMixin, Base):
    __tablename__ = "company_memberships"
    __table_args__ = (UniqueConstraint("user_id", "company_id", name="uq_company_membership"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="employee", nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="company_memberships")
    company: Mapped[Company] = relationship(back_populates="memberships")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    active_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped[Company | None] = relationship(back_populates="projects")
    currency: Mapped[Currency] = relationship()
    memberships: Mapped[list["ProjectMembership"]] = relationship(back_populates="project")
    fiscal_years: Mapped[list["FiscalYear"]] = relationship(back_populates="project")
    cost_centers: Mapped[list["CostCenter"]] = relationship(back_populates="project")
    accounts: Mapped[list["Account"]] = relationship(back_populates="project")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="project")


class ProjectMembership(TimestampMixin, Base):
    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("user_id", "project_id", name="uq_project_membership"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="owner", nullable=False)

    user: Mapped[User] = relationship(back_populates="memberships")
    project: Mapped[Project] = relationship(back_populates="memberships")


class FiscalYear(TimestampMixin, Base):
    __tablename__ = "fiscal_years"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_fiscal_year_project_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped[Project] = relationship(back_populates="fiscal_years")
    journals: Mapped[list["JournalHeader"]] = relationship(back_populates="fiscal_year")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="fiscal_year")


class AccountType(Base):
    __tablename__ = "account_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    normal_balance: Mapped[str] = mapped_column(String(10), nullable=False)


class StatementType(Base):
    __tablename__ = "statement_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)


class Account(TimestampMixin, Base):
    __tablename__ = "normalized_accounts"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_project_account_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("normalized_accounts.id"), nullable=True)
    account_type_id: Mapped[int] = mapped_column(ForeignKey("account_types.id"), nullable=False)
    statement_type_id: Mapped[int] = mapped_column(ForeignKey("statement_types.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    allows_posting: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped[Project] = relationship(back_populates="accounts")
    parent: Mapped["Account | None"] = relationship(remote_side=[id])
    account_type: Mapped[AccountType] = relationship()
    statement_type: Mapped[StatementType] = relationship()


class CostCenter(TimestampMixin, Base):
    __tablename__ = "normalized_cost_centers"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_project_cost_center_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)

    project: Mapped[Project] = relationship(back_populates="cost_centers")


class Budget(TimestampMixin, Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_years.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    project: Mapped[Project] = relationship(back_populates="budgets")
    fiscal_year: Mapped[FiscalYear] = relationship(back_populates="budgets")
    lines: Mapped[list["BudgetLine"]] = relationship(back_populates="budget", cascade="all, delete-orphan")


class BudgetLine(Base):
    __tablename__ = "budget_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("normalized_accounts.id"), nullable=False)
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("normalized_cost_centers.id"), nullable=True)
    period_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    budget: Mapped[Budget] = relationship(back_populates="lines")
    account: Mapped[Account] = relationship()
    cost_center: Mapped[CostCenter | None] = relationship()


class JournalHeader(TimestampMixin, Base):
    __tablename__ = "journal_headers_v2"
    __table_args__ = (
        UniqueConstraint("project_id", "fiscal_year_id", "journal_number", name="uq_journal_project_fy_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_years.id"), nullable=False)
    journal_number: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    fiscal_year: Mapped[FiscalYear] = relationship(back_populates="journals")
    lines: Mapped[list["JournalLine"]] = relationship(back_populates="journal", cascade="all, delete-orphan")


class JournalLine(Base):
    __tablename__ = "journal_lines_v2"
    __table_args__ = (UniqueConstraint("journal_id", "line_number", name="uq_journal_line_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journal_id: Mapped[int] = mapped_column(ForeignKey("journal_headers_v2.id"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("normalized_accounts.id"), nullable=False)
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("normalized_cost_centers.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)

    journal: Mapped[JournalHeader] = relationship(back_populates="lines")
    account: Mapped[Account] = relationship()
    cost_center: Mapped[CostCenter | None] = relationship()


class ProjectTransfer(TimestampMixin, Base):
    __tablename__ = "project_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    destination_project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    source_fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_years.id"), nullable=False)
    destination_fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_years.id"), nullable=False)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    source_project: Mapped[Project] = relationship(foreign_keys=[source_project_id])
    destination_project: Mapped[Project] = relationship(foreign_keys=[destination_project_id])
    source_fiscal_year: Mapped[FiscalYear] = relationship(foreign_keys=[source_fiscal_year_id])
    destination_fiscal_year: Mapped[FiscalYear] = relationship(foreign_keys=[destination_fiscal_year_id])
    lines: Mapped[list["ProjectTransferLine"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan"
    )


class ProjectTransferLine(Base):
    __tablename__ = "project_transfer_lines"
    __table_args__ = (UniqueConstraint("transfer_id", "line_number", name="uq_transfer_line_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("project_transfers.id"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_account_id: Mapped[int] = mapped_column(ForeignKey("normalized_accounts.id"), nullable=False)
    destination_account_id: Mapped[int] = mapped_column(ForeignKey("normalized_accounts.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    transfer: Mapped[ProjectTransfer] = relationship(back_populates="lines")
    source_account: Mapped[Account] = relationship(foreign_keys=[source_account_id])
    destination_account: Mapped[Account] = relationship(foreign_keys=[destination_account_id])
