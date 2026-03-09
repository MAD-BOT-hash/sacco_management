"""
GL Utilities for SACCO Management System

This module provides utility functions for posting transactions to the General Ledger.
All financial transactions in the SACCO system are posted through these utilities
to ensure double-entry accounting integrity.

Transaction Flow:
- Contributions → GL (Debit: Cash/Bank, Credit: Member Savings Liability)
- Loan Disbursement → GL (Debit: Loans Receivable, Credit: Cash/Bank)
- Loan Repayment → GL (Debit: Cash/Bank, Credit: Loans Receivable + Interest Income)
- Share Allocation → GL (Debit: Cash/Bank, Credit: Share Capital)
- Dividend Payment → GL (Debit: Dividend Expense, Credit: Cash/Bank)
- Fines → GL (Debit: Fines Receivable, Credit: Fine Income)
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def get_gl_account(account_name=None, account_number=None):
    """
    Get GL account by name or number
    
    Args:
        account_name: Name of the account
        account_number: Account number
        
    Returns:
        GL Account name (docname)
    """
    filters = {}
    if account_name:
        filters["account_name"] = account_name
    if account_number:
        filters["account_number"] = account_number
        
    return frappe.db.get_value("SACCO GL Account", filters, "name")


def get_payment_mode_account(payment_mode):
    """
    Get GL account for a payment mode
    
    Args:
        payment_mode: Payment Mode docname
        
    Returns:
        GL Account name
    """
    return frappe.db.get_value("Payment Mode", payment_mode, "gl_account")


def create_gl_entry(
    voucher_type,
    posting_date,
    accounts,
    remarks=None,
    reference_type=None,
    reference_name=None,
    branch=None,
    submit=True
):
    """
    Create a GL entry (Journal Entry) for a transaction
    
    Args:
        voucher_type: Type of voucher (Receipt Voucher, Payment Voucher, Journal Entry)
        posting_date: Date of the entry
        accounts: List of account entries, each with:
            - gl_account: GL Account name (required)
            - debit: Debit amount (default 0)
            - credit: Credit amount (default 0)
            - party_type: DocType for party (optional)
            - party: Party docname (optional)
            - remarks: Line remarks (optional)
        remarks: Overall remarks for the entry
        reference_type: Source DocType
        reference_name: Source document name
        branch: Branch for the entry
        submit: Whether to submit (default True)
        
    Returns:
        Journal Entry document
        
    Raises:
        frappe.ValidationError: If debits don't equal credits
    """
    # Validate totals
    total_debit = sum(flt(acc.get("debit", 0)) for acc in accounts)
    total_credit = sum(flt(acc.get("credit", 0)) for acc in accounts)
    
    if flt(total_debit, 2) != flt(total_credit, 2):
        frappe.throw(
            _("Total Debit ({0}) must equal Total Credit ({1})").format(
                total_debit, total_credit
            )
        )
    
    je = frappe.new_doc("SACCO Journal Entry")
    je.voucher_type = voucher_type
    je.posting_date = posting_date or nowdate()
    je.remarks = remarks
    je.reference_type = reference_type
    je.reference_name = reference_name
    je.branch = branch
    je.is_system_generated = 1
    
    for acc in accounts:
        je.append("accounts", {
            "gl_account": acc.get("gl_account"),
            "debit": flt(acc.get("debit", 0)),
            "credit": flt(acc.get("credit", 0)),
            "party_type": acc.get("party_type"),
            "party": acc.get("party"),
            "reference_type": acc.get("reference_type") or reference_type,
            "reference_name": acc.get("reference_name") or reference_name,
            "remarks": acc.get("remarks")
        })
    
    je.insert(ignore_permissions=True)
    
    if submit:
        je.submit()
    
    return je


def reverse_gl_entry(reference_type, reference_name, posting_date=None):
    """
    Reverse a GL entry by creating an opposite entry
    
    Args:
        reference_type: Original document type
        reference_name: Original document name
        posting_date: Date for reversal (default today)
        
    Returns:
        Reversal Journal Entry document or None if no entry found
    """
    # Find original journal entries
    original_entries = frappe.get_all(
        "SACCO Journal Entry",
        filters={
            "reference_type": reference_type,
            "reference_name": reference_name,
            "docstatus": 1
        },
        fields=["name"]
    )
    
    if not original_entries:
        return None
        
    reversal_entries = []
    
    for entry in original_entries:
        original = frappe.get_doc("SACCO Journal Entry", entry.name)
        
        # Create reversal accounts (swap debit and credit)
        reversal_accounts = []
        for row in original.accounts:
            reversal_accounts.append({
                "gl_account": row.gl_account,
                "debit": row.credit,  # Swap
                "credit": row.debit,  # Swap
                "party_type": row.party_type,
                "party": row.party,
                "remarks": f"Reversal of {original.name}"
            })
        
        # Create reversal entry
        reversal = create_gl_entry(
            voucher_type=original.voucher_type,
            posting_date=posting_date or nowdate(),
            accounts=reversal_accounts,
            remarks=f"Reversal of {original.name} for {reference_type} {reference_name}",
            reference_type=reference_type,
            reference_name=reference_name,
            branch=original.branch,
            submit=True
        )
        
        reversal_entries.append(reversal)
    
    return reversal_entries


def post_contribution_to_gl(contribution_doc):
    """
    Post a member contribution to GL
    
    Double Entry:
    - Debit: Payment Mode GL Account (Cash/Bank)
    - Credit: Contribution Type GL Account (Member Savings/Deposits)
    
    Args:
        contribution_doc: Member Contribution document
        
    Returns:
        Journal Entry document
    """
    # Get accounts
    payment_account = get_payment_mode_account(contribution_doc.payment_mode)
    contribution_account = frappe.db.get_value(
        "Contribution Type", 
        contribution_doc.contribution_type, 
        "default_gl_account"
    )
    
    if not payment_account:
        frappe.throw(_("Payment Mode {0} does not have a GL Account configured").format(
            contribution_doc.payment_mode
        ))
        
    if not contribution_account:
        frappe.throw(_("Contribution Type {0} does not have a GL Account configured").format(
            contribution_doc.contribution_type
        ))
    
    # Get member branch
    branch = frappe.db.get_value("SACCO Member", contribution_doc.member, "branch")
    
    accounts = [
        {
            "gl_account": payment_account,
            "debit": contribution_doc.amount,
            "credit": 0,
            "party_type": "SACCO Member",
            "party": contribution_doc.member,
            "remarks": f"Contribution from {contribution_doc.member_name}"
        },
        {
            "gl_account": contribution_account,
            "debit": 0,
            "credit": contribution_doc.amount,
            "party_type": "SACCO Member",
            "party": contribution_doc.member,
            "remarks": f"{contribution_doc.contribution_type} - {contribution_doc.member_name}"
        }
    ]
    
    return create_gl_entry(
        voucher_type="Receipt Voucher",
        posting_date=contribution_doc.contribution_date,
        accounts=accounts,
        remarks=f"Member Contribution: {contribution_doc.contribution_type} - {contribution_doc.member_name}",
        reference_type="Member Contribution",
        reference_name=contribution_doc.name,
        branch=branch
    )


def post_loan_disbursement_to_gl(loan_doc):
    """
    Post loan disbursement to GL
    
    Double Entry:
    - Debit: Loans Receivable
    - Credit: Payment Mode Account (Cash/Bank)
    
    If processing fee:
    - Debit: Payment Mode Account
    - Credit: Processing Fee Income
    
    Args:
        loan_doc: Loan Application document
        
    Returns:
        List of Journal Entry documents
    """
    entries = []
    
    # Get accounts
    loan_account = frappe.db.get_value("Loan Type", loan_doc.loan_type, "default_gl_account")
    payment_account = get_payment_mode_account(loan_doc.disbursement_mode)
    
    if not loan_account:
        frappe.throw(_("Loan Type {0} does not have a GL Account configured").format(
            loan_doc.loan_type
        ))
        
    if not payment_account:
        frappe.throw(_("Payment Mode {0} does not have a GL Account configured").format(
            loan_doc.disbursement_mode
        ))
    
    # Get member branch
    branch = frappe.db.get_value("SACCO Member", loan_doc.member, "branch")
    
    # Main disbursement entry
    accounts = [
        {
            "gl_account": loan_account,
            "debit": loan_doc.disbursed_amount,
            "credit": 0,
            "party_type": "SACCO Member",
            "party": loan_doc.member,
            "remarks": f"Loan disbursement to {loan_doc.member_name}"
        },
        {
            "gl_account": payment_account,
            "debit": 0,
            "credit": loan_doc.disbursed_amount,
            "party_type": "SACCO Member",
            "party": loan_doc.member,
            "remarks": f"Loan disbursement - {loan_doc.loan_type}"
        }
    ]
    
    je = create_gl_entry(
        voucher_type="Payment Voucher",
        posting_date=loan_doc.disbursement_date,
        accounts=accounts,
        remarks=f"Loan Disbursement: {loan_doc.loan_type} - {loan_doc.member_name}",
        reference_type="Loan Application",
        reference_name=loan_doc.name,
        branch=branch
    )
    entries.append(je)
    
    # Processing fee entry (if applicable)
    if flt(loan_doc.processing_fee) > 0:
        processing_fee_account = get_gl_account(account_name="Processing Fee Income")
        
        if processing_fee_account:
            fee_accounts = [
                {
                    "gl_account": payment_account,
                    "debit": loan_doc.processing_fee,
                    "credit": 0,
                    "party_type": "SACCO Member",
                    "party": loan_doc.member,
                    "remarks": f"Processing fee from {loan_doc.member_name}"
                },
                {
                    "gl_account": processing_fee_account,
                    "debit": 0,
                    "credit": loan_doc.processing_fee,
                    "party_type": "SACCO Member",
                    "party": loan_doc.member,
                    "remarks": f"Processing fee - {loan_doc.loan_type}"
                }
            ]
            
            fee_je = create_gl_entry(
                voucher_type="Receipt Voucher",
                posting_date=loan_doc.disbursement_date,
                accounts=fee_accounts,
                remarks=f"Loan Processing Fee: {loan_doc.loan_type} - {loan_doc.member_name}",
                reference_type="Loan Application",
                reference_name=loan_doc.name,
                branch=branch
            )
            entries.append(fee_je)
    
    return entries


def post_loan_repayment_to_gl(repayment_doc):
    """
    Post loan repayment to GL
    
    Double Entry:
    - Debit: Payment Mode Account (Cash/Bank)
    - Credit: Loans Receivable (Principal)
    - Credit: Interest Income (Interest)
    - Credit: Penalty Income (Penalty, if any)
    
    Args:
        repayment_doc: Loan Repayment document
        
    Returns:
        Journal Entry document
    """
    # Get loan details
    loan = frappe.get_doc("Loan Application", repayment_doc.loan)
    loan_account = frappe.db.get_value("Loan Type", loan.loan_type, "default_gl_account")
    payment_account = get_payment_mode_account(repayment_doc.payment_mode)
    interest_account = get_gl_account(account_name="Loan Interest Income")
    penalty_account = get_gl_account(account_name="Penalty Income")
    
    if not loan_account:
        frappe.throw(_("Loan Type does not have a GL Account configured"))
        
    if not payment_account:
        frappe.throw(_("Payment Mode does not have a GL Account configured"))
    
    # Get member branch
    branch = frappe.db.get_value("SACCO Member", repayment_doc.member, "branch")
    
    accounts = [
        {
            "gl_account": payment_account,
            "debit": repayment_doc.amount_paid,
            "credit": 0,
            "party_type": "SACCO Member",
            "party": repayment_doc.member,
            "remarks": f"Loan repayment from {repayment_doc.member_name}"
        }
    ]
    
    # Principal portion
    if flt(repayment_doc.principal_paid) > 0:
        accounts.append({
            "gl_account": loan_account,
            "debit": 0,
            "credit": repayment_doc.principal_paid,
            "party_type": "SACCO Member",
            "party": repayment_doc.member,
            "remarks": f"Principal repayment"
        })
    
    # Interest portion
    if flt(repayment_doc.interest_paid) > 0 and interest_account:
        accounts.append({
            "gl_account": interest_account,
            "debit": 0,
            "credit": repayment_doc.interest_paid,
            "party_type": "SACCO Member",
            "party": repayment_doc.member,
            "remarks": f"Interest payment"
        })
    
    # Penalty portion
    if flt(repayment_doc.penalty_paid) > 0 and penalty_account:
        accounts.append({
            "gl_account": penalty_account,
            "debit": 0,
            "credit": repayment_doc.penalty_paid,
            "party_type": "SACCO Member",
            "party": repayment_doc.member,
            "remarks": f"Penalty payment"
        })
    
    return create_gl_entry(
        voucher_type="Receipt Voucher",
        posting_date=repayment_doc.payment_date,
        accounts=accounts,
        remarks=f"Loan Repayment: {loan.loan_type} - {repayment_doc.member_name}",
        reference_type="Loan Repayment",
        reference_name=repayment_doc.name,
        branch=branch
    )


def post_share_allocation_to_gl(share_doc):
    """
    Post share allocation to GL
    
    Double Entry:
    - Debit: Payment Mode Account (Cash/Bank)
    - Credit: Share Capital
    
    Args:
        share_doc: Share Allocation document
        
    Returns:
        Journal Entry document
    """
    share_account = frappe.db.get_value("Share Type", share_doc.share_type, "default_gl_account")
    payment_account = get_payment_mode_account(share_doc.payment_mode)
    
    if not share_account:
        frappe.throw(_("Share Type {0} does not have a GL Account configured").format(
            share_doc.share_type
        ))
        
    if not payment_account:
        frappe.throw(_("Payment Mode {0} does not have a GL Account configured").format(
            share_doc.payment_mode
        ))
    
    # Get member branch
    branch = frappe.db.get_value("SACCO Member", share_doc.member, "branch")
    
    accounts = [
        {
            "gl_account": payment_account,
            "debit": share_doc.total_amount,
            "credit": 0,
            "party_type": "SACCO Member",
            "party": share_doc.member,
            "remarks": f"Share purchase from {share_doc.member_name}"
        },
        {
            "gl_account": share_account,
            "debit": 0,
            "credit": share_doc.total_amount,
            "party_type": "SACCO Member",
            "party": share_doc.member,
            "remarks": f"{share_doc.quantity} {share_doc.share_type} shares"
        }
    ]
    
    return create_gl_entry(
        voucher_type="Receipt Voucher",
        posting_date=share_doc.allocation_date,
        accounts=accounts,
        remarks=f"Share Allocation: {share_doc.quantity} {share_doc.share_type} - {share_doc.member_name}",
        reference_type="Share Allocation",
        reference_name=share_doc.name,
        branch=branch
    )


def post_dividend_payment_to_gl(dividend_doc, member, amount, payment_date):
    """
    Post dividend payment to GL
    
    Double Entry:
    - Debit: Dividend Expense / Retained Earnings
    - Credit: Payment Mode Account (Cash/Bank) or Dividends Payable
    
    Args:
        dividend_doc: Dividend Declaration document
        member: Member docname
        amount: Dividend amount
        payment_date: Payment date
        
    Returns:
        Journal Entry document
    """
    dividend_expense_account = get_gl_account(account_name="Dividend Expense")
    dividends_payable_account = get_gl_account(account_name="Dividends Payable")
    
    if not dividend_expense_account:
        frappe.throw(_("Dividend Expense account not configured"))
    
    # Get member branch
    branch = frappe.db.get_value("SACCO Member", member, "branch")
    member_name = frappe.db.get_value("SACCO Member", member, "member_name")
    
    accounts = [
        {
            "gl_account": dividend_expense_account,
            "debit": amount,
            "credit": 0,
            "party_type": "SACCO Member",
            "party": member,
            "remarks": f"Dividend for {dividend_doc.period_from} to {dividend_doc.period_to}"
        },
        {
            "gl_account": dividends_payable_account,
            "debit": 0,
            "credit": amount,
            "party_type": "SACCO Member",
            "party": member,
            "remarks": f"Dividend payable to {member_name}"
        }
    ]
    
    return create_gl_entry(
        voucher_type="Journal Entry",
        posting_date=payment_date,
        accounts=accounts,
        remarks=f"Dividend Declaration: {dividend_doc.share_type} - {member_name}",
        reference_type="Dividend Declaration",
        reference_name=dividend_doc.name,
        branch=branch
    )


def post_fine_to_gl(fine_doc):
    """
    Post member fine to GL
    
    Double Entry:
    - Debit: Fines Receivable
    - Credit: Fine Income
    
    Args:
        fine_doc: Member Fine document
        
    Returns:
        Journal Entry document
    """
    fine_type_account = frappe.db.get_value("Fine Type", fine_doc.fine_type, "default_gl_account")
    fines_receivable_account = get_gl_account(account_name="Fines Receivable")
    
    if not fine_type_account:
        frappe.throw(_("Fine Type {0} does not have a GL Account configured").format(
            fine_doc.fine_type
        ))
        
    if not fines_receivable_account:
        frappe.throw(_("Fines Receivable account not configured"))
    
    # Get member branch
    branch = frappe.db.get_value("SACCO Member", fine_doc.member, "branch")
    
    accounts = [
        {
            "gl_account": fines_receivable_account,
            "debit": fine_doc.amount,
            "credit": 0,
            "party_type": "SACCO Member",
            "party": fine_doc.member,
            "remarks": f"Fine charged to {fine_doc.member_name}"
        },
        {
            "gl_account": fine_type_account,
            "debit": 0,
            "credit": fine_doc.amount,
            "party_type": "SACCO Member",
            "party": fine_doc.member,
            "remarks": f"{fine_doc.fine_type} - {fine_doc.reason}"
        }
    ]
    
    return create_gl_entry(
        voucher_type="Journal Entry",
        posting_date=fine_doc.fine_date,
        accounts=accounts,
        remarks=f"Member Fine: {fine_doc.fine_type} - {fine_doc.member_name}",
        reference_type="Member Fine",
        reference_name=fine_doc.name,
        branch=branch
    )


def get_account_balance(gl_account, as_of_date=None):
    """
    Get the balance of a GL account as of a specific date
    
    Args:
        gl_account: GL Account name
        as_of_date: Date to calculate balance as of (default: today)
        
    Returns:
        dict with balance and balance_type
    """
    as_of_date = as_of_date or nowdate()
    
    result = frappe.db.sql("""
        SELECT 
            COALESCE(SUM(jea.debit), 0) as total_debit,
            COALESCE(SUM(jea.credit), 0) as total_credit
        FROM `tabSACCO Journal Entry Account` jea
        INNER JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name
        WHERE jea.gl_account = %s 
        AND je.docstatus = 1
        AND je.posting_date <= %s
    """, (gl_account, as_of_date), as_dict=True)[0]
    
    # Get account type
    account_type = frappe.db.get_value("SACCO GL Account", gl_account, "account_type")
    
    # Get opening balances
    opening = frappe.db.get_value(
        "SACCO GL Account", 
        gl_account, 
        ["opening_debit", "opening_credit"],
        as_dict=True
    )
    
    total_debit = flt(result.total_debit) + flt(opening.opening_debit)
    total_credit = flt(result.total_credit) + flt(opening.opening_credit)
    
    # Calculate balance based on account type
    if account_type in ['Asset', 'Expense']:
        balance = total_debit - total_credit
        balance_type = "Debit" if balance >= 0 else "Credit"
    else:
        balance = total_credit - total_debit
        balance_type = "Credit" if balance >= 0 else "Debit"
    
    return {
        "balance": abs(balance),
        "balance_type": balance_type,
        "total_debit": total_debit,
        "total_credit": total_credit
    }


def get_member_balance(member, account_type=None):
    """
    Get total balance for a member across all accounts
    
    Args:
        member: Member docname
        account_type: Optional filter by account type
        
    Returns:
        dict with balances by account type
    """
    conditions = "jea.party_type = 'SACCO Member' AND jea.party = %(member)s AND je.docstatus = 1"
    values = {"member": member}
    
    if account_type:
        conditions += " AND ga.account_type = %(account_type)s"
        values["account_type"] = account_type
    
    result = frappe.db.sql(f"""
        SELECT 
            ga.account_type,
            ga.account_name,
            COALESCE(SUM(jea.debit), 0) as total_debit,
            COALESCE(SUM(jea.credit), 0) as total_credit
        FROM `tabSACCO Journal Entry Account` jea
        INNER JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name
        INNER JOIN `tabSACCO GL Account` ga ON jea.gl_account = ga.name
        WHERE {conditions}
        GROUP BY ga.account_type, ga.account_name
    """, values, as_dict=True)
    
    return result


def get_trial_balance(as_of_date=None, branch=None):
    """
    Generate trial balance as of a specific date
    
    Args:
        as_of_date: Date for trial balance
        branch: Optional branch filter
        
    Returns:
        List of account balances
    """
    as_of_date = as_of_date or nowdate()
    
    conditions = "je.docstatus = 1 AND je.posting_date <= %(as_of_date)s"
    values = {"as_of_date": as_of_date}
    
    if branch:
        conditions += " AND je.branch = %(branch)s"
        values["branch"] = branch
    
    result = frappe.db.sql(f"""
        SELECT 
            ga.name as account,
            ga.account_name,
            ga.account_number,
            ga.account_type,
            ga.parent_account,
            ga.opening_debit,
            ga.opening_credit,
            COALESCE(SUM(jea.debit), 0) as period_debit,
            COALESCE(SUM(jea.credit), 0) as period_credit
        FROM `tabSACCO GL Account` ga
        LEFT JOIN `tabSACCO Journal Entry Account` jea ON jea.gl_account = ga.name
        LEFT JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name AND {conditions}
        WHERE ga.is_group = 0
        GROUP BY ga.name
        ORDER BY ga.account_number
    """, values, as_dict=True)
    
    # Calculate balances
    for row in result:
        total_debit = flt(row.period_debit) + flt(row.opening_debit)
        total_credit = flt(row.period_credit) + flt(row.opening_credit)
        
        if row.account_type in ['Asset', 'Expense']:
            row.balance = total_debit - total_credit
            row.balance_type = "Debit" if row.balance >= 0 else "Credit"
        else:
            row.balance = total_credit - total_debit
            row.balance_type = "Credit" if row.balance >= 0 else "Debit"
            
        row.balance = abs(row.balance)
    
    return result
