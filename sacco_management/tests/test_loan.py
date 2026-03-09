"""
Unit Tests for Loan Module

Tests for Loan Application, Repayment, Disbursement, and related operations
"""

import frappe
from frappe.utils import nowdate, flt
from .test_utils import SACCOBaseTestCase


class TestLoanApplication(SACCOBaseTestCase):
    """Test cases for Loan Application DocType"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_members = []
        cls.test_loans = []
    
    @classmethod
    def tearDownClass(cls):
        # Cleanup test loans
        for loan in cls.test_loans:
            if frappe.db.exists("Loan Application", loan):
                frappe.delete_doc("Loan Application", loan, force=True)
        
        # Cleanup test members
        for member in cls.test_members:
            if frappe.db.exists("SACCO Member", member):
                frappe.delete_doc("SACCO Member", member, force=True)
        
        frappe.db.commit()
        super().tearDownClass()
    
    def test_loan_application_creation(self):
        """Test basic loan application creation"""
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan = self.create_test_loan_application(member)
        self.test_loans.append(loan.name)
        
        self.assertIsNotNone(loan.name)
        self.assertEqual(loan.member, member.name)
        self.assertEqual(loan.amount_requested, 100000)
        self.assertEqual(loan.status, "Pending Approval")
    
    def test_loan_amount_validation(self):
        """Test that loan amount must be positive"""
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        # Try to create loan with zero amount
        with self.assertRaises(Exception):
            loan = self.create_test_loan_application(member, amount_requested=0)
        
        # Try to create loan with negative amount
        with self.assertRaises(Exception):
            loan = self.create_test_loan_application(member, amount_requested=-1000)
    
    def test_loan_interest_rate_validation(self):
        """Test interest rate validation"""
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        # Valid interest rate
        loan = self.create_test_loan_application(member, interest_rate=12)
        self.test_loans.append(loan.name)
        self.assertEqual(loan.interest_rate, 12)
        
        # Invalid interest rate (> 100)
        with self.assertRaises(Exception):
            loan = self.create_test_loan_application(member, interest_rate=150)
    
    def test_loan_approval_workflow(self):
        """Test loan approval workflow"""
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan = self.create_test_loan_application(member)
        self.test_loans.append(loan.name)
        
        # Approve loan
        loan.status = "Approved"
        loan.approved_date = nowdate()
        loan.approved_by = "Administrator"
        loan.save(ignore_permissions=True)
        
        self.assertEqual(loan.status, "Approved")
        self.assertIsNotNone(loan.approved_date)
    
    def test_loan_disbursement(self):
        """Test loan disbursement process"""
        from sacco_management.sacco.doctype.loan_disbursement.loan_disbursement import create_loan_disbursement
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        # Create and approve loan
        loan = self.create_test_loan_application(member, amount_requested=50000)
        self.test_loans.append(loan.name)
        
        loan.status = "Approved"
        loan.save(ignore_permissions=True)
        
        # Create disbursement
        disbursement = create_loan_disbursement(loan.name)
        disbursement.disbursement_account = "Cash in Hand - Test Branch"
        disbursement.payment_mode = "Cash"
        disbursement.insert(ignore_permissions=True)
        disbursement.submit()
        
        self.assertEqual(disbursement.docstatus, 1)
        self.assertEqual(disbursement.amount, 50000)
    
    def test_loan_repayment_schedule_generation(self):
        """Test automatic repayment schedule generation"""
        from sacco_management.sacco.utils.loan_utils import generate_amortization_schedule
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan = self.create_test_loan_application(
            member,
            amount_requested=120000,
            interest_rate=12,
            repayment_period=12
        )
        self.test_loans.append(loan.name)
        
        # Generate amortization schedule
        schedule = generate_amortization_schedule(loan.name)
        
        self.assertIsNotNone(schedule)
        self.assertGreater(len(schedule), 0)
        
        # Verify total payments
        total_principal = sum([item['principal'] for item in schedule])
        self.assertAlmostEqual(total_principal, 120000, places=2)
    
    def test_loan_repayment_processing(self):
        """Test loan repayment processing"""
        from sacco_management.sacco.doctype.loan_repayment.loan_repayment import create_loan_repayment
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan = self.create_test_loan_application(member, amount_requested=10000)
        self.test_loans.append(loan.name)
        
        # Approve and disburse
        loan.status = "Approved"
        loan.save(ignore_permissions=True)
        
        # Process repayment
        repayment = create_loan_repayment(loan.name)
        repayment.amount_paid = 1000
        repayment.payment_date = nowdate()
        repayment.payment_mode = "Cash"
        repayment.insert(ignore_permissions=True)
        repayment.submit()
        
        self.assertEqual(repayment.docstatus, 1)
        self.assertEqual(repayment.amount_paid, 1000)
        
        # Verify outstanding balance updated
        loan.reload()
        self.assertLess(loan.outstanding_principal, 10000)
    
    def test_loan_penalty_calculation(self):
        """Test penalty calculation for late payment"""
        from sacco_management.sacco.utils.loan_utils import calculate_penalty
        
        # Test fixed penalty
        penalty = calculate_penalty(
            overdue_amount=1000,
            days_overdue=30,
            penalty_type="Fixed",
            penalty_value=100
        )
        self.assertEqual(penalty, 100)
        
        # Test percentage penalty
        penalty = calculate_penalty(
            overdue_amount=1000,
            days_overdue=30,
            penalty_type="Percentage",
            penalty_value=5
        )
        self.assertEqual(penalty, 50)  # 5% of 1000
    
    def test_loan_guarantor(self):
        """Test adding guarantors to loan"""
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan = self.create_test_loan_application(member)
        self.test_loans.append(loan.name)
        
        # Add guarantor
        guarantor = loan.append("guarantors", {
            "guarantor_name": "John Doe",
            "guarantor_type": "Individual",
            "amount_guaranteed": 50000
        })
        
        loan.save(ignore_permissions=True)
        
        self.assertEqual(len(loan.guarantors), 1)
        self.assertEqual(loan.guarantors[0].guarantor_name, "John Doe")
    
    def test_loan_collateral(self):
        """Test adding collateral to loan"""
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan = self.create_test_loan_application(member)
        self.test_loans.append(loan.name)
        
        # Add collateral
        collateral = loan.append("collaterals", {
            "collateral_type": "Land Title",
            "description": "Plot No. 123, Main Street",
            "estimated_value": 200000
        })
        
        loan.save(ignore_permissions=True)
        
        self.assertEqual(len(loan.collaterals), 1)
        self.assertEqual(loan.collaterals[0].collateral_type, "Land Title")


class TestLoanAPI(SACCOBaseTestCase):
    """Test cases for Loan API endpoints"""
    
    def test_get_loans_api(self):
        """Test get_loans API endpoint"""
        from sacco_management.sacco.api.loan_api import get_loans
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        # Create test loans
        for i in range(3):
            loan = self.create_test_loan_application(member, amount_requested=10000 * (i + 1))
            self.test_loans.append(loan.name)
        
        response = get_loans(page=1, page_size=10)
        
        self.assertTrue(response["success"])
        self.assertIn("data", response)
        self.assertGreaterEqual(len(response["data"]["items"]), 3)
    
    def test_get_loan_details_api(self):
        """Test get_loan API endpoint"""
        from sacco_management.sacco.api.loan_api import get_loan
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan = self.create_test_loan_application(member)
        self.test_loans.append(loan.name)
        
        response = get_loan(loan.name)
        
        self.assertTrue(response["success"])
        self.assertIn("loan", response["data"])
        self.assertEqual(response["data"]["loan"]["name"], loan.name)
    
    def test_create_loan_application_api(self):
        """Test create_loan_application API endpoint"""
        from sacco_management.sacco.api.loan_api import create_loan_application
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan_data = {
            "member": member.name,
            "loan_type": "Normal Loan",
            "amount_requested": 50000,
            "repayment_period": 12
        }
        
        response = create_loan_application(loan_data)
        
        self.assertTrue(response["success"])
        self.assertIn("loan_id", response["data"])
    
    def test_approve_loan_api(self):
        """Test approve_loan API endpoint"""
        from sacco_management.sacco.api.loan_api import approve_loan
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan = self.create_test_loan_application(member)
        self.test_loans.append(loan.name)
        
        approval_details = {
            "approved_amount": 45000,
            "interest_rate": 10,
            "comments": "Approved with reduced amount"
        }
        
        response = approve_loan(loan.name, approval_details)
        
        self.assertTrue(response["success"])
        
        # Verify approval
        approved_loan = frappe.get_doc("Loan Application", loan.name)
        self.assertEqual(approved_loan.status, "Approved")
        self.assertEqual(approved_loan.amount_approved, 45000)
    
    def test_get_loan_schedule_api(self):
        """Test get_loan_schedule API endpoint"""
        from sacco_management.sacco.api.loan_api import get_loan_schedule
        
        member = self.create_test_member()
        self.test_members.append(member.name)
        
        loan = self.create_test_loan_application(member)
        self.test_loans.append(loan.name)
        
        response = get_loan_schedule(loan.name)
        
        self.assertTrue(response["success"])
        self.assertIn("schedule", response["data"])


class TestLoanCalculations(SACCOBaseTestCase):
    """Test loan calculation utilities"""
    
    def test_reducing_balance_interest(self):
        """Test reducing balance interest calculation"""
        from sacco_management.sacco.utils.loan_utils import calculate_reducing_balance_interest
        
        principal = 100000
        annual_rate = 12
        months = 12
        
        interest = calculate_reducing_balance_interest(principal, annual_rate, months)
        
        self.assertGreater(interest, 0)
        self.assertLess(interest, principal)  # Interest should be less than principal
    
    def test_emi_calculation(self):
        """Test EMI calculation"""
        from sacco_management.sacco.utils.loan_utils import calculate_emi
        
        principal = 120000
        annual_rate = 12
        months = 12
        
        emi = calculate_emi(principal, annual_rate, months)
        
        self.assertGreater(emi, 0)
        # EMI should be approximately 10662 for these parameters
        self.assertAlmostEqual(emi, 10662, delta=10)
    
    def test_outstanding_balance_calculation(self):
        """Test outstanding balance calculation"""
        original_principal = 100000
        paid_principal = 20000
        
        outstanding = original_principal - paid_principal
        
        self.assertEqual(outstanding, 80000)


# Helper function to run all loan tests
def run_loan_tests():
    """Run all loan module tests"""
    import unittest
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add tests
    suite.addTests(loader.loadTestsFromTestCase(TestLoanApplication))
    suite.addTests(loader.loadTestsFromTestCase(TestLoanAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestLoanCalculations))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result
