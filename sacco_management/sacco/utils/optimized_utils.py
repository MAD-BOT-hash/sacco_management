"""
Optimized Utility Functions with Caching

This module provides cached versions of frequently-used utility functions
for better performance.
"""

import frappe
from frappe import _
from sacco_management.sacco.utils.performance import cache_result, cache_member_data
from sacco_management.sacco.utils.loan_utils import calculate_loan_summary


# =============================================================================
# MEMBER UTILITIES (OPTIMIZED)
# =============================================================================

@cache_member_data(ttl_seconds=300)
def get_member_profile_cached(member_id):
    """
    Get complete member profile with caching
    
    Args:
        member_id (str): Member ID
    
    Returns:
        dict: Complete member profile
    """
    member = frappe.get_doc("SACCO Member", member_id)
    
    # Get all related data in optimized queries
    savings_total = frappe.db.sql("""
        SELECT SUM(current_balance) 
        FROM `tabSavings Account` 
        WHERE member = %s AND docstatus = 1 AND status = 'Active'
    """, (member_id,))[0][0] or 0
    
    loans_total = frappe.db.sql("""
        SELECT SUM(outstanding_principal) 
        FROM `tabLoan Application` 
        WHERE member = %s AND docstatus = 1 AND status IN ('Disbursed', 'Active')
    """, (member_id,))[0][0] or 0
    
    shares_total = frappe.db.sql("""
        SELECT SUM(total_amount) 
        FROM `tabShare Allocation` 
        WHERE member = %s AND docstatus = 1 AND status = 'Allocated'
    """, (member_id,))[0][0] or 0
    
    return {
        "member": member.as_dict(),
        "total_savings": savings_total,
        "total_loans": loans_total,
        "total_shares": shares_total,
        "net_worth": savings_total + shares_total - loans_total
    }


@cache_result(ttl_seconds=600)
def get_member_statistics_cached(branch=None):
    """
    Get member statistics with caching
    
    Args:
        branch (str): Optional branch filter
    
    Returns:
        dict: Member statistics
    """
    filters = {"membership_status": "Active"}
    if branch:
        filters["branch"] = branch
    
    total_members = frappe.db.count("SACCO Member", filters=filters)
    
    stats = frappe.db.sql("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN gender = 'Male' THEN 1 ELSE 0 END) as male_count,
            SUM(CASE WHEN gender = 'Female' THEN 1 ELSE 0 END) as female_count,
            AVG(DATEDIFF(CURDATE(), joining_date)) / 365 as avg_membership_years
        FROM `tabSACCO Member`
        WHERE membership_status = 'Active'
        {}
    """.format("AND branch = %s" if branch else ""), 
    (branch,) if branch else (), as_dict=True)[0]
    
    return {
        "total_members": total_members,
        "statistics": stats
    }


# =============================================================================
# LOAN UTILITIES (OPTIMIZED)
# =============================================================================

@cache_result(ttl_seconds=300)
def get_loan_portfolio_stats():
    """
    Get loan portfolio statistics with caching
    
    Returns:
        dict: Loan portfolio statistics
    """
    stats = frappe.db.sql("""
        SELECT 
            status,
            COUNT(*) as count,
            SUM(amount_requested) as total_requested,
            SUM(outstanding_principal) as total_outstanding,
            SUM(overdue_amount) as total_overdue
        FROM `tabLoan Application`
        WHERE docstatus = 1
        GROUP BY status
    """, as_dict=True)
    
    return {stat.status: stat for stat in stats}


@cache_result(ttl_seconds=1800)  # 30 minutes
def get_monthly_disbursement_trend(months=12):
    """
    Get monthly disbursement trend with caching
    
    Args:
        months (int): Number of months to analyze
    
    Returns:
        list: Monthly trend data
    """
    trend = frappe.db.sql(f"""
        SELECT 
            DATE_FORMAT(disbursement_date, '%%Y-%%m') as month,
            COUNT(*) as count,
            SUM(amount_approved) as total_amount
        FROM `tabLoan Application`
        WHERE status = 'Disbursed'
        AND disbursement_date >= DATE_SUB(CURDATE(), INTERVAL {months} MONTH)
        GROUP BY DATE_FORMAT(disbursement_date, '%%Y-%%m')
        ORDER BY month DESC
    """, as_dict=True)
    
    return trend


# =============================================================================
# SAVINGS UTILITIES (OPTIMIZED)
# =============================================================================

@cache_result(ttl_seconds=300)
def get_total_savings_by_type():
    """
    Get total savings grouped by account type with caching
    
    Returns:
        dict: Savings by type
    """
    result = frappe.db.sql("""
        SELECT 
            account_type,
            COUNT(*) as account_count,
            SUM(current_balance) as total_balance,
            AVG(current_balance) as average_balance
        FROM `tabSavings Account`
        WHERE docstatus = 1 AND status = 'Active'
        GROUP BY account_type
    """, as_dict=True)
    
    return {row.account_type: row for row in result}


@cache_member_data(ttl_seconds=300)
def get_member_savings_summary_cached(member_id):
    """
    Get member savings summary with caching
    
    Args:
        member_id (str): Member ID
    
    Returns:
        dict: Savings summary
    """
    savings = frappe.get_all(
        "Savings Account",
        filters={"member": member_id, "docstatus": 1, "status": "Active"},
        fields=["account_type", "current_balance"],
        order_by="account_type"
    )
    
    total = sum(s.current_balance for s in savings)
    
    return {
        "accounts": savings,
        "total_balance": total,
        "account_count": len(savings)
    }


# =============================================================================
# SHARES UTILITIES (OPTIMIZED)
# =============================================================================

@cache_result(ttl_seconds=600)
def get_share_capital_summary_cached():
    """
    Get share capital summary with caching
    
    Returns:
        dict: Share capital summary
    """
    summary = frappe.db.sql("""
        SELECT 
            COUNT(DISTINCT member) as total_members,
            SUM(quantity) as total_shares,
            SUM(total_amount) as total_capital
        FROM `tabShare Allocation`
        WHERE docstatus = 1 AND status = 'Allocated'
    """, as_dict=True)[0]
    
    return summary


@cache_result(ttl_seconds=1800)
def get_dividend_summary_cached(year=None):
    """
    Get dividend summary with caching
    
    Args:
        year (int): Year to analyze
    
    Returns:
        dict: Dividend summary
    """
    from datetime import date
    
    if not year:
        year = date.today().year
    
    total_dividend = frappe.db.sql("""
        SELECT SUM(total_dividend_amount)
        FROM `tabDividend Declaration`
        WHERE YEAR(declaration_date) = %s AND docstatus = 1
    """, (year,))[0][0] or 0
    
    paid_dividend = frappe.db.sql("""
        SELECT SUM(total_amount_paid)
        FROM `tabDividend Payment`
        WHERE YEAR(payment_date) = %s AND docstatus = 1
    """, (year,))[0][0] or 0
    
    return {
        "year": year,
        "declared": total_dividend,
        "paid": paid_dividend,
        "pending": total_dividend - paid_dividend
    }


# =============================================================================
# DASHBOARD DATA (OPTIMIZED)
# =============================================================================

@cache_result(ttl_seconds=300)
def get_optimized_dashboard_data():
    """
    Get dashboard data with comprehensive caching
    
    Returns:
        dict: Complete dashboard data
    """
    # Member stats
    member_stats = get_member_statistics_cached()
    
    # Loan portfolio
    loan_stats = get_loan_portfolio_stats()
    
    # Savings summary
    savings_stats = get_total_savings_by_type()
    
    # Share capital
    share_stats = get_share_capital_summary_cached()
    
    # Recent activity
    recent_loans = frappe.get_all(
        "Loan Application",
        filters={},
        fields=["name", "member", "amount_requested", "application_date"],
        order_by="creation DESC",
        limit=5
    )
    
    return {
        "members": member_stats,
        "loans": loan_stats,
        "savings": savings_stats,
        "shares": share_stats,
        "recent_activity": {
            "recent_loans": recent_loans
        }
    }


# =============================================================================
# REPORT UTILITIES (OPTIMIZED)
# =============================================================================

@cache_result(ttl_seconds=600)
def get_trial_balance_cached(posting_date):
    """
    Get trial balance with caching
    
    Args:
        posting_date (str): Posting date
    
    Returns:
        list: Trial balance data
    """
    # This would replace the existing trial balance logic with cached version
    return frappe.db.sql("""
        SELECT 
            account,
            SUM(debit) as total_debit,
            SUM(credit) as total_credit,
            (SUM(debit) - SUM(credit)) as balance
        FROM `tabSACCO GL Entry`
        WHERE posting_date <= %s
        GROUP BY account
        HAVING balance != 0
    """, (posting_date,), as_dict=True)


@cache_result(ttl_seconds=900)
def get_contribution_summary_cached(from_date, to_date, branch=None):
    """
    Get contribution summary with caching
    
    Args:
        from_date (str): From date
        to_date (str): To date
        branch (str): Optional branch filter
    
    Returns:
        list: Contribution summary
    """
    filters = [
        ["Member Contribution", "posting_date", ">=", from_date],
        ["Member Contribution", "posting_date", "<=", to_date],
        ["Member Contribution", "docstatus", "=", 1]
    ]
    
    if branch:
        filters.append(["SACCO Member", "branch", "=", branch])
    
    return frappe.get_all(
        "Member Contribution",
        filters=filters,
        fields=[
            "contribution_type",
            "SUM(amount) as total_amount",
            "COUNT(*) as contribution_count"
        ],
        group_by="contribution_type"
    )


# =============================================================================
# CACHE INVALIDATION HELPERS
# =============================================================================

def invalidate_member_related_caches(member_id):
    """
    Invalidate all caches related to a member
    
    Args:
        member_id (str): Member ID
    """
    from sacco_management.sacco.utils.performance import invalidate_member_cache
    
    invalidate_member_cache(member_id)
    
    # Also invalidate aggregate caches
    frappe.cache().delete("stats:active_members")
    frappe.cache().delete(get_member_statistics_cached.__name__)


def invalidate_loan_related_caches():
    """Invalidate all loan-related caches"""
    patterns = [
        "get_loan_portfolio_stats",
        "get_monthly_disbursement_trend",
        "loan:*"
    ]
    
    for pattern in patterns:
        keys = frappe.cache().get_keys(pattern)
        for key in keys:
            frappe.cache().delete(key)


def clear_all_sacco_caches():
    """Clear all SACCO management caches"""
    patterns = [
        "sacco_cache:*",
        "member:*",
        "loan:*",
        "savings:*",
        "shares:*",
        "get_*"
    ]
    
    cleared = 0
    for pattern in patterns:
        keys = frappe.cache().get_keys(pattern)
        for key in keys:
            frappe.cache().delete(key)
            cleared += 1
    
    return {"cleared_keys": cleared}


# =============================================================================
# SCHEDULER JOBS FOR CACHE MANAGEMENT
# =============================================================================

def scheduled_cache_warming():
    """
    Scheduled job to warm up caches (run daily)
    """
    print("Starting cache warming...")
    
    # Warm up member statistics
    get_member_statistics_cached()
    
    # Warm up loan portfolio
    get_loan_portfolio_stats()
    
    # Warm up savings summary
    get_total_savings_by_type()
    
    # Warm up share capital
    get_share_capital_summary_cached()
    
    # Warm up dashboard
    get_optimized_dashboard_data()
    
    print("Cache warming completed!")


def scheduled_cache_cleanup():
    """
    Scheduled job to cleanup old caches (run weekly)
    """
    print("Starting cache cleanup...")
    
    # Clear all caches older than TTL (Redis handles this automatically)
    # But we can force cleanup if needed
    clear_all_sacco_caches()
    
    print("Cache cleanup completed!")
