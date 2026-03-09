"""
Mobile Money Transaction Handler

Auto-create contribution records from successful M-Pesa transactions
"""

import frappe
from frappe import _
from datetime import datetime


@frappe.whitelist(allow_guest=True)
def mpesa_callback():
    """
    Handle M-Pesa callback responses
    
    This endpoint receives callbacks from Safaricom Daraja API
    """
    from frappe.utils import now_datetime
    
    data = frappe.form_dict
    
    frappe.log_error(title="M-Pesa Callback Received", message=str(data))
    
    try:
        # Find transaction record
        checkout_request_id = data.get("CheckoutRequestID")
        
        if not checkout_request_id:
            return {"status": "error", "message": "Missing CheckoutRequestID"}
        
        transaction = frappe.get_doc("Mobile Money Transaction", {
            "checkout_request_id": checkout_request_id
        })
        
        if not transaction:
            # Create new transaction record
            transaction = frappe.new_doc("Mobile Money Transaction")
            transaction.checkout_request_id = checkout_request_id
        
        # Update transaction based on result
        if data.get("ResultCode") == "0":
            # Success
            transaction.status = "Completed"
            transaction.amount = data.get("Amount")
            transaction.mpesa_receipt = data.get("MpesaReceiptNumber")
            transaction.transaction_date = now_datetime()
            
            # Auto-create contribution if member reference exists
            account_reference = data.get("AccountReference")
            if account_reference:
                create_member_contribution_from_mpesa(transaction, account_reference)
        else:
            # Failed
            transaction.status = "Failed"
            transaction.failure_reason = data.get("ResultDesc")
        
        transaction.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {"status": "received"}
        
    except Exception as e:
        frappe.log_error(f"M-Pesa Callback Error: {str(e)}")
        frappe.db.rollback()
        return {"status": "error", "message": str(e)}


def create_member_contribution_from_mpesa(transaction, account_reference):
    """
    Create member contribution record from M-Pesa transaction
    
    Args:
        transaction: Mobile Money Transaction doc
        account_reference: Member ID or account number
    """
    try:
        # Try to find member by account reference
        member = None
        
        # Check if reference is member ID
        if frappe.db.exists("SACCO Member", account_reference):
            member = account_reference
        else:
            # Try to find member by phone
            member = frappe.db.get_value(
                "SACCO Member",
                {"phone": transaction.phone_number},
                "name"
            )
        
        if not member:
            frappe.log_error(
                title="Member Not Found for M-Pesa Transaction",
                message=f"Phone: {transaction.phone_number}, Reference: {account_reference}"
            )
            return
        
        # Get member details
        member_doc = frappe.get_doc("SACCO Member", member)
        
        # Determine contribution type
        contribution_type = determine_contribution_type(account_reference)
        
        # Create contribution record
        contribution = frappe.new_doc("Member Contribution")
        contribution.member = member
        contribution.posting_date = transaction.transaction_date
        contribution.amount = transaction.amount
        contribution.contribution_type = contribution_type
        contribution.payment_mode = "M-Pesa"
        contribution.reference_no = transaction.mpesa_receipt
        contribution.remarks = f"M-Pesa Payment - {transaction.transaction_description or 'Contribution'}"
        
        contribution.insert(ignore_permissions=True)
        contribution.submit()
        
        # Update transaction with link
        transaction.contribution = contribution.name
        transaction.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Send confirmation SMS
        send_payment_confirmation_sms(member_doc, contribution)
        
        frappe.log_msg(
            f"Created contribution {contribution.name} from M-Pesa payment",
            "M-Pesa Integration"
        )
        
    except Exception as e:
        frappe.log_error(f"Error creating contribution from M-Pesa: {str(e)}")
        frappe.db.rollback()


def determine_contribution_type(account_reference):
    """Determine contribution type based on reference"""
    # This can be customized based on your SACCO's structure
    # For example, different prefixes for different contribution types
    
    if account_reference.startswith("DIV"):
        return "Dividend Investment"
    elif account_reference.startswith("SHARE"):
        return "Share Purchase"
    else:
        # Default to regular contribution
        return frappe.db.get_single_value("SACCO Settings", "default_contribution_type") or "Regular Contribution"


def send_payment_confirmation_sms(member, contribution):
    """Send SMS confirmation to member"""
    try:
        from frappe.utils import get_fullname
        
        sms_message = f"""Dear {member.member_name}, we have received your contribution of KES {contribution.amount:,.2f}. 
Ref: {contribution.reference_no}. Thank you for saving with us."""
        
        # Use your preferred SMS gateway
        # Example with Africa's Talking
        send_sms_via_africas_talking(member.phone, sms_message)
        
    except Exception as e:
        frappe.log_error(f"SMS Sending Error: {str(e)}")


def send_sms_via_africas_talking(phone_number, message):
    """Send SMS via Africa's Talking"""
    import requests
    
    api_key = frappe.db.get_single_value("SACCO Settings", "africas_talking_api_key")
    username = frappe.db.get_single_value("SACCO Settings", "africas_talking_username")
    
    if not api_key or not username:
        frappe.log_error("SMS Gateway not configured")
        return
    
    url = "https://api.africastalking.com/version1/messaging"
    
    headers = {
        "Accept": "application/json",
        "ApiKey": api_key
    }
    
    data = {
        "username": username,
        "to": phone_number,
        "message": message
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        result = response.json()
        frappe.log_msg(f"SMS sent to {phone_number}: {result}", "SMS Gateway")
    except Exception as e:
        frappe.log_error(f"Africa's Talking API Error: {str(e)}")
