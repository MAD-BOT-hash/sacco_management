# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class SavingsProduct(Document):
    def validate(self):
        self.validate_interest_rate()
        self.validate_balance_limits()
        self.validate_gl_accounts()
        
    def validate_interest_rate(self):
        """Validate interest rate configuration"""
        if self.interest_applicable:
            if flt(self.interest_rate) < 0:
                frappe.throw(_("Interest Rate cannot be negative"))
            
            if flt(self.min_balance_for_interest) > flt(self.max_balance) and flt(self.max_balance) > 0:
                frappe.throw(_("Minimum balance for interest cannot exceed maximum balance"))
    
    def validate_balance_limits(self):
        """Validate balance limits"""
        if flt(self.min_balance) > flt(self.max_balance) and flt(self.max_balance) > 0:
            frappe.throw(_("Minimum balance cannot exceed maximum balance"))
            
        if flt(self.min_deposit_amount) > flt(self.min_balance) and flt(self.min_balance) > 0:
            frappe.throw(_("Minimum deposit amount cannot exceed minimum balance"))
    
    def validate_gl_accounts(self):
        """Validate GL accounts are set"""
        if not self.default_gl_account:
            frappe.throw(_("Default GL Account is required"))
        
        # Check if GL account is a liability account
        gl_account_type = frappe.db.get_value("SACCO GL Account", self.default_gl_account, "account_type")
        if gl_account_type != "Liability":
            frappe.throw(_("Default GL Account must be a Liability account"))
    
    def on_update(self):
        """Update all savings accounts when product is updated"""
        if self.has_value_changed("is_active"):
            self.update_account_status()
    
    def update_account_status(self):
        """Update status of all accounts using this product"""
        accounts = frappe.get_all("Savings Account", 
            filters={"product": self.name}, 
            fields=["name"])
        
        for acc_data in accounts:
            account = frappe.get_doc("Savings Account", acc_data.name)
            if not self.is_active:
                account.status = "Inactive"
            else:
                account.status = "Active"
            account.save(ignore_permissions=True)
        
        frappe.db.commit()


@frappe.whitelist()
def get_product_details(product_name):
    """Get product details for client-side use"""
    product = frappe.get_doc("Savings Product", product_name)
    return {
        "min_balance": flt(product.min_balance),
        "max_balance": flt(product.max_balance),
        "min_deposit_amount": flt(product.min_deposit_amount),
        "interest_rate": flt(product.interest_rate) if product.interest_applicable else 0,
        "interest_calculation_method": product.interest_calculation_method,
        "default_gl_account": product.default_gl_account,
        "interest_gl_account": product.interest_gl_account
    }
