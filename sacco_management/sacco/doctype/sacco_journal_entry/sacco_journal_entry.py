import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class SaccoJournalEntry(Document):
    def validate(self):
        self.calculate_totals()
        self.validate_balance()
        self.validate_accounts()
        
    def calculate_totals(self):
        """Calculate total debit and credit"""
        self.total_debit = sum(flt(row.debit) for row in self.accounts)
        self.total_credit = sum(flt(row.credit) for row in self.accounts)
        self.difference = flt(self.total_debit) - flt(self.total_credit)
        
    def validate_balance(self):
        """Ensure debits equal credits"""
        if flt(self.difference, 2) != 0:
            frappe.throw(
                _("Total Debit ({0}) must equal Total Credit ({1}). Difference: {2}").format(
                    self.total_debit, self.total_credit, self.difference
                )
            )
            
    def validate_accounts(self):
        """Validate account entries"""
        if not self.accounts:
            frappe.throw(_("At least one accounting entry is required"))
            
        for row in self.accounts:
            # Check that either debit or credit is entered, not both
            if flt(row.debit) > 0 and flt(row.credit) > 0:
                frappe.throw(_("Row {0}: Cannot have both debit and credit in the same row").format(row.idx))
                
            if flt(row.debit) == 0 and flt(row.credit) == 0:
                frappe.throw(_("Row {0}: Either debit or credit must be entered").format(row.idx))
                
            # Check if account is frozen
            account = frappe.get_doc("SACCO GL Account", row.gl_account)
            if account.freeze_account:
                frappe.throw(_("Row {0}: Account {1} is frozen").format(row.idx, row.gl_account))
                
            # Check if account is a group account
            if account.is_group:
                frappe.throw(_("Row {0}: Cannot post to group account {1}").format(row.idx, row.gl_account))
                
    def on_submit(self):
        """Update account balances on submit"""
        self.update_account_balances()
        
    def on_cancel(self):
        """Reverse account balances on cancel"""
        self.update_account_balances()
        
    def update_account_balances(self):
        """Update GL account balances"""
        accounts_to_update = set()
        for row in self.accounts:
            accounts_to_update.add(row.gl_account)
            
        for account_name in accounts_to_update:
            account = frappe.get_doc("SACCO GL Account", account_name)
            account.update_balance()
            account.db_update()


def create_journal_entry(
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
    Create a journal entry programmatically
    
    Args:
        voucher_type: Type of voucher (Journal Entry, Receipt Voucher, etc.)
        posting_date: Date of the entry
        accounts: List of dicts with keys: gl_account, debit, credit, party_type, party
        remarks: Optional remarks
        reference_type: DocType of source document
        reference_name: Name of source document
        branch: Branch for the entry
        submit: Whether to submit the entry (default True)
        
    Returns:
        The created Journal Entry document
    """
    je = frappe.new_doc("SACCO Journal Entry")
    je.voucher_type = voucher_type
    je.posting_date = posting_date
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
            "reference_type": acc.get("reference_type"),
            "reference_name": acc.get("reference_name"),
            "remarks": acc.get("remarks")
        })
        
    je.insert(ignore_permissions=True)
    
    if submit:
        je.submit()
        
    return je


@frappe.whitelist()
def get_journal_entries_for_account(gl_account, from_date=None, to_date=None):
    """Get all journal entries for a specific account"""
    filters = {"gl_account": gl_account, "docstatus": 1}
    
    conditions = "jea.gl_account = %(gl_account)s AND je.docstatus = 1"
    values = {"gl_account": gl_account}
    
    if from_date:
        conditions += " AND je.posting_date >= %(from_date)s"
        values["from_date"] = from_date
        
    if to_date:
        conditions += " AND je.posting_date <= %(to_date)s"
        values["to_date"] = to_date
        
    entries = frappe.db.sql(f"""
        SELECT 
            je.name as voucher_no,
            je.voucher_type,
            je.posting_date,
            jea.debit,
            jea.credit,
            jea.party_type,
            jea.party,
            je.remarks,
            je.reference_type,
            je.reference_name
        FROM `tabSACCO Journal Entry Account` jea
        INNER JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name
        WHERE {conditions}
        ORDER BY je.posting_date, je.name
    """, values, as_dict=True)
    
    return entries
