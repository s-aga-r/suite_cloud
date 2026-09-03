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
});
