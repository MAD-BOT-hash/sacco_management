"""
Performance and Load Tests

Tests for system performance under load
"""

import frappe
from frappe.utils import nowdate, flt
import time
from .test_utils import SACCOBaseTestCase


class TestMemberPerformance(SACCOBaseTestCase):
    """Performance tests for member operations"""
    
    def test_bulk_member_creation(self):
        """Test creating multiple members in bulk"""
        import time
        
        num_members = 100
        start_time = time.time()
        
        created_members = []
        
        for i in range(num_members):
            member_data = {
                "member_name": f"Performance Test Member {i}",
                "email": f"perf_test_{i}_{frappe.generate_hash()[:6]}@example.com",
                "membership_type": "Ordinary"
            }
            
            member = self.create_test_member(**member_data)
            created_members.append(member.name)
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / num_members
        
        print(f"\nBulk Member Creation Performance:")
        print(f"  Total members: {num_members}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Average time per member: {avg_time*1000:.2f}ms")
        
        # Assert average creation time < 500ms
        self.assertLess(avg_time, 0.5, "Member creation too slow")
        
        # Cleanup
        for member_id in created_members:
            frappe.delete_doc("SACCO Member", member_id, force=True)
        
        frappe.db.commit()
    
    def test_member_search_performance(self):
        """Test search performance with large dataset"""
        # Create test data
        test_members = []
        for i in range(50):
            member = self.create_test_member(member_name=f"Search Test {i % 10}")
            test_members.append(member.name)
        
        frappe.db.commit()
        
        # Test search speed
        iterations = 10
        start_time = time.time()
        
        for _ in range(iterations):
            results = frappe.get_all("SACCO Member",
                                    filters={"member_name": ["like", "%Search Test%"]},
                                    fields=["name", "member_name"])
        
        end_time = time.time()
        avg_search_time = (end_time - start_time) / iterations * 1000
        
        print(f"\nMember Search Performance:")
        print(f"  Average search time: {avg_search_time:.2f}ms")
        print(f"  Results per search: {len(results)}")
        
        # Assert search completes in < 100ms
        self.assertLess(avg_search_time, 100, "Search too slow")
        
        # Cleanup
        for member_id in test_members:
            frappe.delete_doc("SACCO Member", member_id, force=True)
        
        frappe.db.commit()


class TestLoanPerformance(SACCOBaseTestCase):
    """Performance tests for loan operations"""
    
    def test_loan_calculation_performance(self):
        """Test loan calculation performance"""
        from sacco_management.sacco.utils.loan_utils import (
            calculate_reducing_balance_interest,
            generate_amortization_schedule,
            calculate_emi
        )
        
        iterations = 100
        start_time = time.time()
        
        for i in range(iterations):
            principal = 100000 + (i * 1000)
            rate = 10 + (i % 5)
            months = 12 + (i % 24)
            
            interest = calculate_reducing_balance_interest(principal, rate, months)
            emi = calculate_emi(principal, rate, months)
            schedule = generate_amortization_schedule(f"TEST-{i}")
        
        end_time = time.time()
        avg_calc_time = (end_time - start_time) / iterations * 1000
        
        print(f"\nLoan Calculation Performance:")
        print(f"  Average calculation time: {avg_calc_time:.2f}ms")
        print(f"  Total calculations: {iterations * 3}")
        
        # Assert calculations complete quickly
        self.assertLess(avg_calc_time, 50, "Calculations too slow")
    
    def test_bulk_loan_application(self):
        """Test creating multiple loan applications"""
        member = self.create_test_member()
        
        num_loans = 50
        start_time = time.time()
        
        created_loans = []
        
        for i in range(num_loans):
            loan_data = {
                "amount_requested": 50000 + (i * 1000),
                "repayment_period": 12
            }
            
            loan = self.create_test_loan_application(member, **loan_data)
            created_loans.append(loan.name)
        
        end_time = time.time()
        avg_time = (end_time - start_time) / num_loans * 1000
        
        print(f"\nBulk Loan Application Performance:")
        print(f"  Total loans: {num_loans}")
        print(f"  Average time per loan: {avg_time:.2f}ms")
        
        # Assert average creation time < 1s
        self.assertLess(avg_time, 1000, "Loan creation too slow")
        
        # Cleanup
        for loan_id in created_loans:
            frappe.delete_doc("Loan Application", loan_id, force=True)
        frappe.delete_doc("SACCO Member", member.name, force=True)
        frappe.db.commit()


class TestDatabasePerformance(SACCOBaseTestCase):
    """Test database query performance"""
    
    def test_query_optimization(self):
        """Test that queries use indexes efficiently"""
        
        # Create test data
        test_data = []
        for i in range(100):
            member = self.create_test_member(branch="Test Branch")
            test_data.append(member.name)
        
        frappe.db.commit()
        
        # Test indexed query
        start_time = time.time()
        
        results = frappe.get_all("SACCO Member",
                                filters={"branch": "Test Branch"},
                                fields=["name", "member_name"])
        
        query_time = (time.time() - start_time) * 1000
        
        print(f"\nDatabase Query Performance:")
        print(f"  Query time: {query_time:.2f}ms")
        print(f"  Results returned: {len(results)}")
        
        # Query should complete in < 200ms
        self.assertLess(query_time, 200, "Query too slow")
        
        # Cleanup
        for member_id in test_data:
            frappe.delete_doc("SACCO Member", member_id, force=True)
        
        frappe.db.commit()


class TestAPIPerformance(APITestCase):
    """Test API endpoint performance"""
    
    def test_api_response_time(self):
        """Test API endpoint response times"""
        import time
        
        # Create test member
        member = self.create_test_member()
        
        # Test get_member endpoint
        iterations = 20
        start_time = time.time()
        
        for _ in range(iterations):
            response = self.make_api_call(
                "GET",
                "member_api.get_member",
                params={"member_id": member.name}
            )
        
        avg_response_time = (time.time() - start_time) / iterations * 1000
        
        print(f"\nAPI Response Time Performance:")
        print(f"  Endpoint: get_member")
        print(f"  Average response time: {avg_response_time:.2f}ms")
        print(f"  Iterations: {iterations}")
        
        # Assert response time < 500ms
        self.assertLess(avg_response_time, 500, "API response too slow")
        
        # Cleanup
        frappe.delete_doc("SACCO Member", member.name, force=True)
        frappe.db.commit()


def run_performance_tests():
    """Run all performance tests"""
    import unittest
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMemberPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestLoanPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabasePerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIPerformance))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result
