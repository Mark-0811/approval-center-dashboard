# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


CATEGORIES = (
    ('invoicing', 'Invoicing Approvals', 10, 4),
    ('form_requests', 'Form Request Approvals', 20, 2),
    ('sales', 'Sales Approvals', 30, 1),
    ('warehouse', 'Warehouse Approvals', 40, 3),
    ('purchase', 'Purchase Approvals', 50, 5),
    ('pricing', 'Pricing Approvals', 60, 6),
    ('finance', 'Finance Approvals', 70, 7),
)


APPROVAL_FUNCTIONS = (
    # code, label, category, model, pending, approved, rejected, cancelled,
    # name field, date field, requester field, approver field, group xmlids
    (
        'invoice_cancel', 'Invoice Cancellation', 'invoicing',
        'dex.invoice.cancel.request',
        "[('state', '=', 'requested')]", "[('state', '=', 'approved')]",
        "[('state', '=', 'rejected')]", '[]',
        'name', 'requested_date', 'requested_by_id', False,
        ('dex_invoice_cancel.group_invoice_cancel_approver',),
    ),
    (
        'invoice_update', 'Invoice Update', 'invoicing',
        'dex.invoice.update.request',
        "[('state', '=', 'requested')]", "[('state', '=', 'approved')]",
        "[('state', '=', 'rejected')]", '[]',
        'name', 'requested_date', 'requested_by_id', False,
        ('dex_invoice_cancel.group_invoice_update_approver',),
    ),
    (
        'it_request', 'IT Request Form', 'form_requests', 'it.request.form',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'online_purchase', 'Online Purchases Form', 'form_requests', 'on.line.purchases',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'client_pickup', 'Client Pickup Permit', 'form_requests', 'client.pick.up.permit',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'gasoline_allowance', 'Gasoline Allowance', 'form_requests', 'gasoline.allowance.form',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'grab_request', 'Grab Request Form', 'form_requests', 'grab.request.form',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'payment_request', 'Payment Request Form', 'form_requests', 'payment.request.form',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'cash_advance_request', 'Request for Cash Advance', 'form_requests',
        'request.for.cash.advance',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'transport_vehicle', 'Transport Network Vehicle', 'form_requests',
        'transport.network.vehicle.form',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'official_business', 'Official Business Form', 'form_requests',
        'official.business.form',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'overtime_authorization', 'Overtime Authorization', 'form_requests',
        'overtime.authorization.form',
        "[('approval_status', '=', 'to_approve')]", "[('approval_status', '=', 'approved')]",
        "[('approval_status', '=', 'disapprove')]", "[('approval_status', '=', 'cancel')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'job_request', 'Job Request', 'form_requests', 'job.request',
        "[('state', '=', 'queue')]", "[('state', 'in', ('assigned', 'ongoing', 'on_hold', 'done'))]",
        "[('state', '=', 'rejected')]", "[('state', '=', 'cancelled')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'onboarding', 'Onboarding Checklist', 'form_requests',
        'employee.onboarding.checklist',
        "[('state', '=', 'waiting_for_it')]", "[('state', '=', 'done')]",
        '[]', "[('state', '=', 'cancelled')]",
        'name', 'create_date', 'requesters_id', 'approver_id', (),
    ),
    (
        'ns_cancel', 'NS Cancellation', 'sales', 'ns.cancel.request',
        "[('state', '=', 'requested')]", "[('state', '=', 'approved')]",
        "[('state', '=', 'rejected')]", '[]',
        'name', 'requested_date', 'requested_by_id', 'approver_user_ids', (),
    ),
    (
        'reserve_expiration', 'Reserve Expiration Adjustment', 'sales', 'adjust.expiration',
        "[('state', '=', 'to_approve')]", "[('state', '=', 'approved')]",
        "[('state', '=', 'disapprove')]", '[]',
        'name', 'create_date', 'submitted_by', 'reserve_expiry_approvers', (),
    ),
    (
        'discount_approval', 'Sales Discount Approval', 'sales', 'sale.order.line',
        "[('last_sent_request', '!=', False), ('maximum_exceeded', '=', True)]",
        "[('last_approved', '!=', False), ('maximum_exceeded', '=', False)]",
        '[]', '[]', 'name', 'last_sent_request', False, False, (),
    ),
    (
        'warehouse_transfer', 'Warehouse Transfer', 'warehouse', 'warehouse.order',
        "[('state', '=', 'draft'), ('approval_status', 'in', ('pending_approval', 'needs_approval', 'partial_approve'))]",
        "[('approval_status', '=', 'approved')]", "[('approval_status', '=', 'rejected')]",
        "[('state', '=', 'cancel')]", 'name', 'create_date', 'user_id', False,
        ('dex_whtransfer_approval.group_whtransfer_superapprover',),
    ),
    (
        'warehouse_pickup', 'Warehouse Pickup', 'warehouse',
        'dex_invoice_preprinted.warehouse_pickup',
        "[('state', '=', 'for_approval')]",
        "[('state', 'in', ('approved', 'partial_released', 'released'))]",
        '[]', "[('state', '=', 'cancel')]", 'name', 'create_date', 'create_uid', False,
        ('dex_invoice_preprinted.group_warehouse_pickup_approve',),
    ),
    (
        'purchase_request', 'Purchase Request', 'purchase', 'mits_purchase_request.order',
        "[('state', '=', 'for_approval')]", "[('state', '=', 'purchase')]",
        '[]', "[('state', '=', 'cancelled')]", 'name', 'date_request', 'user_id', False,
        ('dex_sec.group_request_purchase_to_purchase',),
    ),
    (
        'pricelist_update', 'Pricelist Update', 'pricing',
        'dex_pricelist_update.pricelist',
        "[('state', '=', 'for_approval')]", "[('state', '=', 'approved')]",
        '[]', "[('state', '=', 'cancelled')]", 'name', 'create_date', 'create_uid', False,
        (),
    ),
    (
        'remittance', 'Remittance', 'finance', 'dex_remittance.remittance',
        "[('state', '=', 'ready')]", "[('state', '=', 'done')]",
        '[]', "[('state', '=', 'cancel')]", 'name', 'create_date', 'requested_by', False,
        (),
    ),
)


def _field(env, model_name, field_name):
    if not field_name:
        return env['ir.model.fields']
    return env['ir.model.fields'].sudo().search([
        ('model', '=', model_name),
        ('name', '=', field_name),
    ], limit=1)


def _groups(env, xmlids):
    groups = env['res.groups']
    for xmlid in xmlids:
        group = env.ref(xmlid, raise_if_not_found=False)
        if group:
            groups |= group
    return groups


def _seed_dashboard(env):
    category_model = env['dex_approval_dashboard.category'].sudo()
    type_model = env['dex_approval_dashboard.type'].sudo()
    categories = {}
    for code, name, sequence, color in CATEGORIES:
        category = category_model.search([('code', '=', code)], limit=1)
        values = {
            'name': name,
            'sequence': sequence,
            'color': color,
            'active': True,
        }
        if category:
            category.write(values)
        else:
            values['code'] = code
            category = category_model.create(values)
        categories[code] = category

    available_models = env.registry.models
    sequence_by_category = {}
    for definition in APPROVAL_FUNCTIONS:
        (
            code, name, category_code, model_name,
            pending_domain, approved_domain, rejected_domain, cancelled_domain,
            name_field, date_field, requester_field, approver_field, group_xmlids,
        ) = definition
        if model_name not in available_models:
            _logger.info(
                'Skipping approval dashboard function %s because %s is not installed',
                code, model_name)
            continue
        model = env['ir.model'].sudo()._get(model_name)
        if not model:
            continue
        sequence_by_category[category_code] = sequence_by_category.get(category_code, 0) + 10
        action = env['ir.actions.act_window'].sudo().search([
            ('res_model', '=', model_name),
        ], order='id', limit=1)
        values = {
            'name': name,
            'category_id': categories[category_code].id,
            'sequence': sequence_by_category[category_code],
            'active': True,
            'model_id': model.id,
            'action_id': action.id,
            'pending_domain': pending_domain,
            'approved_domain': approved_domain,
            'rejected_domain': rejected_domain,
            'cancelled_domain': cancelled_domain,
            'extra_domain': '[]',
            'name_field_id': _field(env, model_name, name_field).id,
            'date_field_id': _field(env, model_name, date_field).id,
            'requester_field_id': _field(env, model_name, requester_field).id,
            'approver_field_id': _field(env, model_name, approver_field).id,
            'responsible_group_ids': [(6, 0, _groups(env, group_xmlids).ids)],
        }
        approval_type = type_model.search([('code', '=', code)], limit=1)
        if approval_type:
            approval_type.write(values)
        else:
            values['code'] = code
            type_model.create(values)


def post_init_hook(cr, registry):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        _seed_dashboard(env)
        env['dex_approval_dashboard.action'].seed_default_actions()
        env['dex_approval_dashboard.type'].action_sync_all()
