# -*- coding: utf-8 -*-

from odoo import fields, models


class ApprovalDashboardCategory(models.Model):
    _name = 'dex_approval_dashboard.category'
    _description = 'Approval Dashboard Category'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True, copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer()
    approval_type_ids = fields.One2many(
        'dex_approval_dashboard.type', 'category_id', string='Approval Functions')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The approval category code must be unique.'),
    ]
