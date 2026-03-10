from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime

Base = declarative_base()

class Account(Base):
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True)
    account_number = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    category = Column(String, nullable=False) # Asset, Liability, Equity, Revenue, Expense
    parent_id = Column(Integer, ForeignKey('accounts.id'), nullable=True)
    financial_statement = Column(String, nullable=False) # Balance Sheet, Income Statement
    
    parent = relationship("Account", remote_side=[id])
    entries = relationship("JournalEntry", back_populates="account")

class CostCenter(Base):
    __tablename__ = 'cost_centers'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

class JournalHeader(Base):
    __tablename__ = 'journal_headers'
    id = Column(Integer, primary_key=True)
    entry_number = Column(Integer, unique=True, nullable=False)
    date = Column(Date, default=datetime.date.today)
    description = Column(String)
    
    details = relationship("JournalEntry", back_populates="header", cascade="all, delete-orphan")

class JournalEntry(Base):
    __tablename__ = 'journal_entries'
    id = Column(Integer, primary_key=True)
    header_id = Column(Integer, ForeignKey('journal_headers.id'))
    account_id = Column(Integer, ForeignKey('accounts.id'))
    description = Column(String)
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)
    cost_center_id = Column(Integer, ForeignKey('cost_centers.id'), nullable=True)
    
    header = relationship("JournalHeader", back_populates="details")
    account = relationship("Account", back_populates="entries")
    cost_center = relationship("CostCenter")

# Database Setup
engine = create_engine('sqlite:///accounting.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
