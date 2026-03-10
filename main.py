import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QLabel)
from PyQt6.QtCore import Qt
from chart_of_accounts import ChartOfAccounts
from journal_entries import JournalEntries
from reports import GeneralLedger, TrialBalance
from models import Session, CostCenter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("منظومة المحاسبة الاحترافية - Manus")
        self.setGeometry(100, 100, 1200, 800)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        self.init_db_data()
        self.init_ui()

    def init_db_data(self):
        # Add some default cost centers if none exist
        session = Session()
        if session.query(CostCenter).count() == 0:
            cc1 = CostCenter(name="الإدارة العامة")
            cc2 = CostCenter(name="قسم المبيعات")
            cc3 = CostCenter(name="قسم الإنتاج")
            session.add_all([cc1, cc2, cc3])
            session.commit()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("نظام المحاسبة المتكامل")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px; color: #2c3e50;")
        layout.addWidget(title)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { height: 40px; width: 150px; font-size: 14px; }
            QTabWidget::pane { border: 1px solid #ccc; }
        """)
        
        self.coa_tab = ChartOfAccounts()
        self.journal_tab = JournalEntries()
        self.ledger_tab = GeneralLedger()
        self.trial_tab = TrialBalance()
        
        self.tabs.addTab(self.coa_tab, "دليل الحسابات")
        self.tabs.addTab(self.journal_tab, "القيود اليومية")
        self.tabs.addTab(self.ledger_tab, "دفتر الأستاذ")
        self.tabs.addTab(self.trial_tab, "ميزان المراجعة")
        
        # Connect tab change to refresh data
        self.tabs.currentChanged.connect(self.refresh_data)
        
        layout.addWidget(self.tabs)

    def refresh_data(self, index):
        # Refresh account lists and reports when switching tabs
        if index == 1: # Journal Entries
            self.journal_tab.load_accounts()
            self.journal_tab.load_cost_centers()
        elif index == 2: # General Ledger
            self.ledger_tab.update_acc_combo()
        elif index == 3: # Trial Balance
            self.trial_tab.load_trial_balance()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Professional look
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
