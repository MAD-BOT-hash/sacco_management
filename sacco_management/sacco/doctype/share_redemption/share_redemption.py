# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class ShareRedemption(Document):
    def validate(self):
        self.validate_member()
        self.validate_eligible_quantity()
        self.calculate_amounts()
        
    def validate_member(self):
        """Validate member exists and is eligible"""
        member_status = frappe.db.get_value("SACCO Member", self.member, "status")
        
        if self.exit_type == "Death":
            # Allow for deceased members
            pass
        elif member_status != "Active":
            frappe.throw(_("Member must be Active for share redemption"))
    
    def validate_eligible_quantity(self):
        """Validate quantity available for redemption"""
        # Get total allocated shares
        total_shares = frappe.db.sql("""
            SELECT COALESCE(SUM(quantity), 0)
            FROM `tabShare Allocation`
            WHERE member = %s AND share_type = %s AND docstatus = 1 AND status = 'Allocated'
        """, (self.member, self.share_type))[0][0] or 0
        
        # Check if any redemption already in process
        pending_redemption = frappe.db.sql("""
            SELECT COALESCE(SUM(quantity_requested), 0)
            FROM `tabShare Redemption`
            WHERE member = %s AND share_type = %s AND docstatus = 1 AND status IN ('Pending Approval', 'Approved')
        """, (self.member, self.share_type))[0][0] or 0
        
        self.eligible_quantity = flt(total_shares) - flt(pending_redemption)
        
        if flt(self.quantity_requested) > flt(self.eligible_quantity):
            frappe.throw(_("Cannot redeem {0} shares. Only {1} shares eligible for redemption.")
                        .format(self.quantity_requested, self.eligible_quantity))
    
    def calculate_amounts(self):
        """Calculate redemption amounts"""
        if self.quantity_requested and self.price_per_share:
            self.total_redemption_amount = flt(self.quantity_requested) * flt(self.price_per_share)
            self.net_payable_amount = flt(self.total_redemption_amount) - flt(self.forfeited_amount)
    
    def before_submit(self):
        """Validate board approval"""
        if not self.board_approval_number:
            frappe.throw(_("Board Approval Number is required for share redemption"))
        
        if not self.board_approval_date:
            frappe.throw(_("Board Approval Date is required"))
        
        self.status = "Approved"
    
    def on_submit(self):
        """Process share redemption"""
        self.create_gl_entries()
        self.update_share_allocation()
        self.update_member_shares()
    
    def on_cancel(self):
        """Reverse redemption on cancellation"""
        self.reverse_gl_entries()
        self.update_member_shares(cancel=True)
    
    def create_gl_entries(self):
        """Create GL entries for share redemption"""
        from sacco_management.sacco.utils.gl_utils import make_gl_entry
        
        posting_date = self.redemption_date or nowdate()
        
        # Get accounts
        share_capital_account = frappe.db.get_single_value("SACCO Settings", "share_capital_account")
        bank_account = self.bank_account or frappe.db.get_single_value("SACCO Settings", "default_bank_account")
        
        if not share_capital_account or not bank_account:
            frappe.throw(_("Please configure Share Capital Account and Bank Account"))
        
        # Debit Share Capital Account (reduce capital)
        make_gl_entry(
            voucher_type="Share Redemption",
            voucher_no=self.name,
            posting_date=posting_date,
            account=share_capital_account,
            debit=self.total_redemption_amount,
            credit=0,
            remarks=f"Share redemption - {self.name}"
        )
        
        # Handle forfeiture (if any)
        if flt(self.forfeited_amount) > 0:
            forfeiture_account = frappe.db.get_single_value("SACCO Settings", "share_forfeiture_account")
            if forfeiture_account:
                make_gl_entry(
                    voucher_type="Share Redemption",
                    voucher_no=self.name,
                    posting_date=posting_date,
                    account=forfeiture_account,
                    debit=0,
                    credit=self.forfeited_amount,
                    remarks=f"Forfeiture on share redemption"
                )
        
        # Credit Bank Account (net payment)
        make_gl_entry(
            voucher_type="Share Redemption",
            voucher_no=self.name,
            posting_date=posting_date,
            account=bank_account,
            debit=0,
            credit=self.net_payable_amount,
            remarks=f"Payment for share redemption"
        )
        
        self.gl_posted = 1
    
    def reverse_gl_entries(self):
        """Reverse GL entries"""
        gl_entries = frappe.get_all("SACCO Journal Entry Account",
                                   filters={
                                       "reference_type": "Share Redemption",
                                       "reference_name": self.name
                                   })
        
        for gl in gl_entries:
            frappe.db.set_value("SACCO Journal Entry Account", gl.name, "is_cancelled", 1)
        
        self.gl_posted = 0
    
    def update_share_allocation(self):
        """Update share allocation status"""
        # Get the latest share allocation for this member and type
        allocations = frappe.get_all("Share Allocation",
                                    filters={
                                        "member": self.member,
                                        "share_type": self.share_type,
                                        "docstatus": 1,
                                        "status": "Allocated"
                                    },
                                    order_by="allocation_date DESC",
                                    limit=1)
        
        if allocations:
            allocation = frappe.get_doc("Share Allocation", allocations[0].name)
            
            # Reduce quantity or mark as redeemed
            remaining_qty = flt(allocation.quantity) - flt(self.quantity_requested)
            
            if remaining_qty <= 0:
                allocation.status = "Redeemed"
            else:
                allocation.quantity = remaining_qty
            
            allocation.save(ignore_permissions=True)
    
    def update_member_shares(self, cancel=False):
        """Update member's total shares"""
        member = frappe.get_doc("SACCO Member", self.member)
        
        if cancel:
            member.total_shares = flt(member.total_shares) + flt(self.quantity_requested)
        else:
            member.total_shares = flt(member.total_shares) - flt(self.quantity_requested)
        
        member.save(ignore_permissions=True)
