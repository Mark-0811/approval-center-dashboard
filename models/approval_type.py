# -*- coding: utf-8 -*-

import ast
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


_logger = logging.getLogger(__name__)


class ApprovalDashboardType(models.Model):
    _name = 'dex_approval_dashboard.type'
    _description = 'Approval Dashboard Function'
    _order = 'category_id, sequence, name, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True, copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category_id = fields.Many2one(
        'dex_approval_dashboard.category', required=True, ondelete='restrict')
    color = fields.Integer(related='category_id.color', readonly=True)

    model_id = fields.Many2one(
        'ir.model', string='Source Model', required=True, ondelete='restrict',
        domain=[('transient', '=', False)])
    model_name = fields.Char(related='model_id.model', store=True, readonly=True)
    menu_id = fields.Many2one('ir.ui.menu', string='Original Menu', ondelete='set null')
    action_id = fields.Many2one(
        'ir.actions.act_window', string='Original Window Action', ondelete='set null')

    pending_domain = fields.Char(required=True, default='[]')
    approved_domain = fields.Char(required=True, default='[]')
    rejected_domain = fields.Char(required=True, default='[]')
    cancelled_domain = fields.Char(default='[]')
    extra_domain = fields.Char(
        default='[]', help='Applied together with every status domain.')

    name_field_id = fields.Many2one(
        'ir.model.fields', string='Display Name Field', ondelete='set null')
    date_field_id = fields.Many2one(
        'ir.model.fields', string='Request Date Field', ondelete='set null')
    requester_field_id = fields.Many2one(
        'ir.model.fields', string='Requester Field', ondelete='set null')
    approver_field_id = fields.Many2one(
        'ir.model.fields', string='Native Approver Field', ondelete='set null')
    stage_date_field_id = fields.Many2one(
        'ir.model.fields', string='Current Stage Date Field', ondelete='set null')
    decision_date_field_id = fields.Many2one(
        'ir.model.fields', string='Decision Date Field', ondelete='set null')
    department_field_id = fields.Many2one(
        'ir.model.fields', string='Department Field', ondelete='set null')
    customer_field_id = fields.Many2one(
        'ir.model.fields', string='Customer Field', ondelete='set null')
    project_field_id = fields.Many2one(
        'ir.model.fields', string='Project Field', ondelete='set null')
    site_field_id = fields.Many2one(
        'ir.model.fields', string='Site Field', ondelete='set null')
    amount_field_id = fields.Many2one(
        'ir.model.fields', string='Amount Field', ondelete='set null')
    currency_field_id = fields.Many2one(
        'ir.model.fields', string='Currency Field', ondelete='set null')
    stage_field_id = fields.Many2one(
        'ir.model.fields', string='Approval Stage Field', ondelete='set null')
    next_approver_field_id = fields.Many2one(
        'ir.model.fields', string='Next Approver Field', ondelete='set null')
    purpose_field_id = fields.Many2one(
        'ir.model.fields', string='Purpose Field', ondelete='set null')
    remarks_field_id = fields.Many2one(
        'ir.model.fields', string='Remarks Field', ondelete='set null')
    attention_days = fields.Integer(default=2, required=True)
    overdue_days = fields.Integer(default=4, required=True)

    responsible_user_ids = fields.Many2many(
        'res.users', 'dex_approval_dashboard_type_user_rel',
        'type_id', 'user_id', string='Additional Responsible Users')
    responsible_group_ids = fields.Many2many(
        'res.groups', 'dex_approval_dashboard_type_group_rel',
        'type_id', 'group_id', string='Responsible Groups')
    dashboard_action_ids = fields.One2many(
        'dex_approval_dashboard.action', 'approval_type_id',
        string='Dashboard Actions')

    pending_count = fields.Integer(compute='_compute_counts')
    approved_count = fields.Integer(compute='_compute_counts')
    rejected_count = fields.Integer(compute='_compute_counts')
    cancelled_count = fields.Integer(compute='_compute_counts')
    total_count = fields.Integer(compute='_compute_counts')
    last_sync = fields.Datetime(readonly=True, copy=False)
    sync_error = fields.Text(readonly=True, copy=False)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The approval function code must be unique.'),
    ]

    @api.onchange('model_id')
    def _onchange_model_id(self):
        for field_name in self._source_mapping_field_names():
            setattr(self, field_name, False)

    @api.model
    def _source_mapping_field_names(self):
        return (
            'name_field_id', 'date_field_id', 'requester_field_id',
            'approver_field_id', 'stage_date_field_id',
            'decision_date_field_id', 'department_field_id',
            'customer_field_id', 'project_field_id', 'site_field_id',
            'amount_field_id', 'currency_field_id', 'stage_field_id',
            'next_approver_field_id', 'purpose_field_id', 'remarks_field_id',
        )

    @api.constrains(
        'model_id', 'name_field_id', 'date_field_id',
        'requester_field_id', 'approver_field_id', 'stage_date_field_id',
        'decision_date_field_id', 'department_field_id',
        'customer_field_id', 'project_field_id', 'site_field_id',
        'amount_field_id', 'currency_field_id', 'stage_field_id',
        'next_approver_field_id', 'purpose_field_id', 'remarks_field_id')
    def _check_configured_fields(self):
        for record in self:
            for field_name in record._source_mapping_field_names():
                field = record[field_name]
                if field and field.model_id != record.model_id:
                    raise ValidationError(_(
                        'Configured fields must belong to the selected source model.'))
            for field in (record.date_field_id, record.stage_date_field_id,
                          record.decision_date_field_id):
                if field and field.ttype not in ('date', 'datetime'):
                    raise ValidationError(_(
                        'Request, stage, and decision date mappings must use date fields.'))
            if (record.amount_field_id and
                    record.amount_field_id.ttype not in ('integer', 'float', 'monetary')):
                raise ValidationError(_('The amount mapping must use a numeric field.'))
            if (record.currency_field_id and
                    (record.currency_field_id.ttype != 'many2one' or
                     record.currency_field_id.relation != 'res.currency')):
                raise ValidationError(_(
                    'The currency mapping must be a Currency many-to-one field.'))

    @api.constrains('attention_days', 'overdue_days')
    def _check_sla_thresholds(self):
        for record in self:
            if record.attention_days < 0:
                raise ValidationError(_('Attention days cannot be negative.'))
            if record.overdue_days <= record.attention_days:
                raise ValidationError(_(
                    'Overdue days must be greater than attention days.'))

    @api.constrains(
        'pending_domain', 'approved_domain', 'rejected_domain',
        'cancelled_domain', 'extra_domain')
    def _check_domains(self):
        for record in self:
            for field_name in (
                    'pending_domain', 'approved_domain', 'rejected_domain',
                    'cancelled_domain', 'extra_domain'):
                record._parse_domain(getattr(record, field_name), field_name)

    def _parse_domain(self, value, label=None):
        try:
            domain = ast.literal_eval(value or '[]')
        except (SyntaxError, ValueError, TypeError) as exc:
            raise ValidationError(_(
                'Invalid domain in %s: %s') % (label or self.name, exc))
        if not isinstance(domain, (list, tuple)):
            raise ValidationError(_('%s must be an Odoo domain.') % (label or self.name))
        return list(domain)

    def _status_domain(self, status):
        self.ensure_one()
        value = getattr(self, '%s_domain' % status)
        status_domain = self._parse_domain(value, '%s_domain' % status)
        if not status_domain:
            # An empty status mapping disables that status. Treating ``[]``
            # as an ordinary domain would incorrectly classify every source
            # record under statuses that do not apply to that workflow.
            return [('id', '=', 0)]
        return expression.AND([
            self._parse_domain(self.extra_domain, 'extra_domain'),
            status_domain,
        ])

    def _source_model(self):
        self.ensure_one()
        if not self.model_name or self.model_name not in self.env:
            raise UserError(_(
                'The source model %s is not available in this database.') %
                (self.model_name or self.model_id.name))
        return self.env[self.model_name]

    def _safe_search_count(self, domain):
        self.ensure_one()
        try:
            # Bypass unsafe custom ``search`` overrides in legacy source
            # modules while retaining the ORM domain compiler.
            return self._source_model().sudo()._search(domain, count=True)
        except Exception:
            _logger.exception('Unable to count approval function %s', self.code)
            return 0

    @api.depends(
        'model_name', 'pending_domain', 'approved_domain',
        'rejected_domain', 'cancelled_domain', 'extra_domain')
    def _compute_counts(self):
        for record in self:
            counts = {}
            for status in ('pending', 'approved', 'rejected', 'cancelled'):
                try:
                    counts[status] = record._safe_search_count(
                        record._status_domain(status))
                except (UserError, ValidationError):
                    counts[status] = 0
            record.pending_count = counts['pending']
            record.approved_count = counts['approved']
            record.rejected_count = counts['rejected']
            record.cancelled_count = counts['cancelled']
            record.total_count = sum(counts.values())

    def _open_dashboard_items(self, title, status=False):
        self.ensure_one()
        domain = [('approval_type_id', '=', self.id)]
        if status:
            domain.append(('normalized_status', '=', status))
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'dex_approval_dashboard.item',
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'domain': domain,
            'context': {
                'search_default_assigned_to_me': 1,
            },
        }

    def action_open_pending(self):
        self.ensure_one()
        return self._open_dashboard_items(
            _('%s - Pending') % self.name, 'pending')

    def action_open_approved(self):
        self.ensure_one()
        return self._open_dashboard_items(
            _('%s - Approved') % self.name, 'approved')

    def action_open_rejected(self):
        self.ensure_one()
        return self._open_dashboard_items(
            _('%s - Rejected') % self.name, 'rejected')

    def action_open_cancelled(self):
        self.ensure_one()
        return self._open_dashboard_items(
            _('%s - Cancelled') % self.name, 'cancelled')

    def action_open_all(self):
        self.ensure_one()
        return self._open_dashboard_items(_('%s - All Requests') % self.name)

    def action_sync(self):
        self.ensure_one()
        self.env['dex_approval_dashboard.item'].sudo().sync_type(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Approval Center'),
                'message': _('%s was refreshed.') % self.name,
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def action_sync_all(self):
        for approval_type in self.search([('active', '=', True)]):
            try:
                self.env['dex_approval_dashboard.item'].sudo().sync_type(approval_type)
            except Exception as exc:
                _logger.exception('Approval dashboard sync failed for %s', approval_type.code)
                approval_type.sudo().write({
                    'sync_error': str(exc),
                    'last_sync': fields.Datetime.now(),
                })
        return True

    @api.model
    def _cron_sync_all(self):
        return self.action_sync_all()
