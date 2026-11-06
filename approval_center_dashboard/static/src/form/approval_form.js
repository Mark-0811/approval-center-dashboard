/** @odoo-module **/

import { onPatched, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.approvalOrm = useService("orm");
        this.approvalAction = useService("action");
        this.approvalNotification = useService("notification");
        this.approvalPanel = useState({context: false, key: false, loading: false, comment: ""});
        onPatched(() => this.refreshApprovalPanel());
    },

    async refreshApprovalPanel() {
        const root = this.model.root;
        const key = root && root.resId ? `${root.resModel}:${root.resId}` : false;
        if (key === this.approvalPanel.key || this.approvalPanel.loading) return;
        this.approvalPanel.key = key;
        this.approvalPanel.context = false;
        if (!key) return;
        this.approvalPanel.loading = true;
        try {
            this.approvalPanel.context = await this.approvalOrm.call(
                "approval.center.request", "form_get_approval_context", [root.resModel, root.resId]
            );
        } catch (error) {
            this.approvalNotification.add(error.message || "Could not load approval controls.", {type: "warning"});
        } finally {
            this.approvalPanel.loading = false;
        }
    },

    async runApprovalDecision(context, decision) {
        if (!context || !context.can_decide) return;
        const label = decision === "approved" ? "Approve" : "Reject";
        if (!window.confirm(`${label} ${context.reference}?`)) return;
        try {
            const result = await this.approvalOrm.call(
                "approval.center.request", "dashboard_decide", [context.request_id, decision]
            );
            if (result && result.type) await this.approvalAction.doAction(result);
            this.approvalNotification.add(`${context.reference} ${decision}.`, {type: "success"});
            this.approvalPanel.key = false;
            await this.refreshApprovalPanel();
        } catch (error) {
            this.approvalNotification.add(error.message || "The decision could not be completed.", {type: "danger"});
        }
    },

    async postFormApprovalComment(context) {
        try {
            await this.approvalOrm.call("approval.center.request", "dashboard_comment", [
                context.request_id, this.approvalPanel.comment, true,
            ]);
            this.approvalPanel.comment = "";
            this.approvalNotification.add("Comment posted and requester notified.", {type: "success"});
        } catch (error) {
            this.approvalNotification.add(error.message || "The comment could not be posted.", {type: "danger"});
        }
    },
});
