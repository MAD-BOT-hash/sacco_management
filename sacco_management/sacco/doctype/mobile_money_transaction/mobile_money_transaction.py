# Copyright (c) 2024, SACCO Developer and contributors
# For license information, see license.txt

import frappe
from frappe.model.document import Document


class MobileMoneyTransaction(Document):
	"""Mobile Money Transaction tracking for M-Pesa and other mobile payments"""
	
	def validate(self):
		"""Validate transaction data"""
		if not self.amount:
			frappe.throw(_("Amount is required"))
		
		if not self.phone_number:
			frappe.throw(_("Phone number is required"))
		
		# Validate phone number format (Kenyan format: 254XXXXXXXXX)
		if self.phone_number and not self.phone_number.startswith("254"):
			frappe.throw(_("Phone number must start with 254 (e.g., 254712345678)"))
		
		if len(self.phone_number) != 12:
			frappe.throw(_("Phone number must be 12 digits (e.g., 254712345678)"))
	
	def before_submit(self):
		"""Validate before submitting"""
		if self.status == "Pending":
			frappe.throw(_("Transaction cannot be submitted in Pending status"))


@frappe.whitelist(allow_guest=True)
def get_transaction_status(checkout_request_id):
	"""Get transaction status by checkout request ID"""
	transaction = frappe.db.exists("Mobile Money Transaction", {
		"checkout_request_id": checkout_request_id
	})
	
	if transaction:
		doc = frappe.get_doc("Mobile Money Transaction", transaction)
		return {
			"status": doc.status,
			"amount": doc.amount,
			"mpesa_receipt": doc.mpesa_receipt,
			"transaction_date": doc.transaction_date
		}
	
	return None
