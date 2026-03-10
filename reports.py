from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QPushButton)
from models import Session, Account, JournalEntry, JournalHeader
from sqlalchemy import func

class GeneralLedger(QWidget):
    def __init__(self):
        super().__init__()
        self.session = Session()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Filter
        filter_layout = QHBoxLayout()
        self.acc_combo = QComboBox()
        self.update_acc_combo()
        
        view_btn = QPushButton("عرض التقرير")
        view_btn.clicked.connect(self.load_ledger)
        
        filter_layout.addWidget(QLabel("اختر الحساب:"))
        filter_layout.addWidget(self.acc_combo)
        filter_layout.addWidget(view_btn)
        layout.addLayout(filter_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["التاريخ", "رقم القيد", "البيان", "مدين", "دائن", "الرصيد"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        self.setLayout(layout)

    def update_acc_combo(self):
        self.acc_combo.clear()
        accounts = self.session.query(Account).all()
        for acc in accounts:
            self.acc_combo.addItem(f"{acc.account_number} - {acc.name}", acc.id)

    def load_ledger(self):
        acc_id = self.acc_combo.currentData()
        if not acc_id: return
        
        self.table.setRowCount(0)
        entries = self.session.query(JournalEntry).join(JournalHeader).filter(JournalEntry.account_id == acc_id).order_by(JournalHeader.date).all()
        
        balance = 0.0
        for entry in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            balance += (entry.debit - entry.credit)
            
            self.table.setItem(row, 0, QTableWidgetItem(str(entry.header.date)))
            self.table.setItem(row, 1, QTableWidgetItem(str(entry.header.entry_number)))
            self.table.setItem(row, 2, QTableWidgetItem(entry.description or entry.header.description))
            self.table.setItem(row, 3, QTableWidgetItem(f"{entry.debit:,.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{entry.credit:,.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{balance:,.2f}"))

class TrialBalance(QWidget):
    def __init__(self):
        super().__init__()
        self.session = Session()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        refresh_btn = QPushButton("تحديث ميزان المراجعة")
        refresh_btn.clicked.connect(self.load_trial_balance)
        layout.addWidget(refresh_btn)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["اسم الحساب", "إجمالي مدين", "إجمالي دائن", "الرصيد"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        self.total_label = QLabel("المجاميع: مدين 0.00 | دائن 0.00")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.total_label)
        
        self.setLayout(layout)
        self.load_trial_balance()

    def load_trial_balance(self):
        self.table.setRowCount(0)
        accounts = self.session.query(Account).all()
        
        total_debit = 0.0
        total_credit = 0.0
        
        for acc in accounts:
            debit_sum = self.session.query(func.sum(JournalEntry.debit)).filter(JournalEntry.account_id == acc.id).scalar() or 0.0
            credit_sum = self.session.query(func.sum(JournalEntry.credit)).filter(JournalEntry.account_id == acc.id).scalar() or 0.0
            
            if debit_sum == 0 and credit_sum == 0: continue
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            balance = debit_sum - credit_sum
            
            self.table.setItem(row, 0, QTableWidgetItem(f"{acc.account_number} - {acc.name}"))
            self.table.setItem(row, 1, QTableWidgetItem(f"{debit_sum:,.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{credit_sum:,.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{balance:,.2f}"))
            
            total_debit += debit_sum
            total_credit += credit_sum
            
        self.total_label.setText(f"المجاميع: مدين {total_debit:,.2f} | دائن {total_credit:,.2f}")
        if abs(total_debit - total_credit) > 0.01:
            self.total_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.total_label.setStyleSheet("color: green; font-weight: bold;")
