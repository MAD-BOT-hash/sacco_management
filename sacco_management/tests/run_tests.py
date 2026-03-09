"""
Main Test Runner for SACCO Management System

Run all tests or specific test suites
Usage:
    python -m tests.run_tests --all
    python -m tests.run_tests --module member
    python -m tests.run_tests --performance
"""

import unittest
import sys
import os
import argparse
from datetime import datetime


def run_all_tests():
    """Run complete test suite"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Discover and add all test modules
    test_modules = [
        'tests.test_member',
        'tests.test_loan',
        'tests.test_savings_shares',
        'tests.test_integration',
        'tests.test_performance'
    ]
    
    for module_name in test_modules:
        try:
            module = __import__(module_name, fromlist=[''])
            suite.addTests(loader.loadTestsFromModule(module))
            print(f"✓ Loaded tests from {module_name}")
        except ImportError as e:
            print(f"✗ Failed to load {module_name}: {e}")
    
    # Run tests
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        failfast=False,
        buffer=False
    )
    
    print(f"\n{'='*70}")
    print(f"SACCO Management System - Test Suite")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"Test Summary")
    print(f"{'='*70}")
    print(f"Total Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Success: {result.wasSuccessful()}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    return result


def run_module_tests(module_name):
    """Run tests for specific module"""
    module_map = {
        'member': 'tests.test_member',
        'loan': 'tests.test_loan',
        'savings': 'tests.test_savings_shares',
        'shares': 'tests.test_savings_shares',
        'integration': 'tests.test_integration',
        'performance': 'tests.test_performance'
    }
    
    if module_name not in module_map:
        print(f"Unknown module: {module_name}")
        print(f"Available modules: {', '.join(module_map.keys())}")
        return None
    
    target_module = module_map[module_name]
    
    try:
        module = __import__(target_module, fromlist=[''])
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(module)
        
        runner = unittest.TextTestRunner(verbosity=2)
        print(f"\nRunning tests for: {target_module}\n")
        result = runner.run(suite)
        
        return result
    except ImportError as e:
        print(f"Failed to load module {target_module}: {e}")
        return None


def run_performance_suite():
    """Run only performance tests"""
    from tests.test_performance import run_performance_tests
    return run_performance_tests()


def generate_test_report(result):
    """Generate HTML test report"""
    import html
    
    report_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SACCO Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #2c3e50; }}
            .summary {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; }}
            .success {{ color: #27ae60; }}
            .failure {{ color: #e74c3c; }}
            .error {{ color: #e67e22; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #3498db; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>SACCO Management System - Test Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="summary">
            <h2>Summary</h2>
            <p>Total Tests: {result.testsRun}</p>
            <p class="{'success' if result.wasSuccessful() else 'failure'}">
                Status: {'PASSED ✓' if result.wasSuccessful() else 'FAILED ✗'}
            </p>
            <p>Failures: {len(result.failures)}</p>
            <p>Errors: {len(result.errors)}</p>
            <p>Skipped: {len(result.skipped)}</p>
        </div>
        
        {'<h2>Failures</h2>' if result.failures else ''}
        {generate_failure_table(result.failures) if result.failures else ''}
        
        {'<h2>Errors</h2>' if result.errors else ''}
        {generate_failure_table(result.errors) if result.errors else ''}
    </body>
    </html>
    """
    
    return report_html


def generate_failure_table(failures):
    """Generate HTML table for failures/errors"""
    if not failures:
        return ""
    
    html = "<table><tr><th>Test</th><th>Message</th></tr>"
    
    for test, traceback in failures:
        html += f"<tr><td>{test}</td><td><pre>{traceback[:500]}...</pre></td></tr>"
    
    html += "</table>"
    return html


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='SACCO Management System Test Runner')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--module', type=str, help='Run specific module (member, loan, savings, shares)')
    parser.add_argument('--performance', action='store_true', help='Run performance tests only')
    parser.add_argument('--report', action='store_true', help='Generate HTML report')
    
    args = parser.parse_args()
    
    if args.all:
        result = run_all_tests()
    elif args.module:
        result = run_module_tests(args.module)
    elif args.performance:
        result = run_performance_suite()
    else:
        # Default: run all tests
        result = run_all_tests()
    
    if args.report and result:
        report = generate_test_report(result)
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(f"\nTest report saved to: {report_file}\n")
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
