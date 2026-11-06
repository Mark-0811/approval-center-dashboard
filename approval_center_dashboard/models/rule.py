import ast
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ApprovalRule(models.Model):
    _name = 'approval.center.rule'
    _description = 'Configurable Approval Rule'
    _order = 'category_id, sequence, name, id'
    _rec_name = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category_id = fields.Many2one('approval.center.category', required=True, ondelete='restrict')
    model_id = fields.Many2one('ir.model', required=True, ondelete='restrict',
                               domain=[('transient', '=', False)])
    model_name = fields.Char(related='model_id.model', store=True)
    menu_id = fields.Many2one('ir.ui.menu', string='Related Menu')
    pending_domain = fields.Char(required=True, default='[]')
    approved_domain = fields.Char(default='[]')
    rejected_domain = fields.Char(default='[]')
    cancelled_domain = fields.Char(default='[]')
    name_field_id = fields.Many2one('ir.model.fields', string='Reference Field')
    date_field_id = fields.Many2one('ir.model.fields', string='Request Date Field')
    requester_field_id = fields.Many2one('ir.model.fields', string='Requester Field')
    approver_field_id = fields.Many2one('ir.model.fields', string='Responsible User Field')
    purpose_field_id = fields.Many2one('ir.model.fields', string='Purpose / Remarks Field')
    approve_method = fields.Char(help='Optional public method on the source record.')
    reject_method = fields.Char(help='Optional public method on the source record.')
    approver_group_ids = fields.Many2many('res.groups', string='Approver Groups')
    approver_user_ids = fields.Many2many('res.users', string='Additional Approvers')
    last_sync = fields.Datetime(readonly=True)
    sync_error = fields.Text(readonly=True)

    _sql_constraints = [('code_unique', 'unique(code)', 'Rule code must be unique.')]

    @api.constrains('model_id', 'name_field_id', 'date_field_id', 'requester_field_id',
                    'approver_field_id', 'purpose_field_id')
    def _check_mapped_fields(self):
        for rule in self:
            for field_name in ('name_field_id', 'date_field_id', 'requester_field_id',
                               'approver_field_id', 'purpose_field_id'):
                mapped = rule[field_name]
                if mapped and mapped.model_id != rule.model_id:
                    raise ValidationError(_('Mapped fields must belong to the selected source model.'))
            if rule.date_field_id and rule.date_field_id.ttype not in ('date', 'datetime'):
                raise ValidationError(_('Request date must map to a date or datetime field.'))

    @api.constrains('pending_domain', 'approved_domain', 'rejected_domain', 'cancelled_domain')
    def _check_domains(self):
        for rule in self:
            for field_name in ('pending_domain', 'approved_domain', 'rejected_domain', 'cancelled_domain'):
                try:
                    domain = ast.literal_eval(rule[field_name] or '[]')
                except (ValueError, SyntaxError, TypeError) as error:
                    raise ValidationError(_('Invalid domain in %s: %s') % (field_name, error))
                if not isinstance(domain, (list, tuple)):
                    raise ValidationError(_('Status domains must be Odoo domain lists.'))

    @api.constrains('approve_method', 'reject_method', 'model_name')
    def _check_methods(self):
        for rule in self:
            for method_name in (rule.approve_method, rule.reject_method):
                if not method_name:
                    continue
                if method_name.startswith('_') or rule.model_name not in self.env:
                    raise ValidationError(_('Select a public method on the configured model.'))
                if not callable(getattr(self.env[rule.model_name], method_name, None)):
                    raise ValidationError(_('Method %s does not exist on %s.') % (method_name, rule.model_name))

    def _status_domain(self, status):
        self.ensure_one()
        return list(ast.literal_eval(self['%s_domain' % status] or '[]'))

    @api.model
    def sync_all(self):
        if not self.env.su and not self.env.user.has_group('approval_center_dashboard.group_approval_manager'):
            from odoo.exceptions import AccessError
            raise AccessError(_('Only Approval Center managers can refresh the index.'))
        Request = self.env['approval.center.request'].sudo()
        for rule in self.sudo().search([('active', '=', True)]):
            try:
                Source = self.env[rule.model_name].sudo()
                alive = set()
                for status in ('pending', 'approved', 'rejected', 'cancelled'):
                    domain = rule._status_domain(status)
                    if not domain:
                        continue
                    for source in Source.search(domain):
                        alive.add(source.id)
                        values = Request._values_from_source(rule, source, status)
                        existing = Request.search([('rule_id', '=', rule.id), ('source_res_id', '=', source.id)], limit=1)
                        if existing:
                            existing.write(values)
                        else:
                            Request.create(values)
                Request.search([('rule_id', '=', rule.id), ('source_res_id', 'not in', list(alive) or [0])]).unlink()
                rule.write({'last_sync': fields.Datetime.now(), 'sync_error': False})
            except Exception as error:
                _logger.exception('Approval rule sync failed: %s', rule.display_name)
                rule.write({'last_sync': fields.Datetime.now(), 'sync_error': str(error)})
        return True
