# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class DividendDeclaration(Document):
    def validate(self):
        self.validate_dates()
        self.validate_duplicate_declaration()
        
    def validate_dates(self):
        """Validate period dates"""
        if self.period_from and self.period_to:
            if getdate(self.period_from) > getdate(self.period_to):
                frappe.throw(_("Period From cannot be after Period To"))
            if getdate(self.period_to) > getdate(self.declaration_date):
                frappe.throw(_("Period To cannot be after Declaration Date"))
    
    def validate_duplicate_declaration(self):
        """Check for duplicate dividend declarations for the same period"""
        if self.is_new():
            existing = frappe.db.exists("Dividend Declaration", {
                "share_type": self.share_type,
                "period_from": self.period_from,
                "period_to": self.period_to,
                "docstatus": ["!=", 2],
                "name": ["!=", self.name]
            })
            if existing:
                frappe.throw(_("Dividend Declaration already exists for this Share Type and Period"))
    
    def before_submit(self):
        """Generate dividend payments before submission"""
        if not self.dividend_payments:
            self.calculate_dividends()
        self.calculate_totals()
    
    def on_submit(self):
        """Actions on submit"""
        self.db_set("status", "Pending Approval")
    
    def on_cancel(self):
        """Actions on cancel"""
        self.db_set("status", "Cancelled")
        # Reverse any GL entries
        self.reverse_gl_entries()
    
    @frappe.whitelist()
    def calculate_dividends(self):
        """Calculate dividend for each member holding shares"""
        # Clear existing payments
        self.dividend_payments = []
        
        # Get share type details
        share_type = frappe.get_doc("Share Type", self.share_type)
        price_per_share = flt(share_type.price_per_share)
        
        # Build query for share allocations
        filters = {
            "share_type": self.share_type,
            "docstatus": 1,
            "status": "Allocated"
        }
        
        # Get all members with shares of this type
        share_query = """
            SELECT 
                sa.member,
                m.member_name,
                SUM(sa.quantity) as total_shares,
                SUM(sa.amount) as total_amount
            FROM `tabShare Allocation` sa
            INNER JOIN `tabSACCO Member` m ON sa.member = m.name
            WHERE sa.share_type = %(share_type)s
            AND sa.docstatus = 1
            AND sa.status = 'Allocated'
            AND sa.allocation_date <= %(period_to)s
        """
        
        if self.branch:
            share_query += " AND m.branch = %(branch)s"
        
        share_query += " GROUP BY sa.member HAVING total_shares > 0"
        
        query_params = {
            "share_type": self.share_type,
            "period_to": self.period_to,
            "branch": self.branch
        }
        
        members_with_shares = frappe.db.sql(share_query, query_params, as_dict=True)
        
        total_shares = 0
        total_gross = 0
        total_tax = 0
        total_net = 0
        
        for member in members_with_shares:
            shares = flt(member.total_shares)
            share_value = shares * price_per_share
            gross_dividend = share_value * flt(self.dividend_rate) / 100
            withholding_tax = gross_dividend * flt(self.withholding_tax_rate) / 100
            net_dividend = gross_dividend - withholding_tax
            
            self.append("dividend_payments", {
                "member": member.member,
                "member_name": member.member_name,
                "shares_held": shares,
                "dividend_rate": self.dividend_rate,
                "gross_amount": gross_dividend,
                "withholding_tax": withholding_tax,
                "net_amount": net_dividend,
                "status": "Pending"
            })
            
            total_shares += shares
            total_gross += gross_dividend
            total_tax += withholding_tax
            total_net += net_dividend
        
        # Update summary
        self.total_shares = total_shares
        self.total_gross_dividend = total_gross
        self.total_withholding_tax = total_tax
        self.total_net_dividend = total_net
        
        if not members_with_shares:
            frappe.msgprint(_("No members found with shares of type {0} for the selected period").format(self.share_type))
        else:
            frappe.msgprint(_("Calculated dividends for {0} members").format(len(members_with_shares)))
        
        return len(members_with_shares)
    
    def calculate_totals(self):
        """Recalculate totals from dividend payments"""
        total_shares = 0
        total_gross = 0
        total_tax = 0
        total_net = 0
        
        for payment in self.dividend_payments:
            total_shares += flt(payment.shares_held)
            total_gross += flt(payment.gross_amount)
            total_tax += flt(payment.withholding_tax)
            total_net += flt(payment.net_amount)
        
        self.total_shares = total_shares
        self.total_gross_dividend = total_gross
        self.total_withholding_tax = total_tax
        self.total_net_dividend = total_net
    
    @frappe.whitelist()
    def approve_dividend(self):
        """Approve the dividend declaration"""
        if self.status != "Pending Approval":
            frappe.throw(_("Only Pending Approval declarations can be approved"))
        
        self.db_set("status", "Approved")
        frappe.msgprint(_("Dividend Declaration approved successfully"))
    
    @frappe.whitelist()
    def process_payments(self):
        """Process all dividend payments and post to GL"""
        if self.status != "Approved":
            frappe.throw(_("Only Approved declarations can be processed for payment"))
        
        from sacco_management.sacco.utils.gl_utils import post_dividend_payment_to_gl
        
        payment_date = frappe.utils.today()
        
        for payment in self.dividend_payments:
            if payment.status == "Pending":
                # Update payment details
                frappe.db.set_value("Dividend Payment", payment.name, {
                    "payment_date": payment_date,
                    "status": "Paid"
                })
                
                # Post to GL
                try:
                    post_dividend_payment_to_gl(self, payment)
                except Exception as e:
                    frappe.log_error(f"GL Posting Error for Dividend Payment {payment.member}: {str(e)}")
                    continue
        
        self.db_set("status", "Paid")
        frappe.msgprint(_("All dividend payments processed successfully"))
    
    def reverse_gl_entries(self):
        """Reverse GL entries on cancellation"""
        # Find and cancel related journal entries
        journal_entries = frappe.get_all("SACCO Journal Entry", 
            filters={
                "reference_type": "Dividend Declaration",
                "reference_name": self.name,
                "docstatus": 1
            },
            pluck="name"
        )
        
        for je_name in journal_entries:
            je = frappe.get_doc("SACCO Journal Entry", je_name)
            je.cancel()


def post_dividend_payment_to_gl(dividend_declaration, payment):
    """Post dividend payment to GL"""
    from sacco_management.sacco.utils.gl_utils import create_gl_entry
    
    share_type = frappe.get_doc("Share Type", dividend_declaration.share_type)
    
    # Get GL accounts
    dividend_expense_account = frappe.db.get_single_value("SACCO Settings", "dividend_expense_account") or \
                              frappe.db.get_value("SACCO GL Account", {"account_type": "Expense", "account_name": ["like", "%Dividend%"]}, "name")
    
    cash_account = frappe.db.get_single_value("SACCO Settings", "default_cash_account") or \
                   frappe.db.get_value("SACCO GL Account", {"account_type": "Asset", "is_cash_account": 1}, "name")
    
    tax_payable_account = frappe.db.get_single_value("SACCO Settings", "withholding_tax_account") or \
                          frappe.db.get_value("SACCO GL Account", {"account_type": "Liability", "account_name": ["like", "%Tax%"]}, "name")
    
    accounts = []
    
    # Debit: Dividend Expense (gross amount)
    if dividend_expense_account:
        accounts.append({
            "account": dividend_expense_account,
            "debit": flt(payment.gross_amount),
            "credit": 0,
            "party_type": "SACCO Member",
            "party": payment.member,
            "reference_type": "Dividend Declaration",
            "reference_name": dividend_declaration.name
        })
    
    # Credit: Cash/Bank (net amount)
    if cash_account:
        accounts.append({
            "account": cash_account,
            "debit": 0,
            "credit": flt(payment.net_amount),
            "party_type": "SACCO Member",
            "party": payment.member,
            "reference_type": "Dividend Declaration",
            "reference_name": dividend_declaration.name
        })
    
    # Credit: Withholding Tax Payable
    if tax_payable_account and flt(payment.withholding_tax) > 0:
        accounts.append({
            "account": tax_payable_account,
            "debit": 0,
            "credit": flt(payment.withholding_tax),
            "party_type": "SACCO Member",
            "party": payment.member,
            "reference_type": "Dividend Declaration",
            "reference_name": dividend_declaration.name
        })
    
    if accounts:
        create_gl_entry(
            voucher_type="Dividend Declaration",
            voucher_no=dividend_declaration.name,
            accounts=accounts,
            posting_date=payment.payment_date or frappe.utils.today(),
            remarks=f"Dividend payment to {payment.member_name} for {dividend_declaration.share_type}"
        )
