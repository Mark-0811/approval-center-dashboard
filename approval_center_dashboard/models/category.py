from odoo import fields, models


class ApprovalCategory(models.Model):
    _name = 'approval.center.category'
    _description = 'Approval Category'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(default=1)
    active = fields.Boolean(default=True)
    rule_ids = fields.One2many('approval.center.rule', 'category_id')
