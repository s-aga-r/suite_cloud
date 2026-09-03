# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address
from passlib.hash import sha512_crypt

# Stalwart's docs generate secrets with `openssl passwd -6`, which is SHA-512 crypt at 5000
# rounds; matching it keeps the stored hashes byte-for-byte in a format Stalwart accepts.
SECRET_HASH_ROUNDS = 5000
MIN_PASSWORD_LENGTH = 8


class MailDirectoryAccount(Document):
    def autoname(self) -> None:
        self.email = self.email.strip().lower()
        self.name = self.email

    def validate(self) -> None:
        self.validate_email()
        self.validate_type()
        self.set_secret()
        self.validate_addresses()
        self.validate_groups()

    def validate_email(self) -> None:
        self.email = self.email.strip().lower()
        validate_email_address(self.email, throw=True)

    def validate_type(self) -> None:
        """Groups never log in, and an account others are members of must stay a group."""

        if self.type == "group":
            self.password = None
            self.secret = None
            return

        if self.is_new():
            return

        if member := frappe.db.get_value("Mail Directory Group Member", {"member_of": self.name}, "parent"):
            frappe.throw(
                _("{0} is a member of this group. Remove its members before changing the type.").format(
                    frappe.bold(member)
                )
            )

    def set_secret(self) -> None:
        """Hashes a newly entered password into the secret column Stalwart reads.

        The plain text is dropped before save, so Frappe stores neither the value nor an
        encrypted copy in __Auth.
        """

        if not self.password:
            return

        if len(self.password) < MIN_PASSWORD_LENGTH:
            frappe.throw(_("Password must be at least {0} characters long.").format(MIN_PASSWORD_LENGTH))

        self.secret = hash_secret(self.password)
        self.password = None

    def validate_addresses(self) -> None:
        self.set_primary_address()

        seen = set()
        for row in self.emails:
            row.address = row.address.strip().lower()
            validate_address(row.address)

            if row.address in seen:
                frappe.throw(_("Address {0} is listed twice.").format(frappe.bold(row.address)))
            seen.add(row.address)

            self.validate_address_is_unused(row.address)

    def set_primary_address(self) -> None:
        """Keeps exactly one primary row, matching the account email, at the top of the table."""

        aliases = [
            row for row in self.emails if row.type != "primary" and row.address.strip().lower() != self.email
        ]

        self.set("emails", [])
        self.append("emails", {"address": self.email, "type": "primary"})
        for row in aliases:
            self.append("emails", row)

    def validate_address_is_unused(self, address: str) -> None:
        owner = frappe.db.get_value(
            "Mail Directory Email", {"address": address, "parent": ["!=", self.name]}, "parent"
        )
        if owner:
            frappe.throw(
                _("Address {0} already belongs to {1}.").format(frappe.bold(address), frappe.bold(owner))
            )

    def validate_groups(self) -> None:
        seen = set()
        for row in self.member_of:
            if row.member_of == self.name:
                frappe.throw(_("An account cannot be a member of itself."))

            if row.member_of in seen:
                frappe.throw(_("Group {0} is listed twice.").format(frappe.bold(row.member_of)))
            seen.add(row.member_of)

            if frappe.db.get_value("Mail Directory Account", row.member_of, "type") != "group":
                frappe.throw(_("{0} is not a group.").format(frappe.bold(row.member_of)))


def validate_address(address: str) -> None:
    """Accepts a full address or a `@domain` catch-all."""

    if address.startswith("@"):
        validate_email_address(f"catch-all{address}", throw=True)
    else:
        validate_email_address(address, throw=True)


def hash_secret(password: str) -> str:
    return sha512_crypt.using(rounds=SECRET_HASH_ROUNDS).hash(password)
