# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, date_diff


def execute(filters=None):
    """Advanced Member Analytics Report - Comprehensive member insights"""
    
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_member_data(filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart


def get_columns():
    """Define report columns"""
    return [
        {"label": _("Member"), "fieldname": "member", "fieldtype": "Link", "options": "SACCO Member", "width": 150},
        {"label": _("Member Name"), "fieldname": "member_name", "fieldtype": "Data", "width": 200},
        {"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 120},
        {"label": _("Membership Type"), "fieldname": "membership_type", "fieldtype": "Data", "width": 120},
        
        # Membership Details
        {"label": _("Joining Date"), "fieldname": "joining_date", "fieldtype": "Date", "width": 110},
        {"label": _("Years as Member"), "fieldname": "years_as_member", "fieldtype": "Float", "width": 120},
        
        # Savings Profile
        {"label": _("Savings Balance"), "fieldname": "savings_balance", "fieldtype": "Currency", "width": 130},
        {"label": _("Avg Monthly Savings"), "fieldname": "avg_monthly_savings", "fieldtype": "Currency", "width": 140},
        
        # Share Capital
        {"label": _("Share Capital"), "fieldname": "share_capital", "fieldtype": "Currency", "width": 130},
        {"label": _("Shares Held"), "fieldname": "shares_held", "fieldtype": "Int", "width": 110},
        
        # Loan Profile
        {"label": _("Total Loans Taken"), "fieldname": "total_loans_taken", "fieldtype": "Int", "width": 120},
        {"label": _("Active Loans"), "fieldname": "active_loans", "fieldtype": "Int", "width": 110},
        {"label": _("Outstanding Amount"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 140},
        {"label": _("Loan Repayment Rate %"), "fieldname": "loan_repayment_rate", "fieldtype": "Percent", "width": 150},
        
        # Contribution Profile
        {"label": _("Total Contributions"), "fieldname": "total_contributions", "fieldtype": "Currency", "width": 140},
        {"label": _("Contribution Consistency %"), "fieldname": "contribution_consistency", "fieldtype": "Percent", "width": 160},
        
        # Risk & Engagement
        {"label": _("Credit Score"), "fieldname": "credit_score", "fieldtype": "Int", "width": 110},
        {"label": _("Risk Category"), "fieldname": "risk_category", "fieldtype": "Data", "width": 120},
        {"label": _("Engagement Score"), "fieldname": "engagement_score", "fieldtype": "Float", "width": 130},
    ]


def get_member_data(filters):
    """Get comprehensive member analytics"""
    branch = filters.get("branch")
    membership_type = filters.get("membership_type")
    min_joining_date = filters.get("min_joining_date")
    
    conditions = "WHERE m.docstatus = 1"
    if branch:
        conditions += f" AND m.branch = '{branch}'"
    if membership_type:
        conditions += f" AND m.membership_type = '{membership_type}'"
    if min_joining_date:
        conditions += f" AND m.joining_date <= '{min_joining_date}'"
    
    members = frappe.db.sql(f"""
        SELECT 
            m.name as member,
            m.member_name,
            m.branch,
            m.membership_type,
            m.joining_date
        FROM `tabSACCO Member` m
        {conditions}
        ORDER BY m.joining_date DESC
    """, as_dict=True)
    
    data = []
    
    for member in members:
        member_data = get_member_analytics(member)
        data.append(member_data)
    
    return data


def get_member_analytics(member):
    """Get comprehensive analytics for a single member"""
    
    # Calculate years as member
    joining_date = member.joining_date or nowdate()
    years_as_member = flt(date_diff(nowdate(), joining_date)) / 365.25
    
    # Get savings data
    savings_balance, avg_monthly_savings = get_savings_stats(member.member)
    
    # Get share capital data
    share_capital, shares_held = get_share_capital_stats(member.member)
    
    # Get loan data
    total_loans_taken, active_loans, outstanding_amount, repayment_rate = get_loan_stats(member.member)
    
    # Get contribution data
    total_contributions, consistency = get_contribution_stats(member.member)
    
    # Calculate credit score (simple algorithm)
    credit_score = calculate_credit_score(member.member, repayment_rate, consistency)
    
    # Determine risk category
    risk_category = determine_risk_category(credit_score, outstanding_amount, repayment_rate)
    
    # Calculate engagement score
    engagement_score = calculate_engagement_score(member.member, years_as_member, total_loans_taken, total_contributions)
    
    return {
        "member": member.member,
        "member_name": member.member_name,
        "branch": member.branch,
        "membership_type": member.membership_type,
        "joining_date": joining_date,
        "years_as_member": flt(years_as_member, 1),
        "savings_balance": flt(savings_balance, 2),
        "avg_monthly_savings": flt(avg_monthly_savings, 2),
        "share_capital": flt(share_capital, 2),
        "shares_held": shares_held,
        "total_loans_taken": total_loans_taken,
        "active_loans": active_loans,
        "outstanding_amount": flt(outstanding_amount, 2),
        "loan_repayment_rate": flt(repayment_rate / 100, 4),  # Convert to decimal for Percent field
        "total_contributions": flt(total_contributions, 2),
        "contribution_consistency": flt(consistency / 100, 4),  # Convert to decimal for Percent field
        "credit_score": credit_score,
        "risk_category": risk_category,
        "engagement_score": flt(engagement_score, 2),
    }


def get_savings_stats(member):
    """Get savings statistics"""
    result = frappe.db.sql("""
        SELECT 
            COALESCE(SUM(sa.current_balance), 0),
            COALESCE(AVG(sd.amount), 0)
        FROM `tabSavings Account` sa
        LEFT JOIN `tabSavings Deposit` sd ON sa.name = sd.savings_account AND sd.docstatus = 1
        WHERE sa.member = %s
        AND sa.docstatus = 1
        AND sa.status = 'Active'
    """, (member,))
    
    result = result[0] if result else (0, 0)
    return result[0] or 0, result[1] or 0


def get_share_capital_stats(member):
    """Get share capital statistics"""
    result = frappe.db.sql("""
        SELECT 
            COALESCE(SUM(sa.total_amount), 0),
            COALESCE(SUM(sa.quantity), 0)
        FROM `tabShare Allocation` sa
        WHERE sa.member = %s
        AND sa.docstatus = 1
        AND sa.status = 'Allocated'
    """, (member,))
    
    result = result[0] if result else (0, 0)
    return result[0] or 0, result[1] or 0


def get_loan_stats(member):
    """Get loan statistics"""
    # Total loans taken
    total_loans = frappe.db.sql("""
        SELECT COUNT(*)
        FROM `tabLoan Application`
        WHERE member = %s
        AND docstatus = 1
    """, (member,))[0][0] or 0
    
    # Active loans
    active_loans = frappe.db.sql("""
        SELECT COUNT(*)
        FROM `tabLoan Application`
        WHERE member = %s
        AND docstatus = 1
        AND status IN ('Approved', 'Disbursed', 'Active')
    """, (member,))[0][0] or 0
    
    # Outstanding amount
    outstanding = frappe.db.sql("""
        SELECT COALESCE(SUM(outstanding_principal), 0)
        FROM `tabLoan Application`
        WHERE member = %s
        AND docstatus = 1
        AND status IN ('Approved', 'Disbursed', 'Active')
    """, (member,))[0][0] or 0
    
    # Calculate repayment rate
    total_repaid = frappe.db.sql("""
        SELECT COALESCE(SUM(principal_paid), 0)
        FROM `tabLoan Repayment` lr
        INNER JOIN `tabLoan Application` la ON lr.loan_application = la.name
        WHERE la.member = %s
        AND lr.docstatus = 1
    """, (member,))[0][0] or 0
    
    total_disbursed = frappe.db.sql("""
        SELECT COALESCE(SUM(amount_requested), 0)
        FROM `tabLoan Application`
        WHERE member = %s
        AND docstatus = 1
    """, (member,))[0][0] or 0
    
    repayment_rate = (total_repaid / total_disbursed * 100) if total_disbursed > 0 else 0
    
    return total_loans, active_loans, outstanding, repayment_rate


def get_contribution_stats(member):
    """Get contribution statistics"""
    # Total contributions
    total = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0)
        FROM `tabMember Contribution`
        WHERE member = %s
        AND docstatus = 1
    """, (member,))[0][0] or 0
    
    # Calculate consistency (months contributed vs expected months)
    member_since = frappe.db.get_value("SACCO Member", member, "joining_date")
    if member_since:
        months_as_member = date_diff(nowdate(), member_since) / 30.44
        months_contributed = frappe.db.sql("""
            SELECT COUNT(DISTINCT DATE_FORMAT(posting_date, '%Y-%m'))
            FROM `tabMember Contribution`
            WHERE member = %s
            AND docstatus = 1
        """, (member,))[0][0] or 0
        
        consistency = (months_contributed / months_as_member * 100) if months_as_member > 0 else 0
    else:
        consistency = 0
    
    return total, consistency


def calculate_credit_score(member, repayment_rate, contribution_consistency):
    """Calculate simple credit score (0-100)"""
    # Base score
    score = 50
    
    # Repayment history (up to +30 points)
    score += (repayment_rate / 100) * 30
    
    # Contribution consistency (up to +20 points)
    score += (contribution_consistency / 100) * 20
    
    # Years as member bonus (up to +10 points)
    years = frappe.db.sql("""
        SELECT TIMESTAMPDIFF(YEAR, joining_date, CURDATE())
        FROM `tabSACCO Member`
        WHERE name = %s
    """, (member,))[0][0] or 0
    score += min(years, 10)
    
    return min(int(score), 100)  # Cap at 100


def determine_risk_category(credit_score, outstanding, repayment_rate):
    """Determine member risk category"""
    if credit_score >= 80:
        return "Low Risk"
    elif credit_score >= 60:
        return "Medium Risk"
    elif credit_score >= 40:
        return "High Risk"
    else:
        return "Very High Risk"


def calculate_engagement_score(member, years, total_loans, total_contributions):
    """Calculate member engagement score (0-10)"""
    score = 0
    
    # Tenure score (up to 2 points)
    score += min(years / 5, 2)
    
    # Loan activity score (up to 3 points)
    score += min(total_loans / 3, 3)
    
    # Contribution score (up to 3 points)
    if total_contributions > 0:
        score += 3
    
    # Meeting attendance score (up to 2 points)
    meetings_attended = frappe.db.sql("""
        SELECT COUNT(*)
        FROM `tabMeeting Register`
        WHERE member = %s
        AND attendance_status = 'Present'
    """, (member,))[0][0] or 0
    score += min(meetings_attended / 10, 2)
    
    return min(score, 10)


def get_chart_data(data):
    """Create chart visualization"""
    if not data:
        return None
    
    # Top 10 members by engagement
    sorted_data = sorted(data, key=lambda x: x['engagement_score'], reverse=True)[:10]
    
    chart = {
        "data": {
            "labels": [d["member_name"][:20] for d in sorted_data],
            "datasets": [
                {
                    "name": "Engagement Score",
                    "values": [d["engagement_score"] for d in sorted_data],
                    "chartType": "bar"
                }
            ]
        },
        "type": "bar",
        "colors": ["#4CAF50"],
        "tooltipOptions": {
            "formatTooltipY": lambda x: f"{x:.2f}"
        }
    }
    
    return chart
