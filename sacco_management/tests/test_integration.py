"""
Integration Tests for API Endpoints

End-to-end tests for complete business workflows
"""

import frappe
from frappe.utils import nowdate, flt
from .test_utils import APITestCase


class TestMemberAPIIntegration(APITestCase):
    """Integration tests for Member API workflows"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.created_members = []
    
    @classmethod
    def tearDownClass(cls):
        # Cleanup
        for member_id in cls.created_members:
            if frappe.db.exists("SACCO Member", member_id):
                frappe.delete_doc("SACCO Member", member_id, force=True)
        
        frappe.db.commit()
        super().tearDownClass()
    
    def test_complete_member_lifecycle(self):
        """Test complete member lifecycle: create -> update -> view -> search"""
        
        # 1. Create member via API
        create_data = {
            "member_name": "Integration Test Member",
            "email": f"integration_{frappe.generate_hash()[:8]}@example.com",
            "membership_type": "Ordinary",
            "phone_number": "+1234567890"
        }
        
        create_response = self.make_api_call(
            "POST",
            "member_api.create_member",
            params={"member_data": create_data}
        )
        
        self.assertResponseSuccess(create_response)
        member_id = create_response["data"]["member_id"]
        self.created_members.append(member_id)
        
        # 2. View member details
        view_response = self.make_api_call(
            "GET",
            "member_api.get_member",
            params={"member_id": member_id}
        )
        
        self.assertResponseSuccess(view_response)
        self.assertEqual(view_response["data"]["member"]["name"], member_id)
        
        # 3. Update member
        update_data = {
            "employer_name": "Test Employer Inc.",
            "department": "IT"
        }
        
        update_response = self.make_api_call(
            "PUT",
            "member_api.update_member",
            params={"member_id": member_id, "member_data": update_data}
        )
        
        self.assertResponseSuccess(update_response)
        
        # 4. Search for member
        search_response = self.make_api_call(
            "GET",
            "member_api.search_members",
            params={"query": "Integration Test"}
        )
        
        self.assertResponseSuccess(search_response)
        self.assertGreater(search_response["data"]["count"], 0)
        
        # 5. Get member statistics
        stats_response = self.make_api_call(
            "GET",
            "member_api.get_member_statistics"
        )
        
        self.assertResponseSuccess(stats_response)


class TestLoanAPIIntegration(APITestCase):
    """Integration tests for Loan API workflows"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_members = []
        cls.test_loans = []
    
    @classmethod
    def tearDownClass(cls):
        for loan in cls.test_loans:
            if frappe.db.exists("Loan Application", loan):
                frappe.delete_doc("Loan Application", loan, force=True)
        
        for member in cls.test_members:
            if frappe.db.exists("SACCO Member", member):
                frappe.delete_doc("SACCO Member", member, force=True)
        
        frappe.db.commit()
        super().tearDownClass()
    
    def test_complete_loan_lifecycle(self):
        """Test complete loan lifecycle: application -> approval -> disbursement -> repayment"""
        
        # 1. Create member first
        member_data = {
            "member_name": "Loan Test Member",
            "email": f"loan_test_{frappe.generate_hash()[:8]}@example.com",
            "membership_type": "Ordinary"
        }
        
        member_response = self.make_api_call(
            "POST",
            "member_api.create_member",
            params={"member_data": member_data}
        )
        
        self.assertResponseSuccess(member_response)
        member_id = member_response["data"]["member_id"]
        self.test_members.append(member_id)
        
        # 2. Create loan application
        loan_data = {
            "member": member_id,
            "loan_type": "Normal Loan",
            "amount_requested": 100000,
            "repayment_period": 12,
            "interest_rate": 12
        }
        
        loan_response = self.make_api_call(
            "POST",
            "loan_api.create_loan_application",
            params={"loan_data": loan_data}
        )
        
        self.assertResponseSuccess(loan_response)
        loan_id = loan_response["data"]["loan_id"]
        self.test_loans.append(loan_id)
        
        # 3. Approve loan
        approval_data = {
            "approved_amount": 95000,
            "interest_rate": 11,
            "comments": "Approved for integration test"
        }
        
        approve_response = self.make_api_call(
            "POST",
            "loan_api.approve_loan",
            params={"loan_id": loan_id, "approval_details": approval_data}
        )
        
        self.assertResponseSuccess(approve_response)
        
        # 4. Get loan schedule
        schedule_response = self.make_api_call(
            "GET",
            "loan_api.get_loan_schedule",
            params={"loan_id": loan_id}
        )
        
        self.assertResponseSuccess(schedule_response)
        self.assertIn("schedule", schedule_response["data"])
        
        # 5. Process repayment
        repayment_data = {
            "amount_paid": 10000,
            "payment_date": nowdate(),
            "payment_mode": "Cash"
        }
        
        repayment_response = self.make_api_call(
            "POST",
            "loan_api.process_repayment",
            params={"loan_id": loan_id, "repayment_data": repayment_data}
        )
        
        self.assertResponseSuccess(repayment_response)


class TestSavingsAPIIntegration(APITestCase):
    """Integration tests for Savings API workflows"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_members = []
        cls.test_accounts = []
    
    @classmethod
    def tearDownClass(cls):
        for account in cls.test_accounts:
            if frappe.db.exists("Savings Account", account):
                frappe.delete_doc("Savings Account", account, force=True)
        
        for member in cls.test_members:
            if frappe.db.exists("SACCO Member", member):
                frappe.delete_doc("SACCO Member", member, force=True)
        
        frappe.db.commit()
        super().tearDownClass()
    
    def test_savings_workflow(self):
        """Test savings account creation, deposit, and withdrawal"""
        
        # 1. Create member
        member_data = {
            "member_name": "Savings Test Member",
            "email": f"savings_test_{frappe.generate_hash()[:8]}@example.com",
            "membership_type": "Ordinary"
        }
        
        member_response = self.make_api_call(
            "POST",
            "member_api.create_member",
            params={"member_data": member_data}
        )
        
        self.assertResponseSuccess(member_response)
        member_id = member_response["data"]["member_id"]
        self.test_members.append(member_id)
        
        # 2. Create savings account
        account_data = {
            "member": member_id,
            "account_type": "Regular Savings"
        }
        
        account_response = self.make_api_call(
            "POST",
            "savings_shares_api.create_savings_account",
            params={"account_data": account_data}
        )
        
        self.assertResponseSuccess(account_response)
        account_id = account_response["data"]["account_id"]
        self.test_accounts.append(account_id)
        
        # 3. Make deposit
        deposit_data = {
            "savings_account": account_id,
            "amount": 50000,
            "payment_mode": "Bank Transfer"
        }
        
        deposit_response = self.make_api_call(
            "POST",
            "savings_shares_api.process_deposit",
            params={"deposit_data": deposit_data}
        )
        
        self.assertResponseSuccess(deposit_response)
        
        # 4. Make withdrawal
        withdrawal_data = {
            "savings_account": account_id,
            "amount": 10000,
            "withdrawal_reason": "Test withdrawal"
        }
        
        withdrawal_response = self.make_api_call(
            "POST",
            "savings_shares_api.process_withdrawal",
            params={"withdrawal_data": withdrawal_data}
        )
        
        self.assertResponseSuccess(withdrawal_response)


class TestSharesAPIIntegration(APITestCase):
    """Integration tests for Shares API workflows"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_members = []
    
    @classmethod
    def tearDownClass(cls):
        for member in cls.test_members:
            if frappe.db.exists("SACCO Member", member):
                frappe.delete_doc("SACCO Member", member, force=True)
        
        frappe.db.commit()
        super().tearDownClass()
    
    def test_share_purchase_workflow(self):
        """Test share purchase workflow"""
        
        # 1. Create member
        member_data = {
            "member_name": "Shares Test Member",
            "email": f"shares_test_{frappe.generate_hash()[:8]}@example.com",
            "membership_type": "Ordinary"
        }
        
        member_response = self.make_api_call(
            "POST",
            "member_api.create_member",
            params={"member_data": member_data}
        )
        
        self.assertResponseSuccess(member_response)
        member_id = member_response["data"]["member_id"]
        self.test_members.append(member_id)
        
        # 2. Purchase shares
        purchase_data = {
            "member": member_id,
            "share_type": "Ordinary Shares",
            "quantity": 100,
            "payment_mode": "Cash"
        }
        
        purchase_response = self.make_api_call(
            "POST",
            "savings_shares_api.purchase_shares",
            params={"purchase_data": purchase_data}
        )
        
        self.assertResponseSuccess(purchase_response)
        
        # 3. Verify allocation created
        allocations_response = self.make_api_call(
            "GET",
            "savings_shares_api.get_share_allocations",
            params={"member_id": member_id}
        )
        
        self.assertResponseSuccess(allocations_response)
        self.assertGreater(len(allocations_response["data"]["allocations"]), 0)


# Helper function to run all integration tests
def run_integration_tests():
    """Run all API integration tests"""
    import unittest
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMemberAPIIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestLoanAPIIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSavingsAPIIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSharesAPIIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result
