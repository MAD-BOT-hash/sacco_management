"""
Monthly Scheduled Tasks for SACCO Management System

These tasks run monthly via Frappe scheduler:
- Calculate and post interest on savings accounts
- Generate monthly statements for members
- Process savings interest posting for all eligible accounts
- Accrue loan interest for the month
"""

import frappe
from frappe import _
from frappe.utils import nowdate, getdate, add_months, get_first_day, get_last_day, flt


def process_savings_interest_posting():
    """
    Process monthly interest posting for all savings accounts
    This calculates and posts interest to member savings accounts
    """
    from sacco_management.sacco.utils.savings_utils import process_monthly_interest
    
    try:
        stats = process_monthly_interest()
        
        frappe.log_error(
            message=f"Monthly Interest Posting Complete: {stats['processed']}/{stats['total_accounts']} accounts, Total Interest: {stats['total_interest_posted']}",
            title="Monthly Savings Interest Posting"
        )
        
        return stats
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title="Error in Monthly Savings Interest Posting"
        )
        raise


def accrue_monthly_loan_interest():
    """
    Accrue interest on all active loans for the month
    This runs at month-end to ensure proper accounting accruals
    """
    from sacco_management.sacco.utils.loan_utils import process_loan_interest_accrual
    
    today = getdate(nowdate())
    month_start = get_first_day(today)
    month_end = get_last_day(today)
    
    try:
        # Process accrual for all active loans
        stats = process_loan_interest_accrual()
        
        frappe.log_error(
            message=f"Monthly Loan Interest Accrual Complete: {stats['processed']} loans, Total: {stats['total_accrued']}",
            title="Monthly Loan Interest Accrual"
        )
        
        return stats
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title="Error in Monthly Loan Interest Accrual"
        )
        raise


def calculate_interest_on_savings():
    """
    Calculate and post interest on member savings
    Runs monthly on the last day of each month
    """
    today = getdate(nowdate())
    month_start = get_first_day(today)
    month_end = get_last_day(today)
    
    # Get contribution types with interest
    interest_types = frappe.get_all(
        "Contribution Type",
        filters={"interest_applicable": 1, "is_active": 1},
        fields=["name", "interest_rate", "interest_calculation_method"]
    )
    
    interest_posted = 0
    
    for contrib_type in interest_types:
        # Get members with this contribution type
        members_with_savings = frappe.db.sql("""
            SELECT 
                mc.member,
                sm.member_name,
                SUM(mc.amount) as total_savings
            FROM `tabMember Contribution` mc
            INNER JOIN `tabSACCO Member` sm ON mc.member = sm.name
            WHERE mc.contribution_type = %s 
            AND mc.docstatus = 1
            AND sm.status = 'Active'
            GROUP BY mc.member
            HAVING total_savings > 0
        """, contrib_type.name, as_dict=True)
        
        for member in members_with_savings:
            try:
                # Calculate monthly interest
                annual_rate = flt(contrib_type.interest_rate)
                monthly_rate = annual_rate / 12 / 100
                interest_amount = flt(member.total_savings) * monthly_rate
                
                if interest_amount > 0:
                    # Create interest contribution
                    interest_contrib = frappe.new_doc("Member Contribution")
                    interest_contrib.member = member.member
                    interest_contrib.contribution_type = contrib_type.name
                    interest_contrib.amount = interest_amount
                    interest_contrib.contribution_date = month_end
                    interest_contrib.payment_mode = "Cash"  # System entry
                    interest_contrib.remarks = f"Interest for {month_start.strftime('%B %Y')} @ {annual_rate}% p.a."
                    interest_contrib.insert(ignore_permissions=True)
                    interest_contrib.submit()
                    
                    interest_posted += 1
                    
            except Exception as e:
                frappe.log_error(
                    message=str(e),
                    title=f"Error posting interest for {member.member}"
                )
    
    frappe.db.commit()
    return interest_posted


def generate_monthly_statements():
    """
    Generate and email monthly statements to all active members
    """
    today = getdate(nowdate())
    prev_month_end = get_first_day(today) - 1
    prev_month_start = get_first_day(prev_month_end)
    
    # Get all active members with email
    members = frappe.get_all(
        "SACCO Member",
        filters={"status": "Active", "email": ["is", "set"]},
        fields=["name", "member_name", "email"]
    )
    
    statements_sent = 0
    
    for member in members:
        try:
            statement = generate_member_statement(
                member.name, 
                prev_month_start, 
                prev_month_end
            )
            
            if statement and member.email:
                frappe.sendmail(
                    recipients=[member.email],
                    subject=f"SACCO Monthly Statement - {prev_month_start.strftime('%B %Y')}",
                    message=format_monthly_statement(member, statement, prev_month_start, prev_month_end)
                )
                statements_sent += 1
                
        except Exception as e:
            frappe.log_error(
                message=str(e),
                title=f"Error generating statement for {member.name}"
            )
    
    return statements_sent


def generate_member_statement(member, from_date, to_date):
    """Generate statement data for a member"""
    
    # Opening balances
    opening = get_member_balances_as_of(member, from_date)
    
    # Transactions during period
    contributions = frappe.db.sql("""
        SELECT contribution_date as date, contribution_type as description, amount
        FROM `tabMember Contribution`
        WHERE member = %s AND docstatus = 1
        AND contribution_date BETWEEN %s AND %s
        ORDER BY contribution_date
    """, (member, from_date, to_date), as_dict=True)
    
    loan_disbursements = frappe.db.sql("""
        SELECT disbursement_date as date, 
               CONCAT('Loan Disbursement - ', loan_type) as description,
               disbursed_amount as amount
        FROM `tabLoan Application`
        WHERE member = %s AND docstatus = 1
        AND disbursement_date BETWEEN %s AND %s
    """, (member, from_date, to_date), as_dict=True)
    
    loan_repayments = frappe.db.sql("""
        SELECT payment_date as date,
               CONCAT('Loan Repayment - ', loan) as description,
               amount_paid as amount
        FROM `tabLoan Repayment`
        WHERE member = %s AND docstatus = 1
        AND payment_date BETWEEN %s AND %s
    """, (member, from_date, to_date), as_dict=True)
    
    # Closing balances
    closing = get_member_balances_as_of(member, to_date)
    
    return {
        "opening": opening,
        "contributions": contributions,
        "loan_disbursements": loan_disbursements,
        "loan_repayments": loan_repayments,
        "closing": closing
    }


def get_member_balances_as_of(member, as_of_date):
    """Get member balances as of a specific date"""
    
    contributions = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0)
        FROM `tabMember Contribution`
        WHERE member = %s AND docstatus = 1 AND contribution_date <= %s
    """, (member, as_of_date))[0][0] or 0
    
    shares = frappe.db.sql("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM `tabShare Allocation`
        WHERE member = %s AND docstatus = 1 AND status = 'Allocated'
        AND allocation_date <= %s
    """, (member, as_of_date))[0][0] or 0
    
    loans_outstanding = frappe.db.sql("""
        SELECT COALESCE(SUM(outstanding_amount), 0)
        FROM `tabLoan Application`
        WHERE member = %s AND docstatus = 1 
        AND status IN ('Disbursed', 'Active')
        AND disbursement_date <= %s
    """, (member, as_of_date))[0][0] or 0
    
    return {
        "contributions": contributions,
        "shares": shares,
        "loans_outstanding": loans_outstanding
    }


def format_monthly_statement(member, statement, from_date, to_date):
    """Format monthly statement email content"""
    return f"""
    <h2>SACCO Monthly Statement</h2>
    <p><strong>Member:</strong> {member.member_name}</p>
    <p><strong>Period:</strong> {from_date.strftime('%B %Y')}</p>
    
    <h3>Opening Balances</h3>
    <table border="1" cellpadding="5">
        <tr><td>Total Contributions</td><td>{statement['opening']['contributions']:,.2f}</td></tr>
        <tr><td>Share Value</td><td>{statement['opening']['shares']:,.2f}</td></tr>
        <tr><td>Loan Outstanding</td><td>{statement['opening']['loans_outstanding']:,.2f}</td></tr>
    </table>
    
    <h3>Transactions</h3>
    <p><strong>Contributions:</strong> {len(statement['contributions'])} transactions</p>
    <p><strong>Loan Disbursements:</strong> {len(statement['loan_disbursements'])} transactions</p>
    <p><strong>Loan Repayments:</strong> {len(statement['loan_repayments'])} transactions</p>
    
    <h3>Closing Balances</h3>
    <table border="1" cellpadding="5">
        <tr><td>Total Contributions</td><td>{statement['closing']['contributions']:,.2f}</td></tr>
        <tr><td>Share Value</td><td>{statement['closing']['shares']:,.2f}</td></tr>
        <tr><td>Loan Outstanding</td><td>{statement['closing']['loans_outstanding']:,.2f}</td></tr>
    </table>
    
    <p>For detailed transactions, please visit the SACCO office or portal.</p>
    <p>This is an automated statement from SACCO Management System.</p>
    """
