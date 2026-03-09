"""
Weekly Scheduled Tasks for SACCO Management System
"""

import frappe
from frappe.utils import nowdate, getdate, add_days


def generate_weekly_reports():
    """
    Generate weekly summary reports for branch managers
    """
    from frappe.utils import get_first_day_of_week, get_last_day_of_week
    
    today = getdate(nowdate())
    week_start = get_first_day_of_week(today)
    week_end = get_last_day_of_week(today)
    
    # Get all branches
    branches = frappe.get_all("Branch", filters={"is_active": 1}, pluck="name")
    
    for branch in branches:
        try:
            # Get week statistics
            stats = get_branch_weekly_stats(branch, week_start, week_end)
            
            # Get branch manager
            manager_email = frappe.db.get_value("Branch", branch, "email")
            
            if manager_email:
                # Send weekly report email
                frappe.sendmail(
                    recipients=[manager_email],
                    subject=f"SACCO Weekly Report - {branch} ({week_start} to {week_end})",
                    message=format_weekly_report(branch, stats, week_start, week_end)
                )
                
        except Exception as e:
            frappe.log_error(
                message=str(e),
                title=f"Error generating weekly report for {branch}"
            )
    
    return len(branches)


def get_branch_weekly_stats(branch, from_date, to_date):
    """Get weekly statistics for a branch"""
    
    # New members
    new_members = frappe.db.count("SACCO Member", {
        "branch": branch,
        "join_date": ["between", [from_date, to_date]]
    })
    
    # Contributions
    contributions = frappe.db.sql("""
        SELECT COALESCE(SUM(mc.amount), 0) as total
        FROM `tabMember Contribution` mc
        INNER JOIN `tabSACCO Member` sm ON mc.member = sm.name
        WHERE sm.branch = %s AND mc.docstatus = 1
        AND mc.contribution_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0] or 0
    
    # Loans disbursed
    loans_disbursed = frappe.db.sql("""
        SELECT COALESCE(SUM(la.disbursed_amount), 0) as total
        FROM `tabLoan Application` la
        INNER JOIN `tabSACCO Member` sm ON la.member = sm.name
        WHERE sm.branch = %s AND la.docstatus = 1
        AND la.disbursement_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0] or 0
    
    # Loan repayments
    repayments = frappe.db.sql("""
        SELECT COALESCE(SUM(lr.amount_paid), 0) as total
        FROM `tabLoan Repayment` lr
        INNER JOIN `tabSACCO Member` sm ON lr.member = sm.name
        WHERE sm.branch = %s AND lr.docstatus = 1
        AND lr.payment_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0] or 0
    
    return {
        "new_members": new_members,
        "contributions": contributions,
        "loans_disbursed": loans_disbursed,
        "repayments": repayments
    }


def format_weekly_report(branch, stats, from_date, to_date):
    """Format weekly report email content"""
    return f"""
    <h2>SACCO Weekly Summary Report</h2>
    <p><strong>Branch:</strong> {branch}</p>
    <p><strong>Period:</strong> {from_date} to {to_date}</p>
    
    <h3>Summary</h3>
    <table border="1" cellpadding="10">
        <tr><td>New Members</td><td>{stats['new_members']}</td></tr>
        <tr><td>Total Contributions</td><td>{stats['contributions']:,.2f}</td></tr>
        <tr><td>Loans Disbursed</td><td>{stats['loans_disbursed']:,.2f}</td></tr>
        <tr><td>Loan Repayments</td><td>{stats['repayments']:,.2f}</td></tr>
    </table>
    
    <p>This is an automated weekly report from SACCO Management System.</p>
    """
