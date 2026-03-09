# SACCO Management System

A comprehensive SACCO (Savings and Credit Cooperative) Management System built on Frappe/ERPNext.

## Features

### Core Modules
- **Member Management** - Complete member lifecycle with nominees and next of kin
- **Contributions** - Multiple contribution types with GL integration
- **Loans** - Full loan lifecycle with flat/reducing balance interest calculation
- **Shares & Dividends** - Share allocation and dividend declaration
- **Fines** - Member fines and attendance fines with auto-penalties
- **Meetings** - Meeting management with attendance tracking

### Key Features
- Multi-branch support
- Role-based access (Teller, Loan Officer, Branch Manager, Admin, Auditor)
- Double-entry accounting with GL integration
- Automated workflows for loan approval
- Comprehensive reporting dashboard
- Scheduled tasks for penalties and reminders

## Installation

```bash
# Get the app
bench get-app https://github.com/MAD-BOT-hash/sacco_mangement.git

# Install on your site (this only installs the app, doesn't create DocTypes yet)
bench --site your-site-name install-app sacco_management

# Run migrations to create DocTypes
bench --site your-site-name migrate

# Clear cache
bench --site your-site-name clear-cache

# Setup default data (GL accounts, roles, contribution types, etc.)
bench --site your-site-name execute sacco_management.sacco.setup.install.setup_sacco_data

# Restart bench
bench restart
```

## DocTypes

| Module | DocTypes |
|--------|----------|
| Core | Branch, Member Group, Payment Mode |
| GL | SACCO GL Account, SACCO Journal Entry |
| Members | SACCO Member, Member Nominee, Member Next of Kin |
| Contributions | Contribution Type, Member Contribution |
| Loans | Loan Type, Loan Application, Loan Repayment |
| Shares | Share Type, Share Allocation |
| Dividends | Dividend Declaration, Dividend Payment |
| Fines | Fine Type, Member Fine |
| Meetings | SACCO Meeting, Meeting Register, Attendance Fine Type, Member Attendance Fine |

## Reports

- Member Statement
- Contribution Summary
- Loan Performance
- Share Capital Report
- Trial Balance
- General Ledger

## License

MIT
