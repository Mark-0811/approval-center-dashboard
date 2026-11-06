/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ApprovalCenterDashboard extends Component {
    static template = "approval_center_dashboard.Main";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            categories: [], rows: [], selectedCategory: false, query: "",
            status: "pending", mine: true, page: 1, pages: 1, total: 0,
            loading: true, commentRequest: false, comment: "", emailRequester: true,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            const result = await this.orm.call("approval.center.request", "dashboard_get_data", [{
                category_id: this.state.selectedCategory, status: this.state.status,
                mine: this.state.mine, query: this.state.query, page: this.state.page,
            }]);
            Object.assign(this.state, result, {loading: false});
        } catch (error) {
            this.state.loading = false;
            this.notification.add(error.message || "Could not load approval requests.", {type: "danger"});
        }
    }

    async chooseCategory(id) {
        this.state.selectedCategory = id || false;
        this.state.page = 1;
        await this.load();
    }

    async onSearch(ev) { this.state.query = ev.target.value; this.state.page = 1; await this.load(); }
    async onStatus(ev) { this.state.status = ev.target.value; this.state.page = 1; await this.load(); }
    async toggleMine(ev) { this.state.mine = ev.target.checked; this.state.page = 1; await this.load(); }
    async pageBy(delta) { this.state.page = Math.max(1, Math.min(this.state.pages, this.state.page + delta)); await this.load(); }

    async openSource(row) {
        const result = await this.orm.call("approval.center.request", "dashboard_open_source", [row.id]);
        await this.action.doAction(result);
    }

    async decide(row, decision) {
        const label = decision === "approved" ? "Approve" : "Reject";
        if (!window.confirm(`${label} ${row.name}?`)) return;
        try {
            const result = await this.orm.call("approval.center.request", "dashboard_decide", [row.id, decision]);
            if (result && result.type) await this.action.doAction(result);
            this.notification.add(`${row.name} ${decision}.`, {type: "success"});
            await this.load();
        } catch (error) { this.notification.add(error.message || "The decision could not be completed.", {type: "danger"}); }
    }

    startComment(row) { this.state.commentRequest = row; this.state.comment = ""; this.state.emailRequester = true; }
    async postComment() {
        try {
            await this.orm.call("approval.center.request", "dashboard_comment", [
                this.state.commentRequest.id, this.state.comment, this.state.emailRequester,
            ]);
            this.notification.add("Comment posted.", {type: "success"});
            this.state.commentRequest = false;
            await this.load();
        } catch (error) { this.notification.add(error.message || "The comment could not be posted.", {type: "danger"}); }
    }
}

registry.category("actions").add("approval_center_dashboard.main", ApprovalCenterDashboard);
