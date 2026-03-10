from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QDateEdit)
from PyQt6.QtCore import QDate, Qt
from models import Session, Account, JournalHeader, JournalEntry, CostCenter
import datetime

class JournalEntries(QWidget):
    def __init__(self):
        super().__init__()
        self.session = Session()
        self.init_ui()
        self.load_cost_centers()
        self.load_accounts()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Header Info
        header_layout = QHBoxLayout()
        self.date_input = QDateEdit(QDate.currentDate())
        self.entry_num_input = QLineEdit()
        self.entry_num_input.setPlaceholderText("رقم القيد")
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("وصف القيد العام")
        
        header_layout.addWidget(QLabel("التاريخ:"))
        header_layout.addWidget(self.date_input)
        header_layout.addWidget(QLabel("رقم القيد:"))
        header_layout.addWidget(self.entry_num_input)
        header_layout.addWidget(QLabel("الوصف:"))
        header_layout.addWidget(self.desc_input)
        
        layout.addLayout(header_layout)
        
        # Entry Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["الحساب", "البيان/الشرح", "مدين", "دائن", "مركز التكلفة", "حذف"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        # Balance Check Label
        self.balance_label = QLabel("القيد متوازن")
        self.balance_label.setStyleSheet("color: green; font-weight: bold;")
        layout.addWidget(self.balance_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("إضافة سطر")
        add_row_btn.clicked.connect(self.add_row)
        save_btn = QPushButton("حفظ القيد")
        save_btn.clicked.connect(self.save_journal)
        
        btn_layout.addWidget(add_row_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.table.itemChanged.connect(self.check_balance)

    def load_accounts(self):
        self.accounts = self.session.query(Account).all()

    def load_cost_centers(self):
        self.cost_centers = self.session.query(CostCenter).all()

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        acc_combo = QComboBox()
        for acc in self.accounts:
            acc_combo.addItem(f"{acc.account_number} - {acc.name}", acc.id)
        self.table.setCellWidget(row, 0, acc_combo)
        
        self.table.setItem(row, 1, QTableWidgetItem("")) # Description
        self.table.setItem(row, 2, QTableWidgetItem("0.0")) # Debit
        self.table.setItem(row, 3, QTableWidgetItem("0.0")) # Credit
        
        cc_combo = QComboBox()
        cc_combo.addItem("بدون", None)
        for cc in self.cost_centers:
            cc_combo.addItem(cc.name, cc.id)
        self.table.setCellWidget(row, 4, cc_combo)
        
        del_btn = QPushButton("حذف")
        del_btn.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        self.table.setCellWidget(row, 5, del_btn)

    def check_balance(self):
        total_debit = 0.0
        total_credit = 0.0
        for r in range(self.table.rowCount()):
            try:
                total_debit += float(self.table.item(r, 2).text() or 0)
                total_credit += float(self.table.item(r, 3).text() or 0)
            except: pass
            
        if abs(total_debit - total_credit) > 0.001:
            self.balance_label.setText("القيد غير متوازن")
            self.balance_label.setStyleSheet("color: red; font-weight: bold;")
            return False
        else:
            self.balance_label.setText(f"القيد متوازن (المجموع: {total_debit})")
            self.balance_label.setStyleSheet("color: green; font-weight: bold;")
            return True

    def save_journal(self):
        if not self.check_balance():
            QMessageBox.warning(self, "خطأ", "القيد غير متوازن!")
            return
            
        try:
            header = JournalHeader(
                entry_number=int(self.entry_num_input.text()),
                date=self.date_input.date().toPyDate(),
                description=self.desc_input.text()
            )
            self.session.add(header)
            self.session.flush()
            
            for r in range(self.table.rowCount()):
                acc_id = self.table.cellWidget(r, 0).currentData()
                desc = self.table.item(r, 1).text()
                debit = float(self.table.item(r, 2).text() or 0)
                credit = float(self.table.item(r, 3).text() or 0)
                cc_id = self.table.cellWidget(r, 4).currentData()
                
                if debit > 0 or credit > 0:
                    entry = JournalEntry(
                        header_id=header.id,
                        account_id=acc_id,
                        description=desc,
                        debit=debit,
                        credit=credit,
                        cost_center_id=cc_id
                    )
                    self.session.add(entry)
            
            self.session.commit()
            QMessageBox.information(self, "نجاح", "تم حفظ القيد بنجاح")
            self.table.setRowCount(0)
            self.entry_num_input.clear()
            self.desc_input.clear()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {str(e)}")
