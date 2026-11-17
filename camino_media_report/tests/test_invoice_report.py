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

    def _invoice_with_line(
        self, move_type="out_invoice", invoice_date="2026-03-01", **line_values
    ):
        account = self.env["account.account"].search(
            [("account_type", "=", "income")], limit=1
        )
        return self._invoice(
            move_type=move_type,
            invoice_date=invoice_date,
            invoice_line_ids=[
                (
                    0,
                    0,
                    {
                        "name": "Management fee 2026",
                        "quantity": 1,
                        "price_unit": 2000.0,
                        "account_id": account.id,
                        **line_values,
                    },
                )
            ],
        )

    def test_line_spanish_description_is_stored_and_not_copied(self):
        invoice = self._invoice_with_line(camino_name_es="Gestión anual 2026")
        line = invoice.invoice_line_ids
        self.assertEqual(line.camino_name_es, "Gestión anual 2026")
        copy = invoice.copy()
        self.assertFalse(copy.invoice_line_ids.camino_name_es)

    def test_report_shows_spanish_line_description(self):
        html = self._html(self._invoice_with_line(camino_name_es="Gestión anual 2026"))
        self.assertIn("Gestión anual 2026", html)

    def test_report_omits_spanish_description_when_empty(self):
        html = self._html(self._invoice_with_line())
        self.assertIn("Management fee 2026", html)
        self.assertNotIn("Gestión anual", html)

    def test_report_keeps_only_description_and_amount_columns(self):
        html = self._html(self._invoice_with_line())
        for column in ("th_quantity", "th_priceunit", "th_discount", "th_taxes"):
            self.assertNotIn(f'name="{column}"', html)
        for cell in ("td_quantity", "td_price_unit", "td_discount", "td_taxes"):
            self.assertNotIn(f'name="{cell}"', html)
        self.assertIn('name="th_subtotal"', html)

    def test_line_form_view_shows_spanish_description(self):
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        self.assertIn('name="camino_name_es"', arch)

    def _archive_company_banks(self):
        # The demo company already has a bank account; it would compete with ours.
        self.env.company.partner_id.bank_ids.write({"active": False})

    def _company_bank(self, acc_number, currency, **values):
        return self.env["res.partner.bank"].create(
            {
                "acc_number": acc_number,
                "partner_id": self.env.company.partner_id.id,
                "acc_holder_name": "Camino Media, S.L.",
                "currency_id": currency.id,
                **values,
            }
        )

    def test_bank_account_stores_invoice_details(self):
        bank = self._company_bank(
            "ES7821002865591301038677",
            self.env.ref("base.EUR"),
            camino_intermediary_bic="CHASGB2L",
            camino_bank_address="Calle Mayor 16, 28013 Madrid",
            camino_invoice_warning="Payments must be ordered in euros (EUR).",
        )
        self.assertEqual(bank.camino_intermediary_bic, "CHASGB2L")
        self.assertIn("Calle Mayor", bank.camino_bank_address)
        self.assertIn("ordered in euros", bank.camino_invoice_warning)

    def test_invoice_picks_the_bank_account_of_its_currency(self):
        self._archive_company_banks()
        eur_bank = self._company_bank(
            "ES7821002865591301038677", self.env.ref("base.EUR")
        )
        usd_bank = self._company_bank(
            "ES6115830001129366855586", self.env.ref("base.USD")
        )
        usd_invoice = self._invoice(currency_id=self.env.ref("base.USD").id)
        eur_invoice = self._invoice(currency_id=self.env.ref("base.EUR").id)
        self.assertEqual(usd_invoice.partner_bank_id, usd_bank)
        self.assertEqual(eur_invoice.partner_bank_id, eur_bank)

    def test_report_shows_bank_details_and_warning(self):
        self._archive_company_banks()
        bank = self._company_bank(
            "ES6115830001129366855586",
            self.env.ref("base.USD"),
            camino_intermediary_bic="CHASGB2L",
            camino_bank_address="Calle Príncipe de Vergara 132",
            camino_invoice_warning="ACCOUNT IN US DOLLARS ONLY",
        )
        invoice = self._invoice(currency_id=self.env.ref("base.USD").id)
        html = self._html(invoice)
        self.assertEqual(invoice.partner_bank_id, bank)
        self.assertIn('name="camino_bank_block"', html)
        for text in (
            "ES6115830001129366855586",
            "CHASGB2L",
            "Calle Príncipe de Vergara 132",
            "ACCOUNT IN US DOLLARS ONLY",
            "Please cite invoice number for our reference.",
        ):
            self.assertIn(text, html)

    def test_report_hides_bank_block_without_account(self):
        self._archive_company_banks()
        html = self._html(self._invoice())
        self.assertNotIn('name="camino_bank_block"', html)

    def test_report_omits_optional_bank_lines_when_empty(self):
        self._archive_company_banks()
        self._company_bank("ES7821002865591301038677", self.env.ref("base.EUR"))
        html = self._html(self._invoice(currency_id=self.env.ref("base.EUR").id))
        self.assertIn('name="camino_bank_block"', html)
        self.assertNotIn("Intermediary BIC:", html)
        self.assertNotIn("Address / Dirección:", html)

    def test_invoice_gets_the_standard_invoice_sequence(self):
        invoice = self._invoice_with_line(invoice_date="2040-03-01")
        invoice.action_post()
        self.assertEqual(invoice.name, "INV/2040/00001")

    def test_credit_note_gets_its_own_sequence(self):
        refund = self._invoice_with_line(
            move_type="out_refund", invoice_date="2040-03-01"
        )
        refund.action_post()
        self.assertEqual(refund.name, "CREDITNOTE/2040/00001")

    def test_credit_notes_are_numbered_consecutively(self):
        first = self._invoice_with_line(
            move_type="out_refund", invoice_date="2040-03-01"
        )
        first.action_post()
        second = self._invoice_with_line(
            move_type="out_refund", invoice_date="2040-03-01"
        )
        second.action_post()
        self.assertEqual(second.name, "CREDITNOTE/2040/00002")

    def test_invoices_and_credit_notes_keep_separate_sequences(self):
        invoice = self._invoice_with_line(invoice_date="2040-03-01")
        invoice.action_post()
        refund = self._invoice_with_line(
            move_type="out_refund", invoice_date="2040-03-01"
        )
        refund.action_post()
        self.assertEqual(invoice.name, "INV/2040/00001")
        self.assertEqual(refund.name, "CREDITNOTE/2040/00001")

    def test_pound_sterling_is_available(self):
        self.assertTrue(self.env.ref("base.GBP").active)

    def test_invoice_can_be_issued_in_pounds(self):
        invoice = self._invoice_with_line(invoice_date="2040-03-01")
        pound = self.env.ref("base.GBP")
        invoice.write({"currency_id": pound.id})
        invoice.action_post()
        self.assertEqual(invoice.currency_id, pound)
        self.assertEqual(invoice.name, "INV/2040/00001")
