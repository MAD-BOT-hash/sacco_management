"""
Field-Level Security Configuration

This module provides field-level security decorators and validation functions
for protecting sensitive data based on user roles.
"""

import frappe
from frappe import _
from functools import wraps
from sacco_management.sacco.security.permission_sets import setup_field_level_security


def get_field_restrictions():
    """Get field-level restrictions configuration"""
    return setup_field_level_security()


def has_field_permission(doctype, fieldname, user=None):
    """
    Check if user has permission to access a specific field
    
    Args:
        doctype (str): Document type
        fieldname (str): Field name
        user (str): User ID (default: current user)
    
    Returns:
        bool: True if user has permission
    """
    if not user:
        user = frappe.session.user
    
    # Admin has access to everything
    if "SACCO Admin" in frappe.get_roles(user):
        return True
    
    restrictions = get_field_restrictions()
    
    if doctype not in restrictions:
        return True  # No restrictions for this doctype
    
    if fieldname not in restrictions[doctype]:
        return True  # No restrictions for this field
    
    allowed_roles = restrictions[doctype][fieldname]
    user_roles = frappe.get_roles(user)
    
    # Check if user has any of the allowed roles
    return any(role in user_roles for role in allowed_roles)


def protect_field(field_name, doctype=None):
    """
    Decorator to protect sensitive fields
    
    Args:
        field_name (str): Field name to protect
        doctype (str): Document type (optional, can be inferred)
    
    Returns:
        decorator function
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Get document from args or kwargs
            doc = kwargs.get('doc') or (args[0] if args else None)
            
            if doc:
                actual_doctype = doctype or doc.doctype
                
                # Check field permission
                if not has_field_permission(actual_doctype, field_name):
                    # Remove protected field from response
                    if hasattr(doc, field_name):
                        setattr(doc, field_name, None)
                    
                    # Also check if it's a dict
                    if isinstance(doc, dict) and field_name in doc:
                        doc[field_name] = None
            
            return f(*args, **kwargs)
        
        return wrapper
    return decorator


def sanitize_document_for_user(doc, user=None):
    """
    Remove or mask fields that user doesn't have permission to view
    
    Args:
        doc (dict|Document): Document to sanitize
        user (str): User ID (default: current user)
    
    Returns:
        dict|Document: Sanitized document
    """
    if not user:
        user = frappe.session.user
    
    # Admin sees everything
    if "SACCO Admin" in frappe.get_roles(user):
        return doc
    
    restrictions = get_field_restrictions()
    doctype = doc.doctype if hasattr(doc, 'doctype') else None
    
    if not doctype or doctype not in restrictions:
        return doc
    
    user_roles = frappe.get_roles(user)
    
    # Convert to dict if it's a Document
    if hasattr(doc, 'as_dict'):
        doc_dict = doc.as_dict()
    elif isinstance(doc, dict):
        doc_dict = doc.copy()
    else:
        return doc
    
    # Remove restricted fields
    for fieldname, allowed_roles in restrictions[doctype].items():
        if not any(role in user_roles for role in allowed_roles):
            if fieldname in doc_dict:
                doc_dict[fieldname] = None
    
    # Update original document if it's a Document object
    if hasattr(doc, 'update'):
        doc.update(doc_dict)
        return doc
    
    return doc_dict


def validate_field_access(doctype, fieldname, value=None, user=None):
    """
    Validate if user can read/write a specific field
    
    Args:
        doctype (str): Document type
        fieldname (str): Field name
        value: Field value (optional)
        user (str): User ID
    
    Raises:
        frappe.PermissionError: If user doesn't have permission
    """
    if not user:
        user = frappe.session.user
    
    if not has_field_permission(doctype, fieldname, user):
        raise frappe.PermissionError(
            _("You don't have permission to access field '{0}' in {1}").format(fieldname, doctype)
        )


def get_visible_fields(doctype, user=None):
    """
    Get list of fields visible to a user
    
    Args:
        doctype (str): Document type
        user (str): User ID
    
    Returns:
        list: List of visible field names
    """
    if not user:
        user = frappe.session.user
    
    # Admin sees all fields
    if "SACCO Admin" in frappe.get_roles(user):
        meta = frappe.get_meta(doctype)
        return [field.fieldname for field in meta.fields]
    
    restrictions = get_field_restrictions()
    user_roles = frappe.get_roles(user)
    
    # Get all fields from meta
    meta = frappe.get_meta(doctype)
    all_fields = [field.fieldname for field in meta.fields]
    
    # Filter out restricted fields
    visible_fields = []
    for field in all_fields:
        if doctype not in restrictions or field not in restrictions[doctype]:
            visible_fields.append(field)
        else:
            allowed_roles = restrictions[doctype][field]
            if any(role in user_roles for role in allowed_roles):
                visible_fields.append(field)
    
    return visible_fields


def apply_row_level_security(query, doctype=None, user=None):
    """
    Apply row-level security filters to SQL queries
    
    Args:
        query (str): Original SQL query
        doctype (str): Document type
        user (str): User ID
    
    Returns:
        str: Query with security filters applied
    """
    if not user:
        user = frappe.session.user
    
    user_roles = frappe.get_roles(user)
    
    # Admin bypasses row-level security
    if "SACCO Admin" in frappe.get_roles(user):
        return query
    
    # Branch-based security
    if "Branch Manager" in user_roles and doctype:
        branch = frappe.db.get_value("User", user, "default_branch")
        if branch:
            # Add branch filter to query
            if "WHERE" in query.upper():
                query = query.replace("WHERE", f"WHERE (branch = '{branch}' OR 1=0) AND ", 1)
            else:
                query += f" WHERE branch = '{branch}'"
    
    # Member can only see their own records
    if "Member" in user_roles and "SACCO Admin" not in user_roles:
        member_id = frappe.db.get_value("SACCO Member", {"email": user})
        if member_id and doctype in ["Savings Account", "Loan Application", "Share Allocation"]:
            if "WHERE" in query.upper():
                query = query.replace("WHERE", f"WHERE (member = '{member_id}' OR 1=0) AND ", 1)
            else:
                query += f" WHERE member = '{member_id}'"
    
    return query
