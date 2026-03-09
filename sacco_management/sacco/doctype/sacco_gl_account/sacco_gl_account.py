import frappe
from frappe.model.document import Document
from frappe import _


class SACCOGLAccount(Document):
    def validate(self):
        self.validate_parent_account()
        self.validate_group_account()
        
    def validate_parent_account(self):
        """Validate parent account settings"""
        if self.parent_account:
            parent = frappe.get_doc("SACCO GL Account", self.parent_account)
            if not parent.is_group:
                frappe.throw(_("Parent account {0} must be a group account").format(self.parent_account))
            if parent.account_type != self.account_type:
                frappe.throw(_("Account type must match parent account type ({0})").format(parent.account_type))
                
    def validate_group_account(self):
        """Group accounts cannot have direct transactions"""
        if self.is_group and self.has_transactions():
            frappe.throw(_("Cannot convert to group account as there are existing transactions"))
            
    def has_transactions(self):
        """Check if account has any journal entry transactions"""
        return frappe.db.exists("SACCO Journal Entry Account", {"gl_account": self.name})
        
    def on_update(self):
        self.update_balance()
        
    def update_balance(self):
        """Calculate and update current balance"""
        result = frappe.db.sql("""
            SELECT 
                COALESCE(SUM(jea.debit), 0) as total_debit,
                COALESCE(SUM(jea.credit), 0) as total_credit
            FROM `tabSACCO Journal Entry Account` jea
            INNER JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name
            WHERE jea.gl_account = %s AND je.docstatus = 1
        """, self.name, as_dict=True)[0]
        
        total_debit = result.total_debit + (self.opening_debit or 0)
        total_credit = result.total_credit + (self.opening_credit or 0)
        
        # Calculate balance based on account type
        if self.account_type in ['Asset', 'Expense']:
            # Debit balance accounts
            self.current_balance = total_debit - total_credit
            self.balance_type = "Debit" if self.current_balance >= 0 else "Credit"
        else:
            # Credit balance accounts (Liability, Equity, Income)
            self.current_balance = total_credit - total_debit
            self.balance_type = "Credit" if self.current_balance >= 0 else "Debit"
            
        self.current_balance = abs(self.current_balance)


@frappe.whitelist()
def get_account_balance(account):
    """Get current balance of an account"""
    doc = frappe.get_doc("SACCO GL Account", account)
    doc.update_balance()
    return {
        "balance": doc.current_balance,
        "balance_type": doc.balance_type
    }


@frappe.whitelist()
def get_children(doctype, parent=None, is_root=False):
    """Get child accounts for tree view"""
    filters = {}
    if parent and not is_root:
        filters["parent_account"] = parent
    else:
        filters["parent_account"] = ("is", "not set")
        
    accounts = frappe.get_all(
        "SACCO GL Account",
        filters=filters,
        fields=["name as value", "account_name", "account_number", "account_type", "is_group as expandable"],
        order_by="account_number"
    )
    
    return accounts
