from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html_escape


class ApprovalRequest(models.Model):
    _name = 'approval.center.request'
    _description = 'Approval Request Index'
    _order = 'request_date desc, id desc'

    name = fields.Char(required=True, index=True)
    rule_id = fields.Many2one('approval.center.rule', required=True, ondelete='cascade', index=True)
    category_id = fields.Many2one(related='rule_id.category_id', store=True, index=True)
    source_model = fields.Char(required=True, index=True)
    source_res_id = fields.Integer(required=True, index=True)
    request_date = fields.Datetime(index=True)
    requester_id = fields.Many2one('res.users', index=True)
    requester_name = fields.Char()
    approver_ids = fields.Many2many('res.users', string='Responsible Approvers')
    purpose = fields.Text()
    status = fields.Selection([('pending','Pending'),('approved','Approved'),('rejected','Rejected'),('cancelled','Cancelled')], required=True, index=True)

    _sql_constraints = [('source_unique', 'unique(rule_id, source_res_id)', 'A source record can only be indexed once per rule.')]

    @api.model
    def _values_from_source(self, rule, source, status):
        def mapped(field):
            if not field or field.name not in source._fields:
                return False
            return source[field.name]

        requester = mapped(rule.requester_field_id)
        if requester and getattr(requester, '_name', False) == 'res.partner':
            requester = self.env['res.users'].search([('partner_id', '=', requester.id)], limit=1)
        if requester and getattr(requester, '_name', False) != 'res.users':
            requester = False
        approvers = mapped(rule.approver_field_id)
        if approvers and getattr(approvers, '_name', False) == 'hr.employee':
            approvers = approvers.mapped('user_id')
        if not approvers or getattr(approvers, '_name', False) != 'res.users':
            approvers = rule.approver_user_ids
        if rule.approver_group_ids:
            approvers |= self.env['res.users'].search([('groups_id', 'in', rule.approver_group_ids.ids)])
        date_value = mapped(rule.date_field_id) or source.create_date
        if rule.date_field_id and rule.date_field_id.ttype == 'date' and date_value:
            date_value = fields.Datetime.to_datetime(date_value)
        name_value = mapped(rule.name_field_id)
        return {
            'name': getattr(name_value, 'display_name', name_value) or source.display_name,
            'rule_id': rule.id, 'source_model': source._name, 'source_res_id': source.id,
            'request_date': date_value, 'requester_id': requester.id if requester else False,
            'requester_name': requester.name if requester else getattr(mapped(rule.requester_field_id), 'display_name', False),
            'approver_ids': [(6, 0, approvers.ids)],
            'purpose': str(mapped(rule.purpose_field_id) or ''), 'status': status,
        }

    @api.model
    def dashboard_get_data(self, options=None):
        options = options or {}
        domain = []
        if options.get('category_id'):
            domain.append(('category_id', '=', int(options['category_id'])))
        if options.get('rule_id'):
            domain.append(('rule_id', '=', int(options['rule_id'])))
        if options.get('status'):
            domain.append(('status', '=', options['status']))
        if options.get('mine', True):
            domain.append(('approver_ids', 'in', self.env.uid))
        query = (options.get('query') or '').strip()
        if query:
            domain += ['|', '|', ('name', 'ilike', query), ('requester_name', 'ilike', query), ('purpose', 'ilike', query)]
        page = max(int(options.get('page') or 1), 1)
        limit = min(max(int(options.get('limit') or 25), 1), 100)
        count = self.search_count(domain)
        rows = self.search(domain, offset=(page - 1) * limit, limit=limit, order='request_date desc, id desc')
        categories = self.env['approval.center.category'].search([('active', '=', True)], order='sequence,name')
        return {
            'categories': [{'id': c.id, 'name': c.name, 'count': self.search_count([('category_id','=',c.id),('status','=','pending'),('approver_ids','in',self.env.uid)])} for c in categories],
            'all_count': self.search_count([('status','=','pending'),('approver_ids','in',self.env.uid)]),
            'rows': [{'id': r.id, 'name': r.name, 'category': r.category_id.name, 'rule': r.rule_id.name,
                      'requester': r.requester_name or '', 'date': fields.Datetime.to_string(r.request_date) if r.request_date else '',
                      'purpose': r.purpose or '', 'status': r.status, 'approvers': ', '.join(r.approver_ids.mapped('name')),
                      'can_decide': r.status == 'pending' and self.env.user in r.approver_ids,
                      'can_comment': self._source_supports_chatter(r)} for r in rows],
            'total': count, 'page': page, 'limit': limit, 'pages': max((count + limit - 1) // limit, 1),
        }

    @api.model
    def _source_supports_chatter(self, request):
        return request.source_model in self.env and 'message_ids' in self.env[request.source_model]._fields

    def _source(self):
        self.ensure_one()
        if self.source_model not in self.env:
            raise UserError(_('The source model is unavailable.'))
        source = self.env[self.source_model].browse(self.source_res_id).exists()
        if not source:
            raise UserError(_('The source record no longer exists.'))
        source.check_access_rights('read')
        source.check_access_rule('read')
        return source

    @api.model
    def dashboard_decide(self, request_id, decision, reason=''):
        request = self.search([('id', '=', int(request_id))], limit=1)
        if not request or request.status != 'pending' or self.env.user not in request.approver_ids:
            raise AccessError(_('This request is no longer assigned to you.'))
        rule = request.rule_id
        method_name = rule.approve_method if decision == 'approved' else rule.reject_method
        if decision not in ('approved', 'rejected') or not method_name:
            raise AccessError(_('No configured action is available.'))
        source = request._source()
        source.check_access_rights('write')
        source.check_access_rule('write')
        if not any(source.search([('id', '=', source.id)] + rule._status_domain('pending'))):
            raise UserError(_('The source request is no longer pending.'))
        result = getattr(source, method_name)()
        self.env['approval.center.rule'].sync_all()
        return result if isinstance(result, dict) else True

    @api.model
    def dashboard_comment(self, request_id, body, email_requester=False):
        request = self.search([('id', '=', int(request_id))], limit=1)
        if not request:
            raise AccessError(_('Request unavailable.'))
        source = request._source()
        if not self._source_supports_chatter(request):
            raise UserError(_('The source record does not support chatter.'))
        source.check_access_rights('write')
        source.check_access_rule('write')
        body = (body or '').strip()
        if not body:
            raise UserError(_('Enter a comment.'))
        source.message_post(body='<p>%s</p>' % html_escape(body).replace('\n','<br/>'))
        if email_requester and request.requester_id and request.requester_id.email:
            self.env['mail.mail'].sudo().create({
                'subject': _('Comment on approval request %s') % request.name,
                'email_to': request.requester_id.email,
                'body_html': '<p>%s</p><p>%s</p>' % (html_escape(request.name), html_escape(body)),
            }).send()
        return True

    @api.model
    def dashboard_open_source(self, request_id):
        request = self.search([('id', '=', int(request_id))], limit=1)
        source = request._source()
        view = self.env['ir.ui.view'].search([('model', '=', source._name), ('type', '=', 'form')], limit=1)
        return {'type': 'ir.actions.act_window', 'name': request.name, 'res_model': source._name,
                'res_id': source.id, 'view_mode': 'form', 'views': [(view.id if view else False, 'form')]}
