from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCaminoInvoiceReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente Camino"})

    def _invoice(self, **values):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                # the standard information block only renders with a date or reference
                "invoice_date": "2026-03-01",
                **values,
            }
        )

    def _html(self, invoice):
        html, _fmt = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices", invoice.ids
        )
        return html.decode()

    def test_fields_are_stored_and_not_copied(self):
        invoice = self._invoice(
            camino_location="Madrid",
            camino_shoot_dates="1-3 marzo",
            camino_contact="Ana",
        )
        self.assertEqual(invoice.camino_location, "Madrid")
        copy = invoice.copy()
        self.assertFalse(copy.camino_location)
        self.assertFalse(copy.camino_shoot_dates)
        self.assertFalse(copy.camino_contact)

    def test_report_shows_the_three_values(self):
        html = self._html(
            self._invoice(
                camino_location="Sevilla",
                camino_shoot_dates="10-12 abril",
                camino_contact="Luis",
            )
        )
        for text in ("Sevilla", "10-12 abril", "Luis"):
            self.assertIn(text, html)

    def test_report_omits_empty_values(self):
        html = self._html(self._invoice(camino_location="Sevilla"))
        self.assertIn("Sevilla", html)
        self.assertNotIn('name="camino_shoot_dates"', html)
        self.assertNotIn('name="camino_contact"', html)

    def test_form_view_shows_the_fields_for_customer_invoices(self):
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        for name in ("camino_location", "camino_shoot_dates", "camino_contact"):
            self.assertIn(f'name="{name}"', arch)
