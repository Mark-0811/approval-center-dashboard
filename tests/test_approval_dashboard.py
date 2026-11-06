# -*- coding: utf-8 -*-

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import SavepointCase


class TestApprovalDashboard(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super(TestApprovalDashboard, cls).setUpClass()
        cls.category = cls.env['dex_approval_dashboard.category'].create({
            'name': 'Test Approvals',
            'code': 'test_approvals',
        })
        cls.source_model = cls.env['ir.model']._get(
            'dex_approval_dashboard.category')
        cls.name_field = cls.env['ir.model.fields'].search([
            ('model', '=', 'dex_approval_dashboard.category'),
            ('name', '=', 'name'),
        ], limit=1)
        cls.type = cls.env['dex_approval_dashboard.type'].create({
            'name': 'Synthetic Review',
            'code': 'synthetic_review',
            'category_id': cls.category.id,
            'model_id': cls.source_model.id,
            'pending_domain': "[('name', '=', 'SYNTHETIC PENDING')]",
            'approved_domain': "[('name', '=', 'SYNTHETIC APPROVED')]",
            'rejected_domain': "[('name', '=', 'SYNTHETIC REJECTED')]",
            'cancelled_domain': "[('name', '=', 'SYNTHETIC CANCELLED')]",
            'name_field_id': cls.name_field.id,
            'requester_field_id': cls.env['ir.model.fields'].search([
                ('model', '=', 'dex_approval_dashboard.category'),
                ('name', '=', 'create_uid'),
            ], limit=1).id,
            'responsible_user_ids': [(6, 0, [cls.env.user.id])],
        })

    def test_counts_and_sync_follow_source_status(self):
        source = self.env['dex_approval_dashboard.category'].create({
            'name': 'SYNTHETIC PENDING',
            'code': 'synthetic_pending',
        })
        self.assertEqual(self.type.pending_count, 1)
        self.env['dex_approval_dashboard.item'].sync_type(self.type)
        item = self.env['dex_approval_dashboard.item'].search([
            ('approval_type_id', '=', self.type.id),
            ('source_res_id', '=', source.id),
        ])
        self.assertEqual(item.normalized_status, 'pending')
        source.name = 'SYNTHETIC APPROVED'
        self.env['dex_approval_dashboard.item'].sync_type(self.type)
        self.assertEqual(item.normalized_status, 'approved')

    def test_sync_is_idempotent(self):
        source = self.env['dex_approval_dashboard.category'].create({
            'name': 'SYNTHETIC PENDING',
            'code': 'synthetic_idempotency',
        })
        self.env['dex_approval_dashboard.item'].sync_type(self.type)
        item = self.env['dex_approval_dashboard.item'].search([
            ('approval_type_id', '=', self.type.id),
            ('source_res_id', '=', source.id),
        ])
        item.last_sync = '2020-01-01 00:00:00'
        self.env['dex_approval_dashboard.item'].sync_type(self.type)
        self.assertEqual(self.env['dex_approval_dashboard.item'].search_count([
            ('approval_type_id', '=', self.type.id),
            ('source_res_id', '=', source.id),
        ]), 1)
        self.assertEqual(
            item.last_sync,
            fields.Datetime.from_string('2020-01-01 00:00:00'))

    def test_invalid_domain_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.type.pending_domain = 'not a domain'

    def test_empty_status_domain_disables_status(self):
        self.env['dex_approval_dashboard.category'].create({
            'name': 'UNRELATED SOURCE RECORD',
            'code': 'unrelated_source_record',
        })
        self.type.cancelled_domain = '[]'
        self.assertEqual(self.type.cancelled_count, 0)

    def test_dashboard_card_opens_removable_current_user_filter(self):
        action = self.type.action_open_pending()
        self.assertEqual(action['res_model'], 'dex_approval_dashboard.item')
        self.assertEqual(action['views'], [(False, 'tree'), (False, 'form')])
        self.assertEqual(action['context']['search_default_assigned_to_me'], 1)
        self.assertEqual(action['domain'], [
            ('approval_type_id', '=', self.type.id),
            ('normalized_status', '=', 'pending'),
        ])

        all_action = self.type.action_open_all()
        self.assertEqual(all_action['domain'], [
            ('approval_type_id', '=', self.type.id),
        ])

    def test_open_source_action_has_odoo_13_views(self):
        source = self.env['dex_approval_dashboard.category'].create({
            'name': 'SYNTHETIC PENDING',
            'code': 'source_action_pending',
        })
        item = self.env['dex_approval_dashboard.item'].create({
            'name': source.name,
            'approval_type_id': self.type.id,
            'source_model': source._name,
            'source_res_id': source.id,
            'normalized_status': 'pending',
        })
        action = item.action_open_source()
        self.assertEqual(action['views'], [(False, 'form')])

    def test_interactive_dashboard_data_and_native_action(self):
        dashboard_user = self.env['res.users'].search([
            ('id', '!=', self.env.user.id),
            ('active', '=', True),
        ], limit=1)
        self.assertTrue(dashboard_user)
        dashboard_user.write({'groups_id': [(4, self.env.ref(
            'dex_approval_dashboard.group_approval_dashboard_manager').id)]})
        source = self.env['dex_approval_dashboard.category'].create({
            'name': 'SYNTHETIC PENDING',
            'code': 'interactive_pending',
        })
        item = self.env['dex_approval_dashboard.item'].create({
            'name': source.name,
            'approval_type_id': self.type.id,
            'source_model': source._name,
            'source_res_id': source.id,
            'normalized_status': 'pending',
            'requester_user_id': dashboard_user.id,
            'requester_name': dashboard_user.name,
            'assigned_user_ids': [(6, 0, [dashboard_user.id])],
        })
        dashboard_action = self.env['dex_approval_dashboard.action'].create({
            'name': 'Toggle',
            'key': 'toggle',
            'approval_type_id': self.type.id,
            'intent': 'approve',
            'execution_type': 'method',
            'method_name': 'toggle_active',
            'availability_domain': "[('name', '=', 'SYNTHETIC PENDING')]",
        })

        data = self.env['dex_approval_dashboard.item'].with_user(
            dashboard_user).dashboard_get_data({
            'status': 'pending',
            'assigned_only': True,
            'approval_type_id': self.type.id,
        })
        self.assertTrue(item)
        self.assertIn(dashboard_user, item.assigned_user_ids)
        self.assertTrue(data['rows'], data)
        row = next(row for row in data['rows'] if row['id'] == item.id)
        self.assertEqual(row['actions'][0]['id'], dashboard_action.id)
        self.assertGreaterEqual(data['all_count'], 1)

        self.env['dex_approval_dashboard.item'].with_user(
            dashboard_user).dashboard_execute_action(item.id, dashboard_action.id)
        self.assertFalse(source.active)

    def test_dashboard_rejects_action_from_another_type(self):
        source = self.env['dex_approval_dashboard.category'].create({
            'name': 'SYNTHETIC PENDING',
            'code': 'action_mismatch_pending',
        })
        self.env['dex_approval_dashboard.item'].sync_type(self.type)
        item = self.env['dex_approval_dashboard.item'].search([
            ('approval_type_id', '=', self.type.id),
            ('source_res_id', '=', source.id),
        ])
        other_type = self.type.copy({'code': 'other_synthetic_review'})
        other_action = self.env['dex_approval_dashboard.action'].create({
            'name': 'Other Toggle',
            'key': 'other_toggle',
            'approval_type_id': other_type.id,
            'intent': 'approve',
            'execution_type': 'method',
            'method_name': 'toggle_active',
        })
        with self.assertRaises(AccessError):
            self.env['dex_approval_dashboard.item'].dashboard_execute_action(
                item.id, other_action.id)

    def test_dashboard_action_blocks_private_or_missing_methods(self):
        with self.assertRaises(ValidationError):
            self.env['dex_approval_dashboard.action'].create({
                'name': 'Unsafe',
                'key': 'unsafe',
                'approval_type_id': self.type.id,
                'intent': 'other',
                'execution_type': 'method',
                'method_name': '_search',
            })
        with self.assertRaises(ValidationError):
            self.env['dex_approval_dashboard.action'].create({
                'name': 'Missing',
                'key': 'missing',
                'approval_type_id': self.type.id,
                'intent': 'other',
                'execution_type': 'method',
                'method_name': 'definitely_not_a_real_method',
            })

    def test_age_values_are_separate_and_future_dates_are_clamped(self):
        item = self.env['dex_approval_dashboard.item'].create({
            'name': 'AGE TEST',
            'approval_type_id': self.type.id,
            'source_model': 'dex_approval_dashboard.category',
            'source_res_id': self.category.id,
            'normalized_status': 'pending',
            'request_date': '2026-01-01 00:00:00',
            'stage_date': '2026-01-03 00:00:00',
        })
        ages = item.with_context(tz='UTC')._dashboard_age_values()
        self.assertGreaterEqual(ages['request_age_days'], ages['stage_age_days'])
        item.stage_date = '2099-01-01 00:00:00'
        self.assertEqual(item.with_context(tz='UTC')._dashboard_age_values()[
            'stage_age_days'], 0)
        item.write({'normalized_status': 'approved', 'decision_date': False})
        self.assertEqual(item._dashboard_age_values(), {
            'request_age_days': False, 'stage_age_days': False,
        })

    def test_source_comment_posts_without_changing_approval_state(self):
        partner_model = self.env['ir.model']._get('res.partner')
        partner_type = self.env['dex_approval_dashboard.type'].create({
            'name': 'Partner Review', 'code': 'partner_review',
            'category_id': self.category.id,
            'model_id': partner_model.id,
            'pending_domain': "[('name', '=', 'Synthetic Comment Source')]",
            'approved_domain': "[('id', '=', 0)]",
            'rejected_domain': "[('id', '=', 0)]",
        })
        partner = self.env.user.partner_id
        partner.email = 'requester@example.com'
        item = self.env['dex_approval_dashboard.item'].create({
            'name': 'COMMENT TEST',
            'approval_type_id': partner_type.id,
            'source_model': 'res.partner',
            'source_res_id': partner.id,
            'normalized_status': 'pending',
            'requester_user_id': self.env.user.id,
            'requester_name': self.env.user.name,
            'assigned_user_ids': [(6, 0, [self.env.uid])],
        })
        result = self.env['dex_approval_dashboard.item'].dashboard_post_comment(
            item.id, 'Synthetic approval comment', email_requester=True)
        self.assertEqual(item.normalized_status, 'pending')
        self.assertTrue(any(
            'Synthetic approval comment' in message['body']
            for message in result['messages']))
        mail = self.env['mail.mail'].search([
            ('email_to', '=', '%s <requester@example.com>' % self.env.user.name),
            ('subject', '=', 'Comment on approval request COMMENT TEST'),
        ], limit=1)
        self.assertTrue(mail)
        self.assertIn('Synthetic approval comment', mail.body_html)
        with self.assertRaises(UserError):
            self.env['dex_approval_dashboard.item'].dashboard_post_comment(
                item.id, '   ')

    def test_comment_is_hidden_without_mail_thread(self):
        item = self.env['dex_approval_dashboard.item'].create({
            'name': 'NO CHATTER',
            'approval_type_id': self.type.id,
            'source_model': self.category._name,
            'source_res_id': self.category.id,
            'normalized_status': 'pending',
        })
        self.assertFalse(item._dashboard_can_comment())

    def test_multi_action_requires_exact_same_type_and_action(self):
        dashboard_user = self.env['res.users'].search([
            ('id', '!=', self.env.user.id), ('active', '=', True),
        ], limit=1)
        dashboard_user.write({'groups_id': [(4, self.env.ref(
            'dex_approval_dashboard.group_approval_dashboard_manager').id)]})
        sources = self.env['dex_approval_dashboard.category'].create([
            {'name': 'SYNTHETIC PENDING', 'code': 'multi_pending_one'},
            {'name': 'SYNTHETIC PENDING', 'code': 'multi_pending_two'},
        ])
        items = self.env['dex_approval_dashboard.item']
        for source in sources:
            items |= self.env['dex_approval_dashboard.item'].create({
                'name': source.code,
                'approval_type_id': self.type.id,
                'source_model': source._name,
                'source_res_id': source.id,
                'normalized_status': 'pending',
                'assigned_user_ids': [(6, 0, [dashboard_user.id])],
            })
        action = self.env['dex_approval_dashboard.action'].create({
            'name': 'Approve', 'key': 'multi_approve',
            'approval_type_id': self.type.id, 'intent': 'approve',
            'execution_type': 'method', 'method_name': 'toggle_active',
            'availability_domain': '[]',
        })
        prepared = self.env['dex_approval_dashboard.item'].with_user(
            dashboard_user).dashboard_prepare_multi_action(items.ids, action.id)
        self.assertEqual([step['item_id'] for step in prepared['steps']], items.ids)
        other_type = self.type.copy({'code': 'multi_other_type'})
        items[1].approval_type_id = other_type
        with self.assertRaises(UserError):
            self.env['dex_approval_dashboard.item'].with_user(
                dashboard_user).dashboard_prepare_multi_action(items.ids, action.id)

    def test_date_mapping_requires_date_field(self):
        with self.assertRaises(ValidationError):
            self.type.stage_date_field_id = self.name_field
