# -*- coding: utf-8 -*-

import logging
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.osv import expression
from odoo.tools import html_escape
from odoo.tools.mail import html2plaintext
from odoo.tools.safe_eval import safe_eval


_logger = logging.getLogger(__name__)


class ApprovalDashboardItem(models.Model):
    _name = 'dex_approval_dashboard.item'
    _description = 'Approval Dashboard Request Index'
    _order = 'request_date desc, id desc'

    name = fields.Char(required=True, readonly=True, index=True)
    approval_type_id = fields.Many2one(
        'dex_approval_dashboard.type', required=True, readonly=True,
        ondelete='cascade', index=True)
    category_id = fields.Many2one(
        related='approval_type_id.category_id', store=True, readonly=True, index=True)
    source_model = fields.Char(required=True, readonly=True, index=True)
    source_res_id = fields.Integer(required=True, readonly=True, index=True)
    source_reference = fields.Reference(
        selection='_reference_models', string='Source Record', readonly=True)
    normalized_status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], required=True, readonly=True, index=True)
    source_status = fields.Char(readonly=True)
    request_date = fields.Datetime(readonly=True, index=True)
    requester_user_id = fields.Many2one('res.users', readonly=True, index=True)
    requester_name = fields.Char(readonly=True)
    assigned_user_ids = fields.Many2many(
        'res.users', 'dex_approval_dashboard_item_user_rel',
        'item_id', 'user_id', string='Responsible Users', readonly=True)
    stage_date = fields.Datetime(readonly=True, index=True)
    decision_date = fields.Datetime(readonly=True, index=True)
    department_name = fields.Char(readonly=True, index=True)
    customer_name = fields.Char(readonly=True, index=True)
    project_name = fields.Char(readonly=True, index=True)
    site_name = fields.Char(readonly=True, index=True)
    amount = fields.Float(readonly=True, index=True)
    currency_name = fields.Char(readonly=True)
    stage_name = fields.Char(readonly=True, index=True)
    next_approver_name = fields.Char(readonly=True)
    purpose = fields.Text(readonly=True)
    remarks = fields.Text(readonly=True)
    last_sync = fields.Datetime(readonly=True)

    _sql_constraints = [
        (
            'source_type_uniq',
            'unique(approval_type_id, source_model, source_res_id)',
            'This source request is already indexed for the approval function.',
        ),
    ]

    @api.model
    def _reference_models(self):
        models_available = self.env['dex_approval_dashboard.type'].sudo().search([]).mapped('model_id')
        return [(model.model, model.name) for model in models_available]

    def action_open_source(self):
        self.ensure_one()
        if self.source_model not in self.env:
            raise UserError(_('The source model is no longer available.'))
        source = self.env[self.source_model].browse(self.source_res_id).exists()
        if not source:
            raise UserError(_('The source record no longer exists.'))
        source.check_access_rights('read')
        source.check_access_rule('read')
        return self._normalize_dashboard_window_action({
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self.source_model,
            'res_id': self.source_res_id,
            'view_mode': 'form',
            'target': 'current',
        })

    @api.model
    def _normalize_dashboard_window_action(self, action):
        """Add the view list required by Odoo 13's JS action manager."""
        if not isinstance(action, dict) or action.get('type') != 'ir.actions.act_window':
            return action
        if action.get('views'):
            return action
        view_modes = [
            mode.strip() for mode in (action.get('view_mode') or 'tree,form').split(',')
            if mode.strip()
        ]
        view_id = action.get('view_id')
        if isinstance(view_id, (list, tuple)):
            view_id = view_id[0] if view_id else False
        view_id = view_id or False
        action['views'] = [
            (view_id if index == 0 else False, mode)
            for index, mode in enumerate(view_modes)
        ]
        return action

    def _dashboard_source(self):
        self.ensure_one()
        if self.source_model not in self.env:
            return self.env['res.users']
        return self.env[self.source_model].browse(self.source_res_id).exists()

    @api.model
    def _as_datetime(self, value):
        if not value:
            return False
        if isinstance(value, datetime):
            return value
        if hasattr(value, 'year') and not isinstance(value, str):
            return datetime.combine(value, time.min)
        value = str(value)
        try:
            if len(value) == 10:
                return fields.Datetime.from_string('%s 00:00:00' % value)
            return fields.Datetime.from_string(value)
        except (TypeError, ValueError):
            return False

    @api.model
    def _local_date(self, value):
        value = self._as_datetime(value)
        if not value:
            return False
        return fields.Datetime.context_timestamp(self, value).date()

    @api.model
    def _age_days(self, start_value, end_value=False):
        start_date = self._local_date(start_value)
        if not start_date:
            return False
        end_date = self._local_date(end_value) if end_value else fields.Date.context_today(self)
        if not end_date:
            return False
        return max((end_date - start_date).days, 0)

    def _dashboard_age_values(self):
        self.ensure_one()
        end_value = False
        if self.normalized_status != 'pending':
            if not self.decision_date:
                return {'request_age_days': False, 'stage_age_days': False}
            end_value = self.decision_date
        return {
            'request_age_days': self._age_days(self.request_date, end_value),
            'stage_age_days': self._age_days(self.stage_date, end_value),
        }

    def _dashboard_aging(self):
        self.ensure_one()
        ages = self._dashboard_age_values()
        age = ages['stage_age_days']
        if age is False:
            age = ages['request_age_days']
        if age is False:
            return dict(ages, aging_state='unknown', priority='normal')
        if age >= self.approval_type_id.overdue_days:
            state, priority = 'overdue', 'urgent'
        elif age >= self.approval_type_id.attention_days:
            state, priority = 'attention', 'high'
        else:
            state, priority = 'normal', 'normal'
        return dict(ages, aging_state=state, priority=priority)

    def _dashboard_can_comment(self, source=False):
        self.ensure_one()
        source = source or self._dashboard_source()
        if not source or not hasattr(source, 'message_post'):
            return False
        try:
            source.check_access_rights('read')
            source.check_access_rule('read')
            source.check_access_rights('write')
            source.check_access_rule('write')
        except (AccessError, UserError):
            return False
        return True

    def _dashboard_requester_recipient(self):
        """Return a safe ``Name <email>`` address for Dexterton mail."""
        self.ensure_one()
        user = self.requester_user_id
        if not user:
            return False
        email = user.partner_id.email or user.login
        if not email or '@' not in email or '\n' in email or '\r' in email:
            return False
        name = (user.name or self.requester_name or '').replace('\n', ' ').replace('\r', ' ')
        return '%s <%s>' % (name, email)

    def _dashboard_available_actions(self):
        self.ensure_one()
        if self.normalized_status != 'pending':
            return []
        if self.env.user not in self.assigned_user_ids:
            return []
        source = self._dashboard_source()
        if not source:
            return []
        try:
            source.check_access_rights('read')
            source.check_access_rule('read')
        except (AccessError, UserError):
            return []

        result = []
        for dashboard_action in self.approval_type_id.dashboard_action_ids.filtered('active'):
            if (dashboard_action.group_ids and
                    not dashboard_action.group_ids & self.env.user.groups_id):
                continue
            try:
                matches = source.search_count(expression.AND([
                    [('id', '=', source.id)],
                    dashboard_action.parsed_availability_domain(),
                ]))
            except Exception:
                _logger.exception(
                    'Could not evaluate dashboard action %s for %s,%s',
                    dashboard_action.name, self.source_model, self.source_res_id)
                matches = 0
            if not matches:
                continue
            result.append({
                'id': dashboard_action.id,
                'name': dashboard_action.name,
                'intent': dashboard_action.intent,
                'confirm_message': dashboard_action.confirm_message or False,
                'requires_reason': bool(dashboard_action.reason_field_id),
            })
        return result

    @api.model
    def _dashboard_domain(self, options):
        domain = []
        category_id = int(options.get('category_id') or 0)
        approval_type_id = int(options.get('approval_type_id') or 0)
        status = options.get('status')
        if category_id:
            domain.append(('category_id', '=', category_id))
        if approval_type_id:
            domain.append(('approval_type_id', '=', approval_type_id))
        if status:
            domain.append(('normalized_status', '=', status))
        if options.get('assigned_only', True) is not False:
            domain.append(('assigned_user_ids', 'in', [self.env.uid]))
        exact_filters = (
            ('department', 'department_name'), ('customer', 'customer_name'),
            ('project', 'project_name'), ('site', 'site_name'),
            ('stage', 'stage_name'),
        )
        for option_name, field_name in exact_filters:
            if options.get(option_name):
                domain.append((field_name, '=', options[option_name]))
        if options.get('requester'):
            domain.append(('requester_name', '=', options['requester']))
        if options.get('approver'):
            domain.append(('assigned_user_ids.name', '=', options['approver']))
        if options.get('date_from'):
            domain.append(('request_date', '>=', '%s 00:00:00' % options['date_from']))
        if options.get('date_to'):
            domain.append(('request_date', '<=', '%s 23:59:59' % options['date_to']))
        query = (options.get('query') or '').strip()
        if query:
            domain = expression.AND([domain, expression.OR([
                [('name', 'ilike', query)], [('requester_name', 'ilike', query)],
                [('approval_type_id.name', 'ilike', query)],
                [('category_id.name', 'ilike', query)],
                [('assigned_user_ids.name', 'ilike', query)],
                [('department_name', 'ilike', query)],
                [('customer_name', 'ilike', query)],
                [('project_name', 'ilike', query)], [('site_name', 'ilike', query)],
                [('purpose', 'ilike', query)], [('remarks', 'ilike', query)],
            ])])
        return domain

    @api.model
    def _dashboard_filtered_items(self, options):
        items = self.search(self._dashboard_domain(options))
        quick = options.get('quick')
        priority = options.get('priority')
        today = fields.Date.context_today(self)
        result = []
        for item in items:
            aging = item._dashboard_aging()
            if quick == 'overdue' and not (
                    item.normalized_status == 'pending' and
                    aging['aging_state'] == 'overdue'):
                continue
            if quick == 'today' and not (
                    item.normalized_status == 'approved' and item.decision_date and
                    item._local_date(item.decision_date) == today):
                continue
            if quick == 'rejected' and item.normalized_status != 'rejected':
                continue
            if quick == 'priority' and aging['priority'] not in ('high', 'urgent'):
                continue
            if priority and aging['priority'] != priority:
                continue
            result.append(item)
        return result

    @api.model
    def _dashboard_sort_items(self, items, options):
        sort_field = options.get('sort_field') or 'request_date'
        reverse = options.get('sort_direction') != 'asc'
        if sort_field in ('request_age_days', 'stage_age_days'):
            return sorted(items, key=lambda item: (
                item._dashboard_age_values()[sort_field] is not False,
                item._dashboard_age_values()[sort_field] or -1,
                item.id,
            ), reverse=reverse)
        allowed = {
            'request_date', 'name', 'requester_name', 'approval_type_id',
            'category_id', 'normalized_status', 'amount', 'department_name',
            'customer_name', 'stage_name',
        }
        if sort_field not in allowed:
            sort_field = 'request_date'
        def key(item):
            value = item[sort_field]
            if hasattr(value, 'display_name'):
                value = value.display_name
            return (value not in (False, None, ''), value or '', item.id)
        return sorted(items, key=key, reverse=reverse)

    def _dashboard_row(self):
        self.ensure_one()
        aging = self._dashboard_aging()
        return {
            'id': self.id,
            'approval_type_id': self.approval_type_id.id,
            'category_id': self.category_id.id,
            'request_date': fields.Datetime.to_string(self.request_date)
                if self.request_date else '',
            'name': self.name,
            'requester_name': self.requester_name or '',
            'approval_type': self.approval_type_id.name,
            'category': self.category_id.name,
            'assigned_users': ', '.join(self.assigned_user_ids.mapped('name')),
            'department': self.department_name or '',
            'customer': self.customer_name or '',
            'project': self.project_name or '',
            'site': self.site_name or '',
            'amount': self.amount or 0.0,
            'currency': self.currency_name or '',
            'stage': self.stage_name or '',
            'next_approver': self.next_approver_name or '',
            'purpose': self.purpose or '',
            'remarks': self.remarks or '',
            'status': self.normalized_status,
            'status_label': dict(self._fields['normalized_status'].selection).get(
                self.normalized_status, self.normalized_status),
            'request_age_days': aging['request_age_days'],
            'stage_age_days': aging['stage_age_days'],
            'aging_state': aging['aging_state'],
            'priority': aging['priority'],
            'comment_available': self._dashboard_can_comment(),
            'actions': self._dashboard_available_actions(),
        }

    @api.model
    def _dashboard_filter_options(self):
        items = self.search([])
        def values(field_name):
            return sorted(set(filter(None, items.mapped(field_name))))[:200]
        return {
            'departments': values('department_name'),
            'requesters': values('requester_name'),
            'approvers': sorted(set(items.mapped('assigned_user_ids.name')))[:200],
            'stages': values('stage_name'), 'customers': values('customer_name'),
            'projects': values('project_name'), 'sites': values('site_name'),
        }

    @api.model
    def dashboard_get_data(self, options=None):
        options = options or {}
        page_size = min(max(int(options.get('page_size') or 25), 1), 100)
        page = max(int(options.get('page') or 1), 1)
        items = self._dashboard_sort_items(
            self._dashboard_filtered_items(options), options)
        total = len(items)
        max_page = max((total + page_size - 1) // page_size, 1)
        page = min(page, max_page)
        page_items = items[(page - 1) * page_size:page * page_size]

        count_domain = [
            ('normalized_status', '=', 'pending'),
            ('assigned_user_ids', 'in', [self.env.uid]),
        ]
        grouped_counts = self.read_group(
            count_domain, ['category_id'], ['category_id'], lazy=False)
        counts = {
            row['category_id'][0]: row['__count']
            for row in grouped_counts if row.get('category_id')
        }
        categories = self.env['dex_approval_dashboard.category'].search([
            ('active', '=', True),
        ], order='sequence, name, id')
        approval_types = self.env['dex_approval_dashboard.type'].search([
            ('active', '=', True),
        ], order='category_id, sequence, name, id')
        return {
            'categories': [{
                'id': category.id, 'name': category.name,
                'count': counts.get(category.id, 0), 'color': category.color,
            } for category in categories],
            'all_count': sum(counts.values()),
            'approval_types': [{
                'id': approval_type.id, 'name': approval_type.name,
                'category_id': approval_type.category_id.id,
            } for approval_type in approval_types],
            'filter_options': self._dashboard_filter_options(),
            'rows': [item._dashboard_row() for item in page_items],
            'total': total, 'page': page, 'page_size': page_size,
            'page_count': max_page,
            'is_manager': self.env.user.has_group(
                'dex_approval_dashboard.group_approval_dashboard_manager'),
        }

    @api.model
    def dashboard_get_details(self, item_id):
        item = self.search([('id', '=', int(item_id))], limit=1)
        if not item:
            raise UserError(_('The approval request is unavailable or no longer exists.'))
        source = item._dashboard_source()
        if not source:
            raise UserError(_('The source record no longer exists.'))
        source.check_access_rights('read')
        source.check_access_rule('read')
        messages = []
        if hasattr(source, 'message_post'):
            message_records = self.env['mail.message'].search([
                ('model', '=', source._name), ('res_id', '=', source.id),
                ('message_type', 'in', ('comment', 'notification')),
            ], order='date desc, id desc', limit=20)
            for message in message_records:
                messages.append({
                    'id': message.id,
                    'author': message.author_id.display_name or _('System'),
                    'date': fields.Datetime.to_string(message.date),
                    'body': html2plaintext(message.body or '').strip(),
                })
        result = item._dashboard_row()
        result['messages'] = messages
        return result

    @api.model
    def dashboard_post_comment(self, item_id, body, email_requester=False):
        item = self.search([('id', '=', int(item_id))], limit=1)
        if not item:
            raise UserError(_('The approval request is unavailable or no longer exists.'))
        body = (body or '').strip()
        if not body:
            raise UserError(_('Enter a comment before posting.'))
        source = item._dashboard_source()
        if not source or not item._dashboard_can_comment(source):
            raise AccessError(_('Comments are unavailable for this request.'))
        source.message_post(
            body='<p>%s</p>' % html_escape(body).replace('\n', '<br/>'),
            message_type='comment', subtype_xmlid='mail.mt_comment')
        recipient = item._dashboard_requester_recipient()
        if email_requester and recipient:
            html = '''<p>Dear %s,</p>
<p>A comment was added to your approval request.</p>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Reference</th><td>%s</td></tr>
  <tr><th align="left">Approval Function</th><td>%s</td></tr>
  <tr><th align="left">Commented By</th><td>%s</td></tr>
</table>
<p><strong>Comment</strong><br/>%s</p>''' % (
                html_escape(item.requester_user_id.name or item.requester_name or ''),
                html_escape(item.name or ''),
                html_escape(item.approval_type_id.name or ''),
                html_escape(self.env.user.name or ''),
                html_escape(body).replace('\n', '<br/>'))
            mail = self.env['dex_mail.mail']
            mail.send_external(
                recipient,
                _('Comment on approval request %s') % item.name,
                mail.convert_html(html))
        return item.dashboard_get_details(item.id)

    @api.model
    def dashboard_prepare_multi_action(self, item_ids, dashboard_action_id):
        item_ids = list(dict.fromkeys(int(item_id) for item_id in (item_ids or [])))
        if not item_ids or len(item_ids) > 100:
            raise UserError(_('Select between 1 and 100 approval requests.'))
        items = self.search([('id', 'in', item_ids)])
        if len(items) != len(item_ids):
            raise AccessError(_('One or more selected requests are unavailable.'))
        action = self.env['dex_approval_dashboard.action'].browse(
            int(dashboard_action_id)).exists()
        if not action or action.intent not in ('approve', 'reject'):
            raise AccessError(_('Only configured approve or reject actions may be selected.'))
        if len(items.mapped('approval_type_id')) != 1 or any(
                item.approval_type_id != action.approval_type_id for item in items):
            raise UserError(_(
                'Selected requests must use the same approval function and action.'))
        ordered = items.sorted(key=lambda item: item_ids.index(item.id))
        steps = []
        for item in ordered:
            available = {
                entry['id']: entry for entry in item._dashboard_available_actions()}
            if action.id not in available:
                raise AccessError(_(
                    '%s is no longer actionable for the current user.') % item.name)
            steps.append(dict(available[action.id], item_id=item.id, item_name=item.name))
        return {'action_id': action.id, 'action_name': action.name, 'steps': steps}

    @api.model
    def dashboard_get_analytics(self, options=None):
        options = dict(options or {})
        options.pop('page', None)
        items = self._dashboard_filtered_items(options)
        pending = [item for item in items if item.normalized_status == 'pending']
        def counts(values):
            result = {}
            for value in values:
                value = value or _('Unspecified')
                result[value] = result.get(value, 0) + 1
            return sorted(result.items(), key=lambda entry: (-entry[1], entry[0]))
        aging = {'normal': 0, 'attention': 0, 'overdue': 0, 'unknown': 0}
        for item in pending:
            aging[item._dashboard_aging()['aging_state']] += 1
        completed = [item for item in items if (
            item.normalized_status in ('approved', 'rejected') and
            item.request_date and item.decision_date)]
        turnaround = {}
        completed_counts = {}
        for item in completed:
            age = item._age_days(item.request_date, item.decision_date)
            for approver in item.assigned_user_ids.mapped('name') or [_('Unspecified')]:
                turnaround.setdefault(approver, []).append(age)
                if item.normalized_status == 'approved':
                    completed_counts[approver] = completed_counts.get(approver, 0) + 1
        return {
            'pending_by_category': counts([item.category_id.name for item in pending]),
            'pending_by_department': counts([item.department_name for item in pending]),
            'aging': aging,
            'turnaround': sorted([
                (name, round(sum(values) / float(len(values)), 1))
                for name, values in turnaround.items()
            ], key=lambda entry: (-entry[1], entry[0])),
            'completed_by_approver': sorted(
                completed_counts.items(), key=lambda entry: (-entry[1], entry[0])),
        }

    @api.model
    def dashboard_get_configuration_summary(self):
        if not self.env.user.has_group(
                'dex_approval_dashboard.group_approval_dashboard_manager'):
            raise AccessError(_('Approval Center manager access is required.'))
        approval_types = self.env['dex_approval_dashboard.type'].search([
            ('active', '=', True)], order='category_id, sequence, name')
        return {'rows': [{
            'id': approval_type.id, 'category': approval_type.category_id.name,
            'name': approval_type.name,
            'attention_days': approval_type.attention_days,
            'overdue_days': approval_type.overdue_days,
            'action_count': len(approval_type.dashboard_action_ids.filtered('active')),
            'mapping_count': sum(bool(approval_type[field_name]) for field_name in (
                'stage_date_field_id', 'decision_date_field_id',
                'department_field_id', 'customer_field_id', 'project_field_id',
                'site_field_id', 'amount_field_id', 'currency_field_id',
                'stage_field_id', 'next_approver_field_id', 'purpose_field_id',
                'remarks_field_id')),
        } for approval_type in approval_types]}

    @api.model
    def dashboard_execute_action(self, item_id, dashboard_action_id, reason=False):
        item = self.search([('id', '=', int(item_id))], limit=1)
        if not item:
            raise UserError(_('The approval request is unavailable or no longer exists.'))
        dashboard_action = self.env['dex_approval_dashboard.action'].browse(
            int(dashboard_action_id)).exists()
        if (not dashboard_action or
                dashboard_action.approval_type_id != item.approval_type_id):
            raise AccessError(_('This dashboard action is not allowed for the request.'))
        approval_type = item.approval_type_id
        allowed_ids = [entry['id'] for entry in item._dashboard_available_actions()]
        if dashboard_action.id not in allowed_ids:
            raise AccessError(_('You are not allowed to perform this action.'))

        source = item._dashboard_source()
        if not source:
            raise UserError(_('The source record no longer exists.'))
        source.check_access_rights('write')
        source.check_access_rule('write')
        if dashboard_action.reason_field_id:
            reason = (reason or '').strip()
            if not reason:
                raise UserError(_('A reason is required for this action.'))
            source.write({dashboard_action.reason_field_id.name: reason})

        if dashboard_action.execution_type == 'method':
            method = getattr(source, dashboard_action.method_name, False)
            if not method or dashboard_action.method_name.startswith('_'):
                raise UserError(_('The configured source action is unavailable.'))
            result = method()
        else:
            result = dashboard_action.window_action_id.read()[0]
            action_context = result.get('context') or {}
            if isinstance(action_context, str):
                action_context = safe_eval(action_context, {
                    'uid': self.env.uid,
                    'active_id': source.id,
                    'active_ids': source.ids,
                    'active_model': source._name,
                })
            action_context = dict(action_context or {}, **{
                'active_id': source.id,
                'active_ids': source.ids,
                'active_model': source._name,
            })
            result['context'] = action_context

        opens_dialog = (
            isinstance(result, dict) and
            result.get('type') == 'ir.actions.act_window' and
            result.get('target') == 'new')
        if not opens_dialog:
            self.sudo().sync_type(approval_type.sudo())
        result = self._normalize_dashboard_window_action(result)
        return {
            'action': result if isinstance(result, dict) else False,
            'approval_type_id': approval_type.id,
            'opens_dialog': opens_dialog,
        }

    @api.model
    def dashboard_refresh_type(self, approval_type_id):
        approval_type = self.env['dex_approval_dashboard.type'].browse(
            int(approval_type_id)).exists()
        if not approval_type:
            return False
        approval_type.check_access_rights('read')
        approval_type.check_access_rule('read')
        self.sudo().sync_type(approval_type.sudo())
        return True

    @api.model
    def _user_from_value(self, value):
        users = self.env['res.users']
        if not value:
            return users
        records = value if hasattr(value, '_name') else users
        if records._name == 'res.users':
            return records
        if records._name == 'hr.employee' and 'user_id' in records._fields:
            return records.mapped('user_id')
        return users

    @api.model
    def _field_value(self, source, field):
        if not field or field.name not in source._fields:
            return False
        try:
            return source[field.name]
        except Exception as error:
            _logger.warning(
                'Could not read %s.%s for approval dashboard record %s',
                source._name, field.name, source.id)
            _logger.debug('Source field read error: %s', error)
            return False

    @api.model
    def _field_display_value(self, source, field):
        value = self._field_value(source, field)
        if value in (False, None):
            return False
        if hasattr(value, '_name'):
            return ', '.join(value.mapped('display_name'))
        source_field = source._fields.get(field.name) if field else False
        if source_field and source_field.type == 'selection':
            selection = source_field.selection
            if callable(selection):
                selection = selection(source)
            return dict(selection or []).get(value, value)
        if isinstance(value, bool):
            return _('Yes') if value else _('No')
        return str(value)

    @api.model
    def _mapped_datetime(self, source, field):
        return self._as_datetime(self._field_value(source, field))

    @api.model
    def _prepare_item_values(self, approval_type, source, status, assigned_users):
        name_value = self._field_value(source, approval_type.name_field_id)
        if hasattr(name_value, 'display_name'):
            name_value = name_value.display_name
        name = name_value or source.display_name

        date_value = self._field_value(source, approval_type.date_field_id)
        if date_value and approval_type.date_field_id.ttype == 'date':
            date_value = fields.Datetime.to_string(
                fields.Datetime.from_string('%s 00:00:00' % date_value))
        date_value = date_value or source.create_date

        requester_value = self._field_value(source, approval_type.requester_field_id)
        requester_users = self._user_from_value(requester_value)
        requester_user = requester_users[:1]
        requester_name = getattr(requester_value, 'display_name', False)

        native_approvers = self._user_from_value(
            self._field_value(source, approval_type.approver_field_id))
        all_assigned = assigned_users | native_approvers
        amount_value = self._field_value(source, approval_type.amount_field_id)
        try:
            amount_value = float(amount_value or 0.0)
        except (TypeError, ValueError):
            amount_value = 0.0
        return {
            'name': name,
            'approval_type_id': approval_type.id,
            'source_model': approval_type.model_name,
            'source_res_id': source.id,
            'source_reference': '%s,%s' % (approval_type.model_name, source.id),
            'normalized_status': status,
            'source_status': status,
            'request_date': date_value,
            'requester_user_id': requester_user.id if requester_user else False,
            'requester_name': requester_name or (
                requester_user.name if requester_user else False),
            'assigned_user_ids': [(6, 0, all_assigned.ids)],
            'stage_date': self._mapped_datetime(
                source, approval_type.stage_date_field_id),
            'decision_date': self._mapped_datetime(
                source, approval_type.decision_date_field_id),
            'department_name': self._field_display_value(
                source, approval_type.department_field_id),
            'customer_name': self._field_display_value(
                source, approval_type.customer_field_id),
            'project_name': self._field_display_value(
                source, approval_type.project_field_id),
            'site_name': self._field_display_value(
                source, approval_type.site_field_id),
            'amount': amount_value,
            'currency_name': self._field_display_value(
                source, approval_type.currency_field_id),
            'stage_name': self._field_display_value(
                source, approval_type.stage_field_id),
            'next_approver_name': self._field_display_value(
                source, approval_type.next_approver_field_id),
            'purpose': self._field_display_value(
                source, approval_type.purpose_field_id),
            'remarks': self._field_display_value(
                source, approval_type.remarks_field_id),
        }

    @api.model
    def _item_needs_update(self, item, values):
        scalar_fields = (
            'name', 'normalized_status', 'source_status', 'request_date',
            'requester_name', 'stage_date', 'decision_date',
            'department_name', 'customer_name', 'project_name', 'site_name',
            'amount', 'currency_name', 'stage_name', 'next_approver_name',
            'purpose', 'remarks',
        )
        if any(item[field_name] != values[field_name]
               for field_name in scalar_fields):
            return True
        if item.requester_user_id.id != values['requester_user_id']:
            return True
        assigned_ids = set(values['assigned_user_ids'][0][2])
        return set(item.assigned_user_ids.ids) != assigned_ids

    @api.model
    def sync_type(self, approval_type):
        approval_type.ensure_one()
        source_model = approval_type._source_model().sudo()
        status_ids = {}
        all_ids = set()
        for status in ('pending', 'approved', 'rejected', 'cancelled'):
            # Use the ORM's low-level search so source modules with an unsafe
            # custom ``search`` override cannot inject unrelated domains. The
            # dashboard reads as superuser and applies its own record rules to
            # the normalized items exposed to users.
            ids = source_model._search(approval_type._status_domain(status))
            status_ids[status] = set(ids)
            all_ids.update(ids)

        existing = self.search([('approval_type_id', '=', approval_type.id)])
        existing_by_res_id = {item.source_res_id: item for item in existing}
        responsible_users = approval_type.responsible_user_ids
        responsible_users |= approval_type.responsible_group_ids.mapped('users')

        create_values = []
        for source in source_model.browse(sorted(all_ids)).exists():
            status = next(
                (key for key in ('pending', 'approved', 'rejected', 'cancelled')
                 if source.id in status_ids[key]),
                False,
            )
            if not status:
                continue
            values = self._prepare_item_values(
                approval_type, source, status, responsible_users)
            item = existing_by_res_id.get(source.id)
            if item:
                if (item.normalized_status == 'pending' and status != 'pending' and
                        not values.get('decision_date')):
                    values['decision_date'] = fields.Datetime.now()
                if self._item_needs_update(item, values):
                    values['last_sync'] = fields.Datetime.now()
                    item.write(values)
            else:
                values['last_sync'] = fields.Datetime.now()
                create_values.append(values)
        if create_values:
            self.create(create_values)

        obsolete = existing.filtered(lambda item: item.source_res_id not in all_ids)
        if obsolete:
            obsolete.unlink()
        approval_type.sudo().write({
            'last_sync': fields.Datetime.now(),
            'sync_error': False,
        })
        return True
