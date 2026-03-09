# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class SavingsDeposit(Document):
    def validate(self):
        self.validate_account()
        self.validate_amount()
        self.set_defaults()
        
    def validate_account(self):
        """Validate account exists and is active"""
        account_status = frappe.db.get_value("Savings Account", self.account, "status")
        if account_status != "Active":
            frappe.throw(_("Cannot deposit to {0} account").format(account_status))
        
        # Validate minimum deposit amount
        product = frappe.get_doc("Savings Product", 
            frappe.db.get_value("Savings Account", self.account, "product"))
        
        if flt(product.min_deposit_amount) > 0 and flt(self.amount) < flt(product.min_deposit_amount):
            frappe.throw(_("Minimum deposit amount is {}").format(product.min_deposit_amount))
    
    def validate_amount(self):
        """Validate amount is positive"""
        if flt(self.amount) <= 0:
            frappe.throw(_("Deposit amount must be positive"))
    
    def set_defaults(self):
        """Set default values"""
        self.principal_amount = flt(self.amount)
        self.interest_component = 0
    
    def on_submit(self):
        """Process deposit on submit"""
        self.process_deposit()
    
    def on_cancel(self):
        """Reverse deposit on cancel"""
        self.reverse_deposit()
    
    def process_deposit(self):
        """Process the savings deposit"""
        account = frappe.get_doc("Savings Account", self.account)
        
        # Update account balance
        account.update_balance(
            amount=self.amount,
            transaction_type="Deposit"
        )
        
        # Set balance after deposit
        self.balance_after_deposit = flt(account.balance)
        
        # Post to GL
        self.post_to_gl(account)
        
        self.status = "Deposited"
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Deposit of {} processed successfully").format(self.amount), alert=True)
    
    def reverse_deposit(self):
        """Reverse the deposit"""
        if self.status != "Deposited":
            frappe.throw(_("Can only reverse deposited entries"))
        
        account = frappe.get_doc("Savings Account", self.account)
        
        # Reverse the balance update
        account.balance = flt(account.balance) - flt(self.amount)
        account.available_balance = flt(account.balance)
        account.total_deposit = flt(account.total_deposit) - flt(self.amount)
        account.save(ignore_permissions=True)
        
        # Reverse GL entry
        if self.gl_posted and self.journal_entry:
            from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
            reverse_gl_entry("Savings Deposit", self.name)
        
        self.status = "Cancelled"
        self.save(ignore_permissions=True)
    
    def post_to_gl(self, account):
        """Post deposit to General Ledger"""
        product = frappe.get_doc("Savings Product", account.product)
        
        payment_account = frappe.db.get_value("Payment Mode", self.payment_mode, "gl_account")
        
        if not payment_account:
            frappe.throw(_("Payment Mode GL Account not configured"))
        
        from sacco_management.sacco.utils.gl_utils import create_gl_entry
        
        accounts = [
            {
                "gl_account": payment_account,
                "debit": self.amount,
                "credit": 0,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Deposit to {account.account_name}"
            },
            {
                "gl_account": product.default_gl_account,
                "debit": 0,
                "credit": self.amount,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Savings Deposit - {account.account_name}"
            }
        ]
        
        je = create_gl_entry(
            voucher_type="Receipt Voucher",
            posting_date=self.deposit_date,
            accounts=accounts,
            remarks=f"Savings Deposit: {account.account_name} - {self.member_name}",
            reference_type="Savings Deposit",
            reference_name=self.name,
            branch=self.branch
        )
        
        self.journal_entry = je.name
        self.gl_posted = 1


@frappe.whitelist()
def create_deposit(account, amount, payment_mode, reference_number=None, remarks=None):
    """
    Create a savings deposit
    
    Args:
        account: Savings Account ID
        amount: Deposit amount
        payment_mode: Payment mode
        reference_number: Reference number
        remarks: Remarks
    
    Returns:
        Created Savings Deposit document
    """
    doc = frappe.new_doc("Savings Deposit")
    doc.account = account
    doc.amount = flt(amount)
    doc.payment_mode = payment_mode
    doc.reference_number = reference_number
    doc.remarks = remarks
    doc.deposit_date = nowdate()
    
    doc.insert(ignore_permissions=True)
    doc.submit()
    
    frappe.db.commit()
    return doc.as_dict()
