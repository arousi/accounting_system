from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView)
from models import Session, Account, Base, engine
from sqlalchemy import func

class ChartOfAccounts(QWidget):
    def __init__(self):
        super().__init__()
        self.session = Session()
        self.init_ui()
        self.load_accounts()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Input Form
        form_layout = QHBoxLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("اسم الحساب")
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["1", "2", "3", "4", "5"])
        
        self.category_combo = QComboBox()
        self.category_combo.addItems(["أصول", "خصوم", "حقوق ملكية", "إيرادات", "مصروفات"])
        
        self.statement_combo = QComboBox()
        self.statement_combo.addItems(["الميزانية العمومية", "قائمة الدخل"])
        
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("حساب رئيسي (لا يوجد)", None)
        self.update_parent_combo()
        
        add_btn = QPushButton("إضافة حساب")
        add_btn.clicked.connect(self.add_account)
        
        form_layout.addWidget(QLabel("الاسم:"))
        form_layout.addWidget(self.name_input)
        form_layout.addWidget(QLabel("المستوى:"))
        form_layout.addWidget(self.level_combo)
        form_layout.addWidget(QLabel("التصنيف:"))
        form_layout.addWidget(self.category_combo)
        form_layout.addWidget(QLabel("القائمة:"))
        form_layout.addWidget(self.statement_combo)
        form_layout.addWidget(QLabel("الحساب الرئيسي:"))
        form_layout.addWidget(self.parent_combo)
        form_layout.addWidget(add_btn)
        
        layout.addLayout(form_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["رقم الحساب", "اسم الحساب", "المستوى", "التصنيف", "الحساب الرئيسي", "القائمة المالية"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        self.setLayout(layout)

    def update_parent_combo(self):
        self.parent_combo.clear()
        self.parent_combo.addItem("حساب رئيسي (لا يوجد)", None)
        accounts = self.session.query(Account).all()
        for acc in accounts:
            self.parent_combo.addItem(f"{acc.account_number} - {acc.name}", acc.id)

    def generate_account_number(self, parent_id, category):
        # Simple logic: Category digit + sequence
        cat_map = {"أصول": "1", "خصوم": "2", "حقوق ملكية": "3", "إيرادات": "4", "مصروفات": "5"}
        prefix = cat_map.get(category, "9")
        
        if parent_id:
            parent = self.session.query(Account).filter_by(id=parent_id).first()
            prefix = parent.account_number
            
        count = self.session.query(Account).filter(Account.parent_id == parent_id).count()
        return f"{prefix}{count + 1:02d}"

    def add_account(self):
        name = self.name_input.text()
        level = int(self.level_combo.currentText())
        category = self.category_combo.currentText()
        statement = self.statement_combo.currentText()
        parent_id = self.parent_combo.currentData()
        
        if not name:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم الحساب")
            return
            
        acc_num = self.generate_account_number(parent_id, category)
        
        new_acc = Account(
            account_number=acc_num,
            name=name,
            level=level,
            category=category,
            parent_id=parent_id,
            financial_statement=statement
        )
        
        try:
            self.session.add(new_acc)
            self.session.commit()
            self.name_input.clear()
            self.update_parent_combo()
            self.load_accounts()
            QMessageBox.information(self, "نجاح", f"تمت إضافة الحساب برقم: {acc_num}")
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {str(e)}")

    def load_accounts(self):
        self.table.setRowCount(0)
        accounts = self.session.query(Account).order_by(Account.account_number).all()
        for acc in accounts:
            row = self.table.rowCount()
            self.table.insertRow(row)
            parent_name = acc.parent.name if acc.parent else "-"
            self.table.setItem(row, 0, QTableWidgetItem(acc.account_number))
            self.table.setItem(row, 1, QTableWidgetItem(acc.name))
            self.table.setItem(row, 2, QTableWidgetItem(str(acc.level)))
            self.table.setItem(row, 3, QTableWidgetItem(acc.category))
            self.table.setItem(row, 4, QTableWidgetItem(parent_name))
            self.table.setItem(row, 5, QTableWidgetItem(acc.financial_statement))
