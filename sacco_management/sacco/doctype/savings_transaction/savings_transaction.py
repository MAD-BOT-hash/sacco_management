# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class SavingsTransaction(Document):
    def validate(self):
        self.validate_account()
        self.validate_amount()
        
    def validate_account(self):
        """Validate account exists and is active"""
        account_status = frappe.db.get_value("Savings Account", self.account, "status")
        if account_status != "Active":
            frappe.throw(_("Cannot process transaction for {0} account").format(account_status))
    
    def validate_amount(self):
        """Validate amount is positive"""
        if flt(self.amount) <= 0:
            frappe.throw(_("Transaction amount must be positive"))
    
    def on_submit(self):
        """Process transaction on submit"""
        self.process_transaction()
    
    def on_cancel(self):
        """Reverse transaction on cancel"""
        self.reverse_transaction()
    
    def process_transaction(self):
        """Process the savings transaction"""
        account = frappe.get_doc("Savings Account", self.account)
        
        # Update account balance
        account.update_balance(
            amount=self.amount,
            transaction_type=self.transaction_type
        )
        
        # Set balance after transaction
        self.balance_after_transaction = flt(account.balance)
        self.running_balance = flt(account.balance)
        
        # Post to GL if not already done
        if not self.gl_posted:
            self.post_to_gl(account)
        
        self.status = "Processed"
        self.save(ignore_permissions=True)
    
    def reverse_transaction(self):
        """Reverse the transaction"""
        if self.status != "Processed":
            frappe.throw(_("Can only reverse processed transactions"))
        
        account = frappe.get_doc("Savings Account", self.account)
        
        # Reverse the balance update
        if self.transaction_type == "Deposit":
            new_balance = flt(account.balance) - flt(self.amount)
        else:
            new_balance = flt(account.balance) + flt(self.amount)
        
        account.balance = new_balance
        account.available_balance = new_balance
        
        if self.transaction_type == "Deposit":
            account.total_deposit = flt(account.total_deposit) - flt(self.amount)
        else:
            account.total_withdrawal = flt(account.total_withdrawal) - flt(self.amount)
        
        account.save(ignore_permissions=True)
        
        # Reverse GL entry
        if self.gl_posted and self.journal_entry:
            from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
            reverse_gl_entry("Savings Transaction", self.name)
        
        self.status = "Cancelled"
        self.save(ignore_permissions=True)
    
    def post_to_gl(self, account):
        """Post transaction to General Ledger"""
        product = frappe.get_doc("Savings Product", account.product)
        
        if self.transaction_type in ["Deposit", "Transfer In"]:
            # Debit: Cash/Bank (Payment Mode Account)
            # Credit: Member Savings (Product GL Account)
            from sacco_management.sacco.utils.gl_utils import create_gl_entry
            
            payment_account = None
            if self.payment_mode:
                payment_account = frappe.db.get_value("Payment Mode", self.payment_mode, "gl_account")
            
            if not payment_account:
                frappe.throw(_("Payment Mode GL Account not configured"))
            
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
                    "remarks": f"{self.transaction_type} - {account.account_name}"
                }
            ]
            
            je = create_gl_entry(
                voucher_type="Receipt Voucher" if self.transaction_type == "Deposit" else "Journal Entry",
                posting_date=self.transaction_date,
                accounts=accounts,
                remarks=f"Savings {self.transaction_type}: {account.account_name} - {self.member_name}",
                reference_type="Savings Transaction",
                reference_name=self.name,
                branch=account.branch
            )
            
            self.journal_entry = je.name
            self.gl_posted = 1
        
        elif self.transaction_type in ["Withdrawal", "Transfer Out"]:
            # Debit: Member Savings (Product GL Account)
            # Credit: Cash/Bank (Payment Mode Account)
            from sacco_management.sacco.utils.gl_utils import create_gl_entry
            
            payment_account = None
            if self.payment_mode:
                payment_account = frappe.db.get_value("Payment Mode", self.payment_mode, "gl_account")
            
            if not payment_account:
                frappe.throw(_("Payment Mode GL Account not configured"))
            
            accounts = [
                {
                    "gl_account": product.default_gl_account,
                    "debit": self.amount,
                    "credit": 0,
                    "party_type": "SACCO Member",
                    "party": self.member,
                    "remarks": f"Withdrawal from {account.account_name}"
                },
                {
                    "gl_account": payment_account,
                    "debit": 0,
                    "credit": self.amount,
                    "party_type": "SACCO Member",
                    "party": self.member,
                    "remarks": f"{self.transaction_type} - {account.account_name}"
                }
            ]
            
            je = create_gl_entry(
                voucher_type="Payment Voucher" if self.transaction_type == "Withdrawal" else "Journal Entry",
                posting_date=self.transaction_date,
                accounts=accounts,
                remarks=f"Savings {self.transaction_type}: {account.account_name} - {self.member_name}",
                reference_type="Savings Transaction",
                reference_name=self.name,
                branch=account.branch
            )
            
            self.journal_entry = je.name
            self.gl_posted = 1


@frappe.whitelist()
def create_transaction(account, amount, transaction_type, payment_mode=None, reference_number=None, remarks=None):
    """
    Create a savings transaction
    
    Args:
        account: Savings Account ID
        amount: Transaction amount
        transaction_type: Deposit or Withdrawal
        payment_mode: Payment mode
        reference_number: Reference number
        remarks: Transaction remarks
    
    Returns:
        Created Savings Transaction document
    """
    doc = frappe.new_doc("Savings Transaction")
    doc.account = account
    doc.amount = flt(amount)
    doc.transaction_type = transaction_type
    doc.transaction_date = nowdate()
    doc.payment_mode = payment_mode
    doc.reference_number = reference_number
    doc.remarks = remarks
    
    doc.insert(ignore_permissions=True)
    doc.submit()
    
    frappe.db.commit()
    return doc.as_dict()
