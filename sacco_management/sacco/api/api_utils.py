"""
API Utilities for SACCO Management System

This module provides utility functions for REST API operations:
- Authentication and authorization
- Request/Response formatting
- Data validation
- Error handling
- Rate limiting helpers
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, now, nowdate, validate_email_address
from functools import wraps
import json


class APIError(Exception):
    """Custom API Exception"""
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def api_response(success=True, data=None, message=None, errors=None, status_code=200):
    """
    Standardize API response format
    
    Args:
        success (bool): Whether the operation was successful
        data (dict/list): Response data
        message (str): Success message
        errors (list): List of error messages
        status_code (int): HTTP status code
    
    Returns:
        dict: Standardized response
    """
    response = {
        "success": success,
        "status_code": status_code,
        "timestamp": now()
    }
    
    if data is not None:
        response["data"] = data
    
    if message:
        response["message"] = message
    
    if errors:
        response["errors"] = errors
        response["success"] = False
    
    return response


def require_auth(f):
    """
    Decorator to require authentication for API endpoints
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not frappe.session.user or frappe.session.user == 'Guest':
            raise APIError(_("Authentication required"), 401)
        
        return f(*args, **kwargs)
    
    return wrapper


def require_role(roles):
    """
    Decorator to require specific roles for API endpoints
    
    Args:
        roles (list): List of required roles
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if isinstance(roles, str):
                required_roles = [roles]
            else:
                required_roles = roles
            
            user_roles = frappe.get_roles(frappe.session.user)
            
            if not any(role in user_roles for role in required_roles):
                raise APIError(
                    _("Insufficient permissions. Required roles: {0}").format(", ".join(required_roles)),
                    403
                )
            
            return f(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_request_data(required_fields, data):
    """
    Validate that required fields are present in request data
    
    Args:
        required_fields (list): List of required field names
        data (dict): Request data
    
    Raises:
        APIError: If validation fails
    """
    missing_fields = []
    
    for field in required_fields:
        if field not in data or not data[field]:
            missing_fields.append(field)
    
    if missing_fields:
        raise APIError(
            _("Missing required fields: {0}").format(", ".join(missing_fields)),
            400
        )


def sanitize_input(data):
    """
    Sanitize input data to prevent XSS and injection attacks
    
    Args:
        data (dict|str): Input data
    
    Returns:
        dict|str: Sanitized data
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            sanitized[key] = sanitize_input(value)
        return sanitized
    
    elif isinstance(data, str):
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&']
        for char in dangerous_chars:
            data = data.replace(char, '')
        return data.strip()
    
    return data


def parse_filters(filters_json):
    """
    Parse filters from JSON string to Frappe filter list
    
    Args:
        filters_json (str): JSON string of filters
    
    Returns:
        list: Frappe filter list
    """
    try:
        filters = json.loads(filters_json)
        
        if isinstance(filters, dict):
            # Convert dict to list format
            filter_list = []
            for key, value in filters.items():
                filter_list.append(["SACCO Member", key, "=", value])
            return filter_list
        elif isinstance(filters, list):
            return filters
        else:
            return []
    
    except json.JSONDecodeError:
        return []


def paginate_results(data, page=1, page_size=20):
    """
    Paginate result set
    
    Args:
        data (list): Full result set
        page (int): Page number (1-indexed)
        page_size (int): Number of items per page
    
    Returns:
        dict: Paginated data with metadata
    """
    total_items = len(data)
    total_pages = (total_items + page_size - 1) // page_size
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    paginated_data = data[start_idx:end_idx]
    
    return {
        "items": paginated_data,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }


def validate_member_data(data):
    """
    Validate member data before creation/update
    
    Args:
        data (dict): Member data
    
    Raises:
        APIError: If validation fails
    """
    # Validate email
    if 'email' in data and data['email']:
        try:
            validate_email_address(data['email'])
        except Exception:
            raise APIError(_("Invalid email address: {0}").format(data['email']), 400)
    
    # Validate phone
    if 'phone_number' in data and data['phone_number']:
        if not data['phone_number'].replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise APIError(_("Invalid phone number format"), 400)
    
    # Validate date formats
    date_fields = ['date_of_birth', 'joining_date', 'employment_date']
    for field in date_fields:
        if field in data and data[field]:
            try:
                getdate(data[field])
            except Exception:
                raise APIError(_("Invalid date format for {0}. Use YYYY-MM-DD").format(field), 400)


def validate_loan_data(data):
    """
    Validate loan application data
    
    Args:
        data (dict): Loan data
    
    Raises:
        APIError: If validation fails
    """
    # Validate amount
    if 'amount_requested' in data:
        if flt(data['amount_requested']) <= 0:
            raise APIError(_("Loan amount must be greater than zero"), 400)
    
    # Validate interest rate
    if 'interest_rate' in data:
        if flt(data['interest_rate']) < 0 or flt(data['interest_rate']) > 100:
            raise APIError(_("Interest rate must be between 0 and 100"), 400)
    
    # Validate repayment period
    if 'repayment_period' in data:
        if int(data['repayment_period']) <= 0:
            raise APIError(_("Repayment period must be positive"), 400)


def get_doc_permissions(doctype, docname=None):
    """
    Get current user's permissions for a document type
    
    Args:
        doctype (str): Document type
        docname (str): Document name (optional)
    
    Returns:
        dict: Permission details
    """
    permissions = {
        "read": frappe.has_permission(doctype, "read"),
        "write": frappe.has_permission(doctype, "write"),
        "create": frappe.has_permission(doctype, "create"),
        "delete": frappe.has_permission(doctype, "delete"),
        "submit": frappe.has_permission(doctype, "submit"),
        "cancel": frappe.has_permission(doctype, "cancel"),
    }
    
    return permissions


def log_api_call(endpoint, method, data=None, status_code=200):
    """
    Log API call for audit trail
    
    Args:
        endpoint (str): API endpoint
        method (str): HTTP method
        data (dict): Request data
        status_code (int): Response status code
    """
    try:
        frappe.log_error(
            message=json.dumps({
                "endpoint": endpoint,
                "method": method,
                "user": frappe.session.user,
                "data": data,
                "status_code": status_code,
                "timestamp": now()
            }),
            title=f"API Call: {endpoint}"
        )
    except Exception:
        pass  # Don't fail the API call if logging fails


def handle_api_exception(func):
    """
    Decorator to handle exceptions in API endpoints
    
    Args:
        func: API endpoint function
    
    Returns:
        wrapper function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            frappe.log_error(message=str(e), title="API Error")
            frappe.response.http_status_code = e.status_code
            return api_response(
                success=False,
                errors=[e.message],
                status_code=e.status_code
            )
        except Exception as e:
            frappe.log_error(message=str(e), title="Unhandled API Error")
            frappe.response.http_status_code = 500
            return api_response(
                success=False,
                errors=[_("Internal server error: {0}").format(str(e))],
                status_code=500
            )
    
    return wrapper
