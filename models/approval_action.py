# -*- coding: utf-8 -*-

import ast

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


FORM_REQUEST_CODES = (
    'it_request', 'online_purchase', 'client_pickup', 'gasoline_allowance',
    'grab_request', 'payment_request', 'cash_advance_request',
    'transport_vehicle', 'official_business', 'overtime_authorization',
)


DEFAULT_ACTIONS = (
    # approval code, key, label, intent, execution, method, action xmlid,
    # reason field, confirmation, availability domain, group xmlids
    ('invoice_cancel', 'approve', 'Approve', 'approve', 'method',
     'action_approve', False, False,
     'Approve this cancellation request?', "[('state', '=', 'requested')]",
     ('dex_invoice_cancel.group_invoice_cancel_approver',)),
    ('invoice_cancel', 'reject', 'Reject', 'reject', 'method',
     'action_reject', False, 'decision_remarks',
     'Reject this cancellation request?', "[('state', '=', 'requested')]",
     ('dex_invoice_cancel.group_invoice_cancel_approver',)),
    ('invoice_update', 'approve', 'Approve', 'approve', 'method',
     'action_approve', False, False,
     'Apply the approved invoice changes?', "[('state', '=', 'requested')]",
     ('dex_invoice_cancel.group_invoice_update_approver',)),
    ('invoice_update', 'reject', 'Reject', 'reject', 'method',
     'action_reject', False, 'decision_remarks',
     'Reject this invoice update request?', "[('state', '=', 'requested')]",
     ('dex_invoice_cancel.group_invoice_update_approver',)),
    ('ns_cancel', 'approve', 'Approve', 'approve', 'method',
     'action_approve', False, False,
     'Approve this NS cancellation?', "[('state', '=', 'requested')]", ()),
    ('ns_cancel', 'reject', 'Reject', 'reject', 'method',
     'action_reject', False, False,
     'Reject this NS cancellation?', "[('state', '=', 'requested')]", ()),
    ('reserve_expiration', 'approve', 'Approve', 'approve', 'method',
     'approve', False, False,
     'Approve this expiration adjustment?', "[('state', '=', 'to_approve')]", ()),
    ('reserve_expiration', 'disapprove', 'Disapprove', 'reject', 'method',
     'disapprove', False, False,
     'Disapprove this expiration adjustment?', "[('state', '=', 'to_approve')]", ()),
    ('discount_approval', 'approve', 'Approve', 'approve', 'method',
     'action_request_approve', False, False,
     'Approve this discount request?', "[('maximum_exceeded', '=', True)]", ()),
    ('warehouse_transfer', 'review', 'Review', 'review', 'method',
     'button_response_approval', False, False,
     False, "[('state', '=', 'draft')]",
     ('dex_whtransfer_approval.group_whtransfer_superapprover',)),
    ('warehouse_pickup', 'approve', 'Approve', 'approve', 'method',
     'button_approved', False, False,
     'Approve this warehouse pickup?', "[('state', '=', 'for_approval')]",
     ('dex_invoice_preprinted.group_warehouse_pickup_approve',)),
    ('warehouse_pickup', 'cancel', 'Cancel', 'cancel', 'method',
     'button_cancel', False, False,
     'Cancel this warehouse pickup?', "[('state', '=', 'for_approval')]",
     ('dex_invoice_preprinted.group_warehouse_pickup_cancel',)),
    ('purchase_request', 'approve', 'Issue Purchase', 'approve', 'method',
     'action_purchase', False, False,
     'Issue this purchase request?', "[('state', '=', 'for_approval')]",
     ('dex_sec.group_request_purchase_to_purchase',)),
    ('purchase_request', 'cancel', 'Cancel', 'cancel', 'method',
     'action_cancel', False, False,
     'Cancel this purchase request?', "[('state', '=', 'for_approval')]", ()),
    ('pricelist_update', 'approve', 'Approve', 'approve', 'method',
     'action_approve', False, False,
     'Approve this pricelist update?', "[('state', '=', 'for_approval')]", ()),
    ('pricelist_update', 'cancel', 'Cancel', 'cancel', 'method',
     'action_cancel', False, False,
     'Cancel this pricelist update?', "[('state', '=', 'for_approval')]", ()),
    ('onboarding', 'approve', 'Approve', 'approve', 'method',
     'status_done', False, False,
     'Approve this onboarding checklist?', "[('state', '=', 'waiting_for_it')]", ()),
    ('onboarding', 'cancel', 'Cancellation Request', 'cancel', 'window_action',
     False, 'dex_onboarding_checklist.dex_form_action_onboarding_cancellation_reason_view',
     False, False, "[('state', '=', 'waiting_for_it')]", ()),
    ('job_request', 'confirm', 'Assign', 'approve', 'method',
     'assigned', False, False,
     'Assign this job request?', "[('state', '=', 'queue')]", ()),
)


class ApprovalDashboardAction(models.Model):
    _name = 'dex_approval_dashboard.action'
    _description = 'Approval Dashboard Native Action'
    _order = 'approval_type_id, sequence, id'

    name = fields.Char(required=True, translate=True)
    key = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    approval_type_id = fields.Many2one(
        'dex_approval_dashboard.type', required=True, ondelete='cascade', index=True)
    source_model_id = fields.Many2one(
        related='approval_type_id.model_id', readonly=True)
    source_model_name = fields.Char(
        related='approval_type_id.model_name', readonly=True)
    intent = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('cancel', 'Cancel'),
        ('review', 'Review'),
        ('other', 'Other'),
    ], required=True, default='other')
    execution_type = fields.Selection([
        ('method', 'Source Method'),
        ('window_action', 'Window / Wizard Action'),
    ], required=True, default='method')
    method_name = fields.Char()
    window_action_id = fields.Many2one('ir.actions.act_window', ondelete='set null')
    availability_domain = fields.Char(default='[]', required=True)
    group_ids = fields.Many2many(
        'res.groups', 'dex_approval_dashboard_action_group_rel',
        'action_id', 'group_id', string='Allowed Groups')
    confirm_message = fields.Char()
    reason_field_id = fields.Many2one(
        'ir.model.fields', string='Required Reason Field', ondelete='set null')

    _sql_constraints = [
        ('type_key_uniq', 'unique(approval_type_id, key)',
         'The action key must be unique for each approval function.'),
    ]

    @api.onchange('approval_type_id')
    def _onchange_approval_type_id(self):
        self.reason_field_id = False

    @api.constrains(
        'execution_type', 'method_name', 'window_action_id',
        'approval_type_id', 'reason_field_id', 'availability_domain')
    def _check_configuration(self):
        for record in self:
            try:
                domain = ast.literal_eval(record.availability_domain or '[]')
            except (SyntaxError, ValueError, TypeError) as exc:
                raise ValidationError(_('Invalid availability domain: %s') % exc)
            if not isinstance(domain, (list, tuple)):
                raise ValidationError(_('Availability domain must be an Odoo domain.'))
            if record.reason_field_id and (
                    record.reason_field_id.model_id != record.approval_type_id.model_id or
                    record.reason_field_id.ttype not in ('char', 'text')):
                raise ValidationError(_(
                    'The reason field must be a text field on the source model.'))
            if record.execution_type == 'method':
                if not record.method_name or record.method_name.startswith('_'):
                    raise ValidationError(_('Select a public source method.'))
                model_name = record.approval_type_id.model_name
                if model_name in self.env and not hasattr(self.env[model_name], record.method_name):
                    raise ValidationError(_(
                        'Method %s does not exist on %s.') %
                        (record.method_name, model_name))
            elif not record.window_action_id:
                raise ValidationError(_('Select a window or wizard action.'))

    def parsed_availability_domain(self):
        self.ensure_one()
        return list(ast.literal_eval(self.availability_domain or '[]'))

    @api.model
    def seed_default_actions(self):
        action_model = self.sudo()
        type_model = self.env['dex_approval_dashboard.type'].sudo()
        field_model = self.env['ir.model.fields'].sudo()
        group_model = self.env['res.groups']

        definitions = list(DEFAULT_ACTIONS)
        reject_action = self.env.ref(
            'dex_form_request_approval.dex_form_action_disapprove_reason_view',
            raise_if_not_found=False)
        if reject_action:
            for code in FORM_REQUEST_CODES:
                definitions.extend([
                    (code, 'approve', 'Approve', 'approve', 'method',
                     'approve_request', False, False,
                     'Approve this request?',
                     "[('approval_status', '=', 'to_approve')]", ()),
                    (code, 'disapprove', 'Disapprove', 'reject', 'window_action',
                     False,
                     'dex_form_request_approval.dex_form_action_disapprove_reason_view',
                     False, False,
                     "[('approval_status', '=', 'to_approve')]", ()),
                ])

        for definition in definitions:
            (type_code, key, label, intent, execution_type, method_name,
             action_xmlid, reason_field, confirm_message, availability_domain,
             group_xmlids) = definition
            approval_type = type_model.search([('code', '=', type_code)], limit=1)
            if not approval_type or approval_type.model_name not in self.env:
                continue
            window_action = (
                self.env.ref(action_xmlid, raise_if_not_found=False)
                if action_xmlid else False)
            if execution_type == 'window_action' and not window_action:
                continue
            if execution_type == 'method' and not hasattr(
                    self.env[approval_type.model_name], method_name):
                continue
            groups = group_model
            for xmlid in group_xmlids:
                group = self.env.ref(xmlid, raise_if_not_found=False)
                if group:
                    groups |= group
            reason = field_model.search([
                ('model', '=', approval_type.model_name),
                ('name', '=', reason_field),
            ], limit=1) if reason_field else field_model
            values = {
                'name': label,
                'intent': intent,
                'execution_type': execution_type,
                'method_name': method_name or False,
                'window_action_id': window_action.id if window_action else False,
                'reason_field_id': reason.id if reason else False,
                'confirm_message': confirm_message or False,
                'availability_domain': availability_domain,
                'group_ids': [(6, 0, groups.ids)],
                'active': True,
            }
            existing = action_model.search([
                ('approval_type_id', '=', approval_type.id),
                ('key', '=', key),
            ], limit=1)
            if existing:
                existing.write(values)
            else:
                values.update({
                    'approval_type_id': approval_type.id,
                    'key': key,
                    'sequence': (action_model.search_count([
                        ('approval_type_id', '=', approval_type.id),
                    ]) + 1) * 10,
                })
                action_model.create(values)
        return True
