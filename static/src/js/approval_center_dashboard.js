odoo.define('dex_approval_dashboard.ApprovalCenterDashboard', function (require) {
    'use strict';

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var fieldUtils = require('web.field_utils');

    var QWeb = core.qweb;
    var _t = core._t;

    var ApprovalCenterDashboard = AbstractAction.extend({
        template: 'DexApprovalCenterDashboard',
        events: {
            'click .o_dex_process': '_onProcess',
            'click .o_dex_tabs button': '_onTab',
            'click .o_dex_quick_filters button': '_onQuick',
            'input .o_dex_search': '_onSearch',
            'change .o_dex_status_filter': '_onStatus',
            'change .o_dex_type_filter': '_onType',
            'click .o_dex_toggle_filters': '_onToggleFilters',
            'click .o_dex_apply_filters': '_onApplyFilters',
            'click .o_dex_clear_filters': '_onClearFilters',
            'click .o_dex_filter_chip': '_onRemoveFilter',
            'click .o_dex_sort': '_onSort',
            'click .o_dex_prev': '_onPrevious',
            'click .o_dex_next': '_onNext',
            'change .o_dex_select_row': '_onSelectRow',
            'change .o_dex_select_page': '_onSelectPage',
            'click .o_dex_clear_selection': '_clearSelection',
            'click .o_dex_multi_action': '_onMultiAction',
            'click .o_dex_execute_action': '_onExecuteAction',
            'click .o_dex_comment': '_onComment',
            'click .o_dex_open_drawer': '_onOpenDrawer',
            'click .o_dex_close_drawer': '_onCloseDrawer',
            'click .o_dex_open_request': '_onOpenRequest',
            'click .o_dex_refresh': '_onRefresh',
            'click .o_dex_refresh_analytics': '_loadAnalytics',
            'click .o_dex_open_configuration': '_onOpenConfiguration',
        },

        init: function () {
            this._super.apply(this, arguments);
            this.state = {
                category_id: false, approval_type_id: false, query: '', status: 'pending',
                assigned_only: true, quick: 'my', department: '', requester: '', approver: '',
                stage: '', customer: '', project: '', site: '', priority: '', date_from: '',
                date_to: '', page: 1, page_size: 25, sort_field: 'request_date',
                sort_direction: 'desc', tab: 'approvals', filters_open: false,
            };
            this.data = {categories: [], approval_types: [], filter_options: {}, rows: []};
            this.selected = {};
            this.selectedRows = {};
            this.drawerItemId = false;
            this._debouncedSearch = _.debounce(this._loadAndRender.bind(this), 300);
        },

        willStart: function () {
            return Promise.all([this._super.apply(this, arguments), this._loadData()]);
        },

        start: function () {
            var result = this._super.apply(this, arguments);
            this._render();
            return result;
        },

        _rpcModel: function (method, args) {
            return this._rpc({model: 'dex_approval_dashboard.item', method: method, args: args || []});
        },

        _loadData: function () {
            var self = this;
            return this._rpcModel('dashboard_get_data', [this.state]).then(function (data) {
                self.data = data;
                self.state.page = data.page;
                _.each(data.rows, function (row) {
                    if (self.selected[row.id]) { self.selectedRows[row.id] = row; }
                });
            });
        },

        _loadAndRender: function () {
            var self = this;
            this.$el.addClass('o_dex_loading');
            return this._loadData().then(function () {
                self._render();
                if (self.drawerItemId) { return self._loadDrawer(self.drawerItemId); }
            }).guardedCatch(function () { self.$el.removeClass('o_dex_loading'); });
        },

        _formatDate: function (value) {
            if (!value) { return '—'; }
            try { return fieldUtils.format.datetime(moment.utc(value).local(), {}, {timezone: false}); }
            catch (error) { return value; }
        },

        _formatAge: function (value) {
            return value === false || value === null || value === undefined ? '—' : value + (value === 1 ? ' day' : ' days');
        },

        _formatTitle: function (value) {
            return (value || '').replace(/_/g, ' ').replace(/\b\w/g, function (letter) { return letter.toUpperCase(); });
        },

        _qwebHelpers: function () {
            return {
                formatDate: this._formatDate.bind(this), formatAge: this._formatAge.bind(this),
                title: this._formatTitle.bind(this), Math: Math,
            };
        },

        _render: function () {
            var helpers = this._qwebHelpers();
            this.$('.o_dex_process_container').html(QWeb.render('DexApprovalCenterProcesses', _.extend({
                data: this.data, selected_category_id: this.state.category_id,
            }, helpers)));
            this.$('.o_dex_advanced_filters').html(QWeb.render('DexApprovalCenterAdvancedFilters', {
                open: this.state.filters_open, options: this.data.filter_options || {},
            }));
            this._restoreAdvancedFilterValues();
            this.$('.o_dex_filter_chips').html(QWeb.render('DexApprovalCenterChips', {
                state: this.state, title: helpers.title, advanced: this._activeAdvancedFilters(),
            }));
            this.$('.o_dex_selection_bar').html(QWeb.render('DexApprovalCenterSelectionBar', this._selectionContext()));
            this.$('.o_dex_table_container').html(QWeb.render('DexApprovalCenterTable', _.extend({
                data: this.data, selected: this.selected,
                page_selected: this.data.rows.length && _.every(this.data.rows, function (row) { return !!this.selected[row.id]; }, this),
            }, helpers)));
            this.$('.o_dex_search').val(this.state.query);
            this.$('.o_dex_status_filter').val(this.state.status || '');
            this._renderTypeOptions();
            this._renderQuickState();
            this.$('.o_dex_config_tab').toggleClass('d-none', !this.data.is_manager);
            this.$el.removeClass('o_dex_loading');
        },

        _renderTypeOptions: function () {
            var self = this;
            var $select = this.$('.o_dex_type_filter');
            $select.find('option:not(:first)').remove();
            _.each(this.data.approval_types || [], function (type) {
                if (!self.state.category_id || type.category_id === self.state.category_id) {
                    $('<option/>', {value: type.id, text: type.name}).appendTo($select);
                }
            });
            $select.val(this.state.approval_type_id || '');
        },

        _restoreAdvancedFilterValues: function () {
            var self = this;
            this.$('.o_dex_advanced_filter').each(function () {
                var key = $(this).data('filter');
                $(this).val(self.state[key] || '');
            });
        },

        _activeAdvancedFilters: function () {
            var self = this;
            var labels = {department: 'Department', requester: 'Requester', approver: 'Approver', stage: 'Stage', customer: 'Customer', project: 'Project', site: 'Site', priority: 'Priority', date_from: 'From', date_to: 'To'};
            return _.chain(labels).map(function (label, key) {
                return self.state[key] ? {key: key, label: label, value: self._formatTitle(self.state[key])} : false;
            }).compact().value();
        },

        _renderQuickState: function () {
            this.$('.o_dex_quick_filters button').removeClass('active');
            this.$('.o_dex_quick_filters button[data-quick="' + (this.state.quick || '') + '"]').addClass('active');
        },

        _selectionContext: function () {
            var rows = _.values(this.selectedRows);
            var context = {count: rows.length, approve: false, reject: false, message: ''};
            if (!rows.length) { return context; }
            var typeId = rows[0].approval_type_id;
            var sameType = _.every(rows, function (row) { return row.approval_type_id === typeId && row.status === 'pending'; });
            var common = function (intent) {
                var first = _.findWhere(rows[0].actions, {intent: intent});
                if (!first) { return false; }
                return _.every(rows, function (row) { return !!_.findWhere(row.actions, {id: first.id}); }) ? first : false;
            };
            if (sameType) { context.approve = common('approve'); context.reject = common('reject'); }
            if (!context.approve && !context.reject) { context.message = _t('Selected requests must use the same approval function and action.'); }
            return context;
        },

        _resetAndLoad: function () { this.state.page = 1; return this._loadAndRender(); },
        _onProcess: function (event) { this.state.category_id = parseInt($(event.currentTarget).data('category-id'), 10) || false; this.state.approval_type_id = false; return this._resetAndLoad(); },
        _onSearch: function (event) { this.state.query = $(event.currentTarget).val(); this.state.page = 1; this._debouncedSearch(); },
        _onStatus: function (event) { this.state.status = $(event.currentTarget).val() || false; this.state.quick = false; return this._resetAndLoad(); },
        _onType: function (event) { this.state.approval_type_id = parseInt($(event.currentTarget).val(), 10) || false; return this._resetAndLoad(); },
        _onToggleFilters: function () { this.state.filters_open = !this.state.filters_open; this._render(); },
        _onApplyFilters: function () { var self = this; this.$('.o_dex_advanced_filter').each(function () { self.state[$(this).data('filter')] = $(this).val() || ''; }); return this._resetAndLoad(); },
        _onClearFilters: function () { var self = this; _.each(['department','requester','approver','stage','customer','project','site','priority','date_from','date_to'], function (key) { self.state[key] = ''; }); return this._resetAndLoad(); },
        _onRemoveFilter: function (event) { var key = $(event.currentTarget).data('remove-filter'); if (key === 'assigned_only') { this.state.assigned_only = false; this.state.quick = false; } else { this.state[key] = false; } return this._resetAndLoad(); },
        _onQuick: function (event) {
            var quick = $(event.currentTarget).data('quick');
            this.state.quick = this.state.quick === quick ? false : quick;
            if (this.state.quick === 'my') { this.state.assigned_only = true; this.state.status = 'pending'; }
            else if (this.state.quick === 'overdue' || this.state.quick === 'priority') { this.state.status = 'pending'; }
            else if (this.state.quick === 'today') { this.state.status = 'approved'; }
            else if (this.state.quick === 'rejected') { this.state.status = 'rejected'; }
            return this._resetAndLoad();
        },
        _onSort: function (event) { var field = $(event.currentTarget).data('sort'); if (this.state.sort_field === field) { this.state.sort_direction = this.state.sort_direction === 'asc' ? 'desc' : 'asc'; } else { this.state.sort_field = field; this.state.sort_direction = 'asc'; } return this._resetAndLoad(); },
        _onPrevious: function () { if (this.state.page > 1) { this.state.page -= 1; return this._loadAndRender(); } },
        _onNext: function () { if (this.state.page < this.data.page_count) { this.state.page += 1; return this._loadAndRender(); } },

        _onSelectRow: function (event) {
            var id = parseInt($(event.currentTarget).data('item-id'), 10);
            if ($(event.currentTarget).is(':checked')) { this.selected[id] = true; this.selectedRows[id] = _.findWhere(this.data.rows, {id: id}); }
            else { delete this.selected[id]; delete this.selectedRows[id]; }
            this._render();
        },
        _onSelectPage: function (event) { var checked = $(event.currentTarget).is(':checked'); var self = this; _.each(this.data.rows, function (row) { if (checked) { self.selected[row.id] = true; self.selectedRows[row.id] = row; } else { delete self.selected[row.id]; delete self.selectedRows[row.id]; } }); this._render(); },
        _clearSelection: function () { this.selected = {}; this.selectedRows = {}; this._render(); },

        _findAction: function (itemId, actionId) { var row = this.selectedRows[itemId] || _.findWhere(this.data.rows, {id: itemId}); return row && _.findWhere(row.actions, {id: actionId}); },
        _onExecuteAction: function (event) { var itemId = parseInt($(event.currentTarget).data('item-id'), 10); var actionId = parseInt($(event.currentTarget).data('action-id'), 10); return this._reviewAction(itemId, actionId); },
        _reviewAction: function (itemId, actionId) {
            var action = this._findAction(itemId, actionId);
            if (!action) { return Promise.resolve({status: 'failed'}); }
            var self = this;
            return new Promise(function (resolve) {
                if (action.requires_reason) {
                    self._reasonDialog(action, function (reason) { self._execute(itemId, actionId, reason).then(resolve); }, function () { resolve({status: 'skipped'}); });
                } else if (action.confirm_message) {
                    Dialog.confirm(self, action.confirm_message, {title: action.name, confirm_callback: function () { self._execute(itemId, actionId, false).then(resolve); }, cancel_callback: function () { resolve({status: 'skipped'}); }});
                } else { self._execute(itemId, actionId, false).then(resolve); }
            });
        },
        _reasonDialog: function (action, confirm, cancel) {
            var $reason = $('<textarea/>', {class: 'form-control', rows: 4, placeholder: _t('Enter the required reason...')});
            var dialog = new Dialog(this, {title: action.name, $content: $('<div/>').append($('<label/>', {text: _t('Reason')}), $reason), buttons: [{text: _t('Continue'), classes: 'btn-primary', close: false, click: function () { var reason = ($reason.val() || '').trim(); if (!reason) { $reason.addClass('is-invalid').focus(); return; } dialog.close(); confirm(reason); }}, {text: _t('Skip'), close: true, click: cancel}]}); dialog.open();
        },
        _execute: function (itemId, actionId, reason) {
            var self = this;
            return this._rpcModel('dashboard_execute_action', [itemId, actionId, reason || false]).then(function (result) {
                var finish = function () { delete self.selected[itemId]; delete self.selectedRows[itemId]; return self._refreshApprovalType(result.approval_type_id).then(function () { return {status: 'completed'}; }); };
                if (result.action) { return self.do_action(result.action, {on_close: finish}).then(function () { return result.opens_dialog ? {status: 'completed'} : finish(); }); }
                return finish();
            }).guardedCatch(function () { return {status: 'failed'}; });
        },
        _refreshApprovalType: function (typeId) { var self = this; return this._rpcModel('dashboard_refresh_type', [typeId]).then(function () { return self._loadData(); }).then(function () { self._render(); }); },

        _onMultiAction: function (event) {
            var self = this; var actionId = parseInt($(event.currentTarget).data('action-id'), 10); var ids = _.map(_.keys(this.selected), Number);
            return this._rpcModel('dashboard_prepare_multi_action', [ids, actionId]).then(function (result) {
                var summary = {completed: 0, skipped: 0, failed: 0};
                var index = 0;
                var next = function () {
                    if (index >= result.steps.length) { Dialog.alert(self, _.str.sprintf(_t('Completed: %s\nSkipped: %s\nFailed: %s'), summary.completed, summary.skipped, summary.failed), {title: _t('Multi-action summary')}); return self._loadAndRender(); }
                    var step = result.steps[index++];
                    return self._showSequenceReview(step, index, result.steps.length).then(function (choice) {
                        if (choice === 'stop') { return self._loadAndRender(); }
                        if (choice === 'skip') { summary.skipped += 1; return next(); }
                        return self._reviewAction(step.item_id, actionId).then(function (outcome) { summary[outcome.status] = (summary[outcome.status] || 0) + 1; return next(); });
                    });
                };
                return next();
            });
        },
        _showSequenceReview: function (step, index, total) {
            var self = this;
            return new Promise(function (resolve) { var dialog = new Dialog(self, {title: _.str.sprintf(_t('%s of %s — %s'), index, total, step.name), $content: $('<p/>', {text: _.str.sprintf(_t('Review %s before running %s.'), step.item_name, step.name)}), buttons: [{text: _t('Continue'), classes: 'btn-primary', close: true, click: function () { resolve('continue'); }}, {text: _t('Skip'), close: true, click: function () { resolve('skip'); }}, {text: _t('Stop'), close: true, click: function () { resolve('stop'); }}]}); dialog.open(); });
        },

        _onComment: function (event) { return this._openCommentDialog(parseInt($(event.currentTarget).data('item-id'), 10)); },
        _openCommentDialog: function (itemId) {
            var self = this; var row = this.selectedRows[itemId] || _.findWhere(this.data.rows, {id: itemId}) || {};
            var $comment = $('<textarea/>', {class: 'form-control', rows: 6, placeholder: _t('Write a comment for the original request...')});
            var $emailRequester = $('<label/>', {class: 'o_dex_email_requester'}).append(
                $('<input/>', {type: 'checkbox', checked: true}),
                document.createTextNode(' ' + _t('Email the requester about this comment (when an email address is available)')));
            var dialog = new Dialog(this, {title: _t('Comment on ') + (row.name || _t('request')), $content: $('<div/>').append($('<p/>', {class: 'text-muted', text: row.approval_type || ''}), $comment, $emailRequester), buttons: [{text: _t('Post Comment'), classes: 'btn-primary', close: false, click: function () { var body = ($comment.val() || '').trim(); if (!body) { $comment.addClass('is-invalid').focus(); return; } self._rpcModel('dashboard_post_comment', [itemId, body, $emailRequester.find('input').is(':checked')]).then(function (details) { dialog.close(); self._renderDrawer(details); self._loadAndRender(); }); }}, {text: _t('Cancel'), close: true}]}); dialog.open();
        },

        _onOpenDrawer: function (event) { this.drawerItemId = parseInt($(event.currentTarget).data('item-id'), 10); return this._loadDrawer(this.drawerItemId); },
        _loadDrawer: function (itemId) { var self = this; return this._rpcModel('dashboard_get_details', [itemId]).then(function (details) { self._renderDrawer(details); }); },
        _renderDrawer: function (details) { this.drawerItemId = details.id; this.$('.o_dex_drawer_host').html(QWeb.render('DexApprovalCenterDrawer', _.extend({row: details}, this._qwebHelpers()))); },
        _onCloseDrawer: function () { this.drawerItemId = false; this.$('.o_dex_drawer_host').empty(); },
        _onOpenRequest: function (event) { var self = this; var id = parseInt($(event.currentTarget).data('item-id'), 10); return this._rpcModel('action_open_source', [[id]]).then(function (action) { return self.do_action(action); }); },

        _onTab: function (event) {
            var tab = $(event.currentTarget).data('tab'); if (tab === 'configuration' && !this.data.is_manager) { return; }
            this.state.tab = tab; this.$('.o_dex_tabs button').removeClass('active'); $(event.currentTarget).addClass('active');
            this.$('.o_dex_approvals_tab,.o_dex_analytics_tab,.o_dex_configuration_tab').addClass('d-none'); this.$('.o_dex_' + tab + '_tab').removeClass('d-none');
            if (tab === 'analytics') { return this._loadAnalytics(); } if (tab === 'configuration') { return this._loadConfiguration(); }
        },
        _loadAnalytics: function () { var self = this; return this._rpcModel('dashboard_get_analytics', [this.state]).then(function (data) { var pending = _.reduce(_.values(data.aging), function (sum, value) { return sum + value; }, 0); self.$('.o_dex_analytics_tab').html(QWeb.render('DexApprovalCenterAnalytics', {data: data, pending: pending, barWidth: function (value, rows) { var max = _.max(_.pluck(rows, '1')) || 1; return Math.max((value / max) * 100, 3); }})); }); },
        _loadConfiguration: function () { var self = this; return this._rpcModel('dashboard_get_configuration_summary').then(function (data) { self.$('.o_dex_configuration_tab').html(QWeb.render('DexApprovalCenterConfiguration', {data: data})); }); },
        _onOpenConfiguration: function () { return this.do_action('dex_approval_dashboard.action_approval_dashboard_types'); },
        _onRefresh: function () { return this._loadAndRender(); },
    });

    core.action_registry.add('dex_approval_dashboard.dashboard', ApprovalCenterDashboard);
    return ApprovalCenterDashboard;
});
