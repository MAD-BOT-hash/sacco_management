"""
API Documentation Generator

Generates comprehensive API documentation for the SACCO Management System
"""

import frappe
from frappe import _
import json


def get_api_documentation():
    """
    Generate complete API documentation
    
    Returns:
        dict: API documentation structure
    """
    return {
        "info": {
            "title": "SACCO Management System API",
            "version": "1.0.0",
            "description": "RESTful API for SACCO Management operations"
        },
        "base_url": "/api/method/sacco_management.sacco.api",
        "authentication": {
            "type": "Session / API Key",
            "description": "All API requests require authentication via Frappe session or API key"
        },
        "endpoints": get_all_endpoints()
    }


def get_all_endpoints():
    """Get all API endpoints with documentation"""
    
    return {
        "Member API": {
            "path": "/api/method/sacco_management.sacco.api.member_api",
            "endpoints": [
                {
                    "method": "GET",
                    "endpoint": "/get_members",
                    "description": "List members with optional filtering and pagination",
                    "parameters": {
                        "filters": {"type": "dict|str", "required": False, "description": "Filter criteria"},
                        "page": {"type": "int", "default": 1, "description": "Page number"},
                        "page_size": {"type": "int", "default": 20, "description": "Items per page"}
                    },
                    "response_example": {
                        "success": True,
                        "status_code": 200,
                        "data": {
                            "items": [],
                            "page": 1,
                            "total_items": 0,
                            "total_pages": 0
                        }
                    },
                    "required_roles": ["SACCO Admin", "Loan Officer"]
                },
                {
                    "method": "GET",
                    "endpoint": "/get_member/{member_id}",
                    "description": "Get complete member details including related records",
                    "parameters": {
                        "member_id": {"type": "str", "required": True}
                    },
                    "response_example": {
                        "success": True,
                        "data": {
                            "member": {},
                            "savings_accounts": [],
                            "share_allocations": [],
                            "loans": []
                        }
                    }
                },
                {
                    "method": "POST",
                    "endpoint": "/create_member",
                    "description": "Create a new SACCO member",
                    "request_body": {
                        "member_name": {"type": "str", "required": True},
                        "email": {"type": "str", "required": True},
                        "membership_type": {"type": "str", "required": True},
                        "phone_number": {"type": "str", "required": False}
                    },
                    "required_roles": ["SACCO Admin", "Loan Officer"]
                },
                {
                    "method": "PUT",
                    "endpoint": "/update_member/{member_id}",
                    "description": "Update existing member information",
                    "parameters": {
                        "member_id": {"type": "str", "required": True}
                    },
                    "required_roles": ["SACCO Admin", "Loan Officer"]
                },
                {
                    "method": "DELETE",
                    "endpoint": "/delete_member/{member_id}",
                    "description": "Delete a member (only if no transactions exist)",
                    "required_roles": ["SACCO Admin"]
                },
                {
                    "method": "GET",
                    "endpoint": "/search_members",
                    "description": "Search members by name, email, or ID",
                    "parameters": {
                        "query": {"type": "str", "required": True},
                        "limit": {"type": "int", "default": 20}
                    }
                },
                {
                    "method": "GET",
                    "endpoint": "/get_member_statistics",
                    "description": "Get member statistics and demographics",
                    "parameters": {
                        "branch": {"type": "str", "required": False}
                    }
                }
            ]
        },
        "Loan API": {
            "path": "/api/method/sacco_management.sacco.api.loan_api",
            "endpoints": [
                {
                    "method": "GET",
                    "endpoint": "/get_loans",
                    "description": "Get list of loans with optional filtering",
                    "parameters": {
                        "filters": {"type": "dict", "required": False},
                        "page": {"type": "int", "default": 1},
                        "page_size": {"type": "int", "default": 20}
                    }
                },
                {
                    "method": "GET",
                    "endpoint": "/get_loan/{loan_id}",
                    "description": "Get complete loan details including schedule and repayments",
                    "parameters": {
                        "loan_id": {"type": "str", "required": True}
                    }
                },
                {
                    "method": "POST",
                    "endpoint": "/create_loan_application",
                    "description": "Create a new loan application",
                    "request_body": {
                        "member": {"type": "str", "required": True},
                        "loan_type": {"type": "str", "required": True},
                        "amount_requested": {"type": "float", "required": True},
                        "repayment_period": {"type": "int", "required": True}
                    },
                    "required_roles": ["SACCO Admin", "Loan Officer", "Member"]
                },
                {
                    "method": "POST",
                    "endpoint": "/approve_loan/{loan_id}",
                    "description": "Approve a loan application",
                    "required_roles": ["SACCO Admin", "Loan Officer", "Credit Committee"]
                },
                {
                    "method": "POST",
                    "endpoint": "/disburse_loan/{loan_id}",
                    "description": "Disburse an approved loan",
                    "required_roles": ["SACCO Admin", "Loan Officer"]
                },
                {
                    "method": "POST",
                    "endpoint": "/process_repayment/{loan_id}",
                    "description": "Process a loan repayment",
                    "request_body": {
                        "amount_paid": {"type": "float", "required": True},
                        "payment_date": {"type": "date", "required": True},
                        "payment_mode": {"type": "str", "required": True}
                    }
                },
                {
                    "method": "GET",
                    "endpoint": "/get_loan_schedule/{loan_id}",
                    "description": "Get loan repayment schedule"
                },
                {
                    "method": "GET",
                    "endpoint": "/get_member_loans/{member_id}",
                    "description": "Get all loans for a member"
                }
            ]
        },
        "Savings & Shares API": {
            "path": "/api/method/sacco_management.sacco.api.savings_shares_api",
            "endpoints": [
                {
                    "method": "GET",
                    "endpoint": "/get_savings_accounts",
                    "description": "Get savings accounts with optional member filter"
                },
                {
                    "method": "POST",
                    "endpoint": "/create_savings_account",
                    "description": "Create new savings account",
                    "request_body": {
                        "member": {"type": "str", "required": True},
                        "account_type": {"type": "str", "required": True}
                    }
                },
                {
                    "method": "POST",
                    "endpoint": "/process_deposit",
                    "description": "Process savings deposit",
                    "request_body": {
                        "savings_account": {"type": "str", "required": True},
                        "amount": {"type": "float", "required": True},
                        "payment_mode": {"type": "str", "required": True}
                    }
                },
                {
                    "method": "POST",
                    "endpoint": "/process_withdrawal",
                    "description": "Process savings withdrawal",
                    "request_body": {
                        "savings_account": {"type": "str", "required": True},
                        "amount": {"type": "float", "required": True},
                        "withdrawal_reason": {"type": "str", "required": True}
                    }
                },
                {
                    "method": "GET",
                    "endpoint": "/get_share_allocations",
                    "description": "Get share allocations"
                },
                {
                    "method": "POST",
                    "endpoint": "/purchase_shares",
                    "description": "Purchase new shares",
                    "request_body": {
                        "member": {"type": "str", "required": True},
                        "share_type": {"type": "str", "required": True},
                        "quantity": {"type": "int", "required": True}
                    }
                },
                {
                    "method": "POST",
                    "endpoint": "/redeem_shares",
                    "description": "Redeem shares",
                    "required_roles": ["SACCO Admin", "Loan Officer"]
                },
                {
                    "method": "GET",
                    "endpoint": "/get_dividend_calculations",
                    "description": "Get dividend calculations"
                },
                {
                    "method": "POST",
                    "endpoint": "/process_dividend_payment",
                    "description": "Process dividend payment",
                    "required_roles": ["SACCO Admin", "Accountant"]
                }
            ]
        }
    }


@frappe.whitelist()
def generate_api_docs(format="json"):
    """
    Generate API documentation
    
    Args:
        format (str): Output format (json, markdown, html)
    
    Returns:
        str|dict: API documentation
    """
    docs = get_api_documentation()
    
    if format == "json":
        return docs
    elif format == "markdown":
        return generate_markdown_docs(docs)
    elif format == "html":
        return generate_html_docs(docs)
    
    return docs


def generate_markdown_docs(docs):
    """Generate markdown documentation"""
    
    md = f"# {docs['info']['title']}\n\n"
    md += f"**Version:** {docs['info']['version']}\n\n"
    md += f"**Base URL:** `{docs['base_url']}`\n\n"
    md += f"**Description:** {docs['info']['description']}\n\n"
    
    md += "## Authentication\n\n"
    md += f"- **Type:** {docs['authentication']['type']}\n"
    md += f"- **Description:** {docs['authentication']['description']}\n\n"
    
    md += "## Endpoints\n\n"
    
    for category, data in docs['endpoints'].items():
        md += f"### {category}\n\n"
        md += f"**Path:** `{data['path']}`\n\n"
        
        for endpoint in data['endpoints']:
            md += f"#### {endpoint['method']} {endpoint['endpoint']}\n\n"
            md += f"{endpoint.get('description', '')}\n\n"
            
            if 'parameters' in endpoint:
                md += "**Parameters:**\n"
                for param, details in endpoint['parameters'].items():
                    required = " **(required)**" if details.get('required') else ""
                    default = f" (default: {details.get('default')})" if 'default' in details else ""
                    md += f"- `{param}`{required}{default}: {details.get('description', '')}\n"
                md += "\n"
            
            if 'request_body' in endpoint:
                md += "**Request Body:**\n"
                for field, details in endpoint['request_body'].items():
                    required = " **(required)**" if details.get('required') else ""
                    md += f"- `{field}`{required} ({details['type']}): Field description\n"
                md += "\n"
            
            if 'response_example' in endpoint:
                md += "**Response Example:**\n"
                md += "```json\n"
                md += json.dumps(endpoint['response_example'], indent=2)
                md += "\n```\n\n"
            
            if 'required_roles' in endpoint:
                md += f"**Required Roles:** {', '.join(endpoint['required_roles'])}\n\n"
            
            md += "---\n\n"
    
    return md


def generate_html_docs(docs):
    """Generate HTML documentation"""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{docs['info']['title']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            h2 {{ color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            h3 {{ color: #16a085; }}
            h4 {{ color: #2980b9; }}
            code {{ background-color: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
            pre {{ background-color: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
            .endpoint {{ margin: 20px 0; padding: 15px; border-left: 4px solid #3498db; background-color: #ecf0f1; }}
        </style>
    </head>
    <body>
        <h1>{docs['info']['title']}</h1>
        <p><strong>Version:</strong> {docs['info']['version']}</p>
        <p><strong>Base URL:</strong> <code>{docs['base_url']}</code></p>
        <p>{docs['info']['description']}</p>
        
        <h2>Authentication</h2>
        <p>{docs['authentication']['description']}</p>
        
        <h2>Endpoints</h2>
    """
    
    for category, data in docs['endpoints'].items():
        html += f"<h3>{category}</h3>"
        html += f"<p><strong>Path:</strong> <code>{data['path']}</code></p>"
        
        for endpoint in data['endpoints']:
            html += f"""
            <div class="endpoint">
                <h4>{endpoint['method']} {endpoint['endpoint']}</h4>
                <p>{endpoint.get('description', '')}</p>
            """
            
            if 'parameters' in endpoint:
                html += "<p><strong>Parameters:</strong></p><ul>"
                for param, details in endpoint['parameters'].items():
                    required = " <strong>(required)</strong>" if details.get('required') else ""
                    default = f" (default: {details.get('default')})" if 'default' in details else ""
                    html += f"<li><code>{param}</code>{required}{default}</li>"
                html += "</ul>"
            
            if 'required_roles' in endpoint:
                html += f"<p><strong>Required Roles:</strong> {', '.join(endpoint['required_roles'])}</p>"
            
            html += "</div>"
    
    html += """
    </body>
    </html>
    """
    
    return html


@frappe.whitelist()
def download_api_docs(format="json"):
    """Download API documentation as file"""
    docs = get_api_documentation()
    
    if format == "json":
        content = json.dumps(docs, indent=2)
        filename = "sacco_api_documentation.json"
    elif format == "markdown":
        content = generate_markdown_docs(docs)
        filename = "sacco_api_documentation.md"
    else:
        content = generate_html_docs(docs)
        filename = "sacco_api_documentation.html"
    
    return {
        "filename": filename,
        "content": content
    }
