"""
Unit Tests for Savings & Shares Module

Tests for Savings Account, Deposits, Withdrawals, Share Allocation, and Dividends
"""

import frappe
from frappe.utils import nowdate, flt
from .test_utils import SACCOBaseTestCase


class TestSavingsAccount(SACCOBaseTestCase):
    """Test cases for Savings Account operations"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_members = []
        cls.test_accounts = []
    
    @classmethod
    def tearDownClass(cls):
        # Cleanup
        for account in cls.test_accounts:
            if frappe.db.exists("Savings Account", account):
                frappe.delete_doc("Savings Account", account, force=True)
        
        for member in cls.test_members:
            if frappe.db.exists("SACCO Member", member):
                frappe.delete_doc("SACCO Member", member, force=True)
        
        frappe.db.commit()
        super().tearDownClass()
    
    def test_savings_account_creation(self):
        """Test savings account creation"""
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        account = self.create_test_savings_account(member)
        self.test_accounts.append(account.name)
        
        self.assertIsNotNone(account.name)
        self.assertEqual(account.member, member.name)
        self.assertEqual(account.status, "Active")
    
    def test_savings_deposit(self):
        """Test savings deposit processing"""
        from sacco_management.sacco.doctype.savings_deposit.savings_deposit import create_savings_deposit
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        account = self.create_test_savings_account(member)
        self.test_accounts.append(account.name)
        
        # Process deposit
        deposit = create_savings_deposit(account.name)
        deposit.amount = 5000
        deposit.payment_mode = "Cash"
        deposit.insert(ignore_permissions=True)
        deposit.submit()
        
        self.assertEqual(deposit.docstatus, 1)
        self.assertEqual(deposit.amount, 5000)
        
        # Verify account balance updated
        account.reload()
        self.assertGreaterEqual(account.current_balance, 5000)
    
    def test_savings_withdrawal(self):
        """Test savings withdrawal processing"""
        from sacco_management.sacco.doctype.savings_withdrawal.savings_withdrawal import create_savings_withdrawal
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        account = self.create_test_savings_account(member)
        self.test_accounts.append(account.name)
        
        # First make a deposit
        from sacco_management.sacco.doctype.savings_deposit.savings_deposit import create_savings_deposit
        deposit = create_savings_deposit(account.name)
        deposit.amount = 10000
        deposit.payment_mode = "Cash"
        deposit.insert(ignore_permissions=True)
        deposit.submit()
        
        # Process withdrawal
        withdrawal = create_savings_withdrawal(account.name)
        withdrawal.amount = 3000
        withdrawal.reason = "Emergency expense"
        withdrawal.insert(ignore_permissions=True)
        withdrawal.submit()
        
        self.assertEqual(withdrawal.docstatus, 1)
        
        # Verify balance reduced
        account.reload()
        self.assertEqual(account.current_balance, 7000)
    
    def test_savings_interest_calculation(self):
        """Test savings interest calculation"""
        from sacco_management.sacco.doctype.savings_interest_posting.savings_interest_posting import create_savings_interest_posting
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        account = self.create_test_savings_account(member, account_type="Regular Savings")
        self.test_accounts.append(account.name)
        
        # Make deposit
        from sacco_management.sacco.doctype.savings_deposit.savings_deposit import create_savings_deposit
        deposit = create_savings_deposit(account.name)
        deposit.amount = 100000
        deposit.payment_mode = "Bank Transfer"
        deposit.insert(ignore_permissions=True)
        deposit.submit()
        
        # Post interest
        interest = create_savings_interest_posting(account.name)
        interest.interest_rate = 5
        interest.interest_amount = 416.67  # 5% annual on 100k for 1 month
        interest.posting_date = nowdate()
        interest.insert(ignore_permissions=True)
        interest.submit()
        
        self.assertEqual(interest.docstatus, 1)
        
        # Verify balance increased
        account.reload()
        self.assertGreater(account.current_balance, 100000)


class TestShareAllocation(SACCOBaseTestCase):
    """Test cases for Share Allocation operations"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_members = []
        cls.test_allocations = []
    
    @classmethod
    def tearDownClass(cls):
        for allocation in cls.test_allocations:
            if frappe.db.exists("Share Allocation", allocation):
                frappe.delete_doc("Share Allocation", allocation, force=True)
        
        for member in cls.test_members:
            if frappe.db.exists("SACCO Member", member):
                frappe.delete_doc("SACCO Member", member, force=True)
        
        frappe.db.commit()
        super().tearDownClass()
    
    def test_share_allocation_creation(self):
        """Test share allocation creation"""
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        allocation = self.create_test_share_allocation(member)
        self.test_allocations.append(allocation.name)
        
        self.assertEqual(allocation.docstatus, 1)
        self.assertEqual(allocation.member, member.name)
        self.assertEqual(allocation.quantity, 100)
    
    def test_share_purchase(self):
        """Test share purchase process"""
        from sacco_management.sacco.doctype.share_purchase.share_purchase import create_share_purchase
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        purchase = create_share_purchase(member.name)
        purchase.share_type = "Ordinary Shares"
        purchase.quantity = 50
        purchase.rate_per_share = 100
        purchase.payment_mode = "Cash"
        purchase.insert(ignore_permissions=True)
        purchase.submit()
        
        self.assertEqual(purchase.docstatus, 1)
        self.assertEqual(purchase.quantity, 50)
        self.assertEqual(purchase.total_amount, 5000)
    
    def test_share_redemption(self):
        """Test share redemption process"""
        from sacco_management.sacco.doctype.share_redemption.share_redemption import create_share_redemption
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        # First allocate shares
        allocation = self.create_test_share_allocation(member, quantity=200)
        self.test_allocations.append(allocation.name)
        
        # Request redemption
        redemption = create_share_redemption(member.name)
        redemption.share_type = "Ordinary Shares"
        redemption.quantity_requested = 50
        redemption.reason = "Financial need"
        redemption.insert(ignore_permissions=True)
        redemption.submit()
        
        self.assertEqual(redemption.docstatus, 1)
        self.assertEqual(redemption.quantity_requested, 50)


class TestDividendDistribution(SACCOBaseTestCase):
    """Test cases for Dividend Distribution"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_members = []
        cls.test_periods = []
    
    @classmethod
    def tearDownClass(cls):
        for period in cls.test_periods:
            if frappe.db.exists("Dividend Period", period):
                frappe.delete_doc("Dividend Period", period, force=True)
        
        for member in cls.test_members:
            if frappe.db.exists("SACCO Member", member):
                frappe.delete_doc("SACCO Member", member, force=True)
        
        frappe.db.commit()
        super().tearDownClass()
    
    def test_dividend_period_creation(self):
        """Test dividend period creation"""
        period_data = {
            "period_name": "FY 2024-25",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "dividend_rate": 10,
            "total_dividend_pool": 1000000
        }
        
        period = frappe.new_doc("Dividend Period")
        period.update(period_data)
        period.insert(ignore_permissions=True)
        
        self.test_periods.append(period.name)
        
        self.assertIsNotNone(period.name)
        self.assertEqual(period.dividend_rate, 10)
    
    def test_dividend_calculation(self):
        """Test dividend calculation for member"""
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        # Allocate shares
        allocation = self.create_test_share_allocation(member, quantity=1000, total_amount=100000)
        self.test_allocations.append(allocation.name)
        
        # Create dividend period
        period = frappe.new_doc("Dividend Period")
        period.period_name = "Test Period"
        period.start_date = "2024-01-01"
        period.end_date = "2024-12-31"
        period.dividend_rate = 10
        period.insert(ignore_permissions=True)
        self.test_periods.append(period.name)
        
        # Calculate dividend
        calc_data = {
            "dividend_period": period.name,
            "member": member.name,
            "eligible_shares": 1000,
            "dividend_rate": 10
        }
        
        calc = frappe.new_doc("Dividend Calculation")
        calc.update(calc_data)
        calc.calculate_dividend()
        
        self.assertEqual(calc.gross_dividend, 10000)  # 10% of 100000


# Helper function to run all savings & shares tests
def run_savings_shares_tests():
    """Run all savings & shares module tests"""
    import unittest
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestSavingsAccount))
    suite.addTests(loader.loadTestsFromTestCase(TestShareAllocation))
    suite.addTests(loader.loadTestsFromTestCase(TestDividendDistribution))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result
