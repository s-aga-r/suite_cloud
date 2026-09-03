// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Directory Account", {
	setup(frm) {
		frm.set_query("member_of", "member_of", () => ({
			filters: {
				type: "group",
				name: ["!=", frm.doc.name],
			},
		}));
	},

	refresh(frm) {
		frm.trigger("add_actions");
	},

	add_actions(frm) {
		if (frm.doc.__islocal || frm.doc.type !== "group") return;

		// Membership lives in the members' child tables, so the list is filtered on that table.
		frm.add_custom_button(__("Members"), () => {
			frappe.set_route("List", "Mail Directory Account", {
				"Mail Directory Group Member.member_of": frm.doc.name,
			});
		});
	},
});
