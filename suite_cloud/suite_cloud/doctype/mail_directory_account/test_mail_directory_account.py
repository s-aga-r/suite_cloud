# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.model.document import Document
from frappe.tests import IntegrationTestCase
from passlib.hash import sha512_crypt

# Reserved TLD, so the test accounts never collide with a site's real ones.
DOMAIN = "suite-cloud-test.invalid"


class TestMailDirectoryAccount(IntegrationTestCase):
    def setUp(self) -> None:
        self.delete_test_accounts()

    def tearDown(self) -> None:
        self.delete_test_accounts()

    def delete_test_accounts(self) -> None:
        # Members link to groups, so delete them first.
        for account_type in ("individual", "group"):
            for name in frappe.get_all(
                "Mail Directory Account",
                {"email": ["like", f"%@{DOMAIN}"], "type": account_type},
                pluck="name",
            ):
                frappe.delete_doc("Mail Directory Account", name, force=True)

    def create_account(self, local_part: str, **values) -> Document:
        doc = frappe.new_doc("Mail Directory Account")
        doc.email = f"{local_part}@{DOMAIN}"
        doc.update(values)
        return doc.insert()

    def test_password_is_hashed_and_dropped(self) -> None:
        account = self.create_account("john", description="John Doe", password="correct horse")

        self.assertFalse(account.password)
        self.assertTrue(account.secret.startswith("$6$"))
        self.assertTrue(sha512_crypt.verify("correct horse", account.secret))
        self.assertIsNone(frappe.db.get_value("Mail Directory Account", account.name, "password"))

    def test_secret_survives_saves_without_password(self) -> None:
        account = self.create_account("john", password="correct horse")
        secret = account.secret

        account.description = "John Doe"
        account.save()

        self.assertEqual(account.secret, secret)

    def test_short_password_is_refused(self) -> None:
        self.assertRaisesRegex(
            frappe.ValidationError, "at least", self.create_account, "john", password="short"
        )

    def test_email_is_lowercased_and_becomes_name(self) -> None:
        account = self.create_account("John.Doe")

        self.assertEqual(account.name, f"john.doe@{DOMAIN}")
        self.assertEqual(account.email, account.name)

    def test_primary_address_row_is_maintained(self) -> None:
        account = self.create_account("john", emails=[{"address": f"JD@{DOMAIN}", "type": "alias"}])

        self.assertEqual(
            [(row.address, row.type) for row in account.emails],
            [(f"john@{DOMAIN}", "primary"), (f"jd@{DOMAIN}", "alias")],
        )

    def test_catch_all_alias_is_accepted(self) -> None:
        account = self.create_account("postmaster", emails=[{"address": f"@{DOMAIN}", "type": "alias"}])

        self.assertEqual(account.emails[1].address, f"@{DOMAIN}")

    def test_address_cannot_belong_to_two_accounts(self) -> None:
        self.create_account("john", emails=[{"address": f"jd@{DOMAIN}", "type": "alias"}])

        self.assertRaisesRegex(
            frappe.ValidationError,
            "already belongs",
            self.create_account,
            "jane",
            emails=[{"address": f"jd@{DOMAIN}", "type": "alias"}],
        )

    def test_group_has_no_secret(self) -> None:
        group = self.create_account("team", type="group", password="correct horse")

        self.assertIsNone(group.secret)

    def test_membership_requires_a_group(self) -> None:
        self.create_account("jane")

        self.assertRaisesRegex(
            frappe.ValidationError,
            "not a group",
            self.create_account,
            "john",
            member_of=[{"member_of": f"jane@{DOMAIN}"}],
        )

    def test_group_with_members_cannot_change_type(self) -> None:
        group = self.create_account("team", type="group")
        self.create_account("john", member_of=[{"member_of": group.name}])

        group.type = "individual"

        self.assertRaisesRegex(frappe.ValidationError, "member of this group", group.save)
