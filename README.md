# Approval Center Dashboard for Odoo 20

This repository contains two separate addons:

- `approval_center_dashboard/` is the Odoo 20 addon. It has no company-specific addon dependencies.
- The repository root contains the earlier Odoo 13 implementation for compatibility.

## Dynamic workflow setup

Install `approval_center_dashboard`, then open **Approval Center → Configuration → Categories** and create workflow categories. Add approval rules with a unique code, source model, and status domains. Map the reference, request date, requester, responsible user, and purpose fields as needed. Add approver users or groups, and optionally configure public source-model methods for approve and reject.

The index refreshes every ten minutes. A manager can also refresh it from the rule form. Source methods execute as the current user and follow the source model's access rules.

The dashboard shows requests assigned to the current user by default. Users can search, filter by status and category, open source records, comment in chatter, and use configured decisions.
