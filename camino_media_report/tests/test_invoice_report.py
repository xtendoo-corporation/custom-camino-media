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
        self.assertNotIn("BIC intermediario", html)
        self.assertNotIn("Dirección", html)

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


@tagged("post_install", "-at_install")
class TestCaminoInvoiceCustomisation(TransactionCase):
    """Brand header, bilingual labels, internal fields, dynamic bank and followers."""

    LOGO = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/"
        "q842iQAAAABJRU5ErkJggg=="
    )

    # Reuse the helpers of the report tests without re-running their tests.
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente Camino"})

    _invoice = TestCaminoInvoiceReport._invoice
    _html = TestCaminoInvoiceReport._html
    _invoice_with_line = TestCaminoInvoiceReport._invoice_with_line
    _archive_company_banks = TestCaminoInvoiceReport._archive_company_banks
    _company_bank = TestCaminoInvoiceReport._company_bank

    # --- bilingual labels -------------------------------------------------
    def test_labels_are_always_bilingual(self):
        # The customer speaks English: Spanish must still be printed.
        self.partner.lang = "en_US"
        html = self._html(self._invoice_with_line())
        for text in ("Invoice Date", "Fecha de factura", "Description", "Descripción",
                     "Amount", "Importe"):
            self.assertIn(text, html)

    def test_spanish_labels_are_italic_grey_and_small(self):
        html = self._html(self._invoice_with_line())
        self.assertIn('class="camino-es"', html)
        self.assertIn("font-style: italic", html)
        self.assertIn("color: #6c757d", html)
        self.assertIn("font-size: 85%", html)

    def test_credit_note_title_is_bilingual(self):
        refund = self._invoice_with_line(move_type="out_refund", invoice_date="2040-03-01")
        refund.action_post()
        html = self._html(refund)
        self.assertIn("Credit Note", html)
        self.assertIn("Nota de crédito", html)

    # --- line format ------------------------------------------------------
    def test_line_has_bold_concept_brackets_and_grey_translation(self):
        invoice = self._invoice_with_line(
            camino_description="Two shooting days in Madrid",
            camino_name_es="Gestión anual 2026",
        )
        html = self._html(invoice)
        self.assertRegex(html, r"<strong[^>]*>\s*Management fee 2026\s*</strong>")
        self.assertIn("(<span", html)
        self.assertIn("Two shooting days in Madrid", html)
        self.assertRegex(
            html, r'class="camino-es"[^>]*font-style: italic[^>]*>\s*Gestión anual 2026'
        )

    def test_line_without_description_has_no_brackets(self):
        html = self._html(self._invoice_with_line())
        self.assertNotIn("(<span", html)

    # --- brand ------------------------------------------------------------
    def test_brand_defaults_to_psn_and_shows_its_logo(self):
        self.env.company.camino_psn_logo = self.LOGO
        invoice = self._invoice_with_line()
        self.assertEqual(invoice.camino_brand, "psn")
        html = self._html(invoice)
        self.assertIn('name="camino_brand_header"', html)
        self.assertIn('alt="Production Service Network"', html)
        self.assertNotIn('alt="Camino Media"', html)

    def test_camino_brand_shows_the_camino_header(self):
        self.env.company.camino_media_logo = self.LOGO
        invoice = self._invoice_with_line()
        invoice.camino_brand = "camino"
        html = self._html(invoice)
        self.assertIn('alt="Camino Media"', html)
        self.assertNotIn('alt="Production Service Network"', html)

    def test_brand_falls_back_to_its_name_without_logo(self):
        self.env.company.camino_psn_logo = False
        html = self._html(self._invoice_with_line())
        self.assertIn("Production Service Network", html)

    # --- project type -----------------------------------------------------
    def test_project_type_has_the_six_categories_and_can_be_grouped(self):
        values = dict(self.env["account.move"]._fields["camino_project_type"].selection)
        self.assertEqual(
            set(values),
            {"advertising", "film", "tv", "documentary", "spot", "still_photo"},
        )
        self._invoice(camino_project_type="film")
        self._invoice(camino_project_type="spot")
        found = self.env["account.move"].search([("camino_project_type", "=", "film")])
        self.assertTrue(found)

    def test_project_type_filters_are_in_the_search_view(self):
        arch = self.env["account.move"].get_view(view_type="search")["arch"]
        for name in ("camino_type_film", "camino_type_spot", "camino_group_project_type"):
            self.assertIn(name, arch)

    # --- internal fields --------------------------------------------------
    def test_project_code_and_purchase_order_are_printed(self):
        html = self._html(
            self._invoice(camino_project_code="Project 583", camino_purchase_order="PO-77")
        )
        self.assertIn("Project 583", html)
        self.assertIn("PO-77", html)
        self.assertIn("Orden de compra", html)

    def test_purchase_order_is_omitted_when_empty(self):
        html = self._html(self._invoice())
        self.assertNotIn('name="camino_purchase_order"', html)
        self.assertNotIn('name="camino_project_code"', html)

    def test_internal_fields_are_never_printed(self):
        invoice = self._invoice_with_line(camino_channel="ny_rep")
        invoice.camino_internal_note = "Pay in 60 days, call Ana"
        html = self._html(invoice)
        self.assertNotIn("Pay in 60 days", html)
        self.assertNotIn("New York Representative", html)

    def test_line_channel_defaults_from_the_invoice(self):
        invoice = self._invoice_with_line(camino_channel=False)
        invoice.camino_channel = "london_rep"
        self.assertEqual(invoice.invoice_line_ids.camino_channel, "london_rep")

    def test_line_channel_can_differ_from_the_invoice(self):
        invoice = self._invoice_with_line(camino_channel="hollywood_rep")
        invoice.camino_channel = "referral"
        self.assertEqual(invoice.invoice_line_ids.camino_channel, "hollywood_rep")

    def test_internal_fields_are_hidden_from_portal_users(self):
        portal = self.env["res.users"].create(
            {
                "name": "Portal",
                "login": "portal_camino",
                "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
            }
        )
        fields_get = self.env["account.move"].with_user(portal).fields_get()
        for name in ("camino_channel", "camino_internal_note"):
            self.assertNotIn(name, fields_get)
        self.assertIn(
            "camino_channel", self.env["account.move"].fields_get()
        )

    def test_internal_fields_are_in_the_form(self):
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        for name in (
            "camino_brand", "camino_project_type", "camino_project_code",
            "camino_purchase_order", "camino_channel", "camino_internal_note",
            "camino_description",
        ):
            self.assertIn(f'name="{name}"', arch)

    def test_new_fields_are_not_copied(self):
        invoice = self._invoice(
            camino_project_type="tv", camino_project_code="P1",
            camino_purchase_order="PO", camino_channel="partner",
            camino_internal_note="x",
        )
        copy = invoice.copy()
        for name in ("camino_project_type", "camino_project_code",
                     "camino_purchase_order", "camino_channel", "camino_internal_note"):
            self.assertFalse(copy[name], name)

    # --- dynamic bank account ---------------------------------------------
    def test_invoice_in_pounds_picks_the_pound_account(self):
        self._archive_company_banks()
        self._company_bank("ES7821002865591301038677", self.env.ref("base.EUR"))
        gbp_bank = self._company_bank("ES0000000000000000000001", self.env.ref("base.GBP"))
        invoice = self._invoice(currency_id=self.env.ref("base.GBP").id)
        self.assertEqual(invoice.partner_bank_id, gbp_bank)

    def test_changing_the_currency_changes_the_bank_account(self):
        self._archive_company_banks()
        eur = self._company_bank("ES7821002865591301038677", self.env.ref("base.EUR"))
        usd = self._company_bank("ES6115830001129366855586", self.env.ref("base.USD"))
        invoice = self._invoice(currency_id=self.env.ref("base.EUR").id)
        self.assertEqual(invoice.partner_bank_id, eur)
        invoice.currency_id = self.env.ref("base.USD")
        self.assertEqual(invoice.partner_bank_id, usd)

    def test_bank_account_is_in_the_header_filtered_by_currency(self):
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        self.assertIn("('currency_id', '=', currency_id)", arch)

    # --- payment notice ---------------------------------------------------
    def test_default_payment_notice_is_red_bold_and_bilingual(self):
        self._archive_company_banks()
        self._company_bank("ES7821002865591301038677", self.env.ref("base.EUR"))
        html = self._html(self._invoice(currency_id=self.env.ref("base.EUR").id))
        self.assertIn('name="camino_payment_notice"', html)
        self.assertIn("fw-bold text-danger", html)
        self.assertIn("All bank charges are for the account of the payer", html)
        self.assertIn("Todos los gastos bancarios corren a cargo del pagador", html)
        self.assertIn("currency of the account", html)

    def test_bank_specific_warning_replaces_the_default_notice(self):
        self._archive_company_banks()
        self._company_bank(
            "ES7821002865591301038677", self.env.ref("base.EUR"),
            camino_invoice_warning="CUSTOM WARNING",
        )
        html = self._html(self._invoice(currency_id=self.env.ref("base.EUR").id))
        self.assertIn("CUSTOM WARNING", html)
        self.assertNotIn("All bank charges", html)

    # --- followers --------------------------------------------------------
    def test_company_followers_are_subscribed_to_new_invoices(self):
        accounting = self.env["res.partner"].create(
            {"name": "Contabilidad", "email": "conta@example.com"}
        )
        self.env.company.camino_invoice_follower_ids = accounting
        invoice = self._invoice()
        self.assertIn(accounting, invoice.message_partner_ids)
        # They actually receive the messages posted when sending the invoice.
        message = invoice.message_post(
            body="Invoice", subtype_xmlid="mail.mt_comment", partner_ids=self.partner.ids
        )
        self.assertIn(accounting, message.notified_partner_ids)

    def test_no_followers_added_without_configuration(self):
        self.env.company.camino_invoice_follower_ids = False
        invoice = self._invoice()
        self.assertFalse(invoice.message_partner_ids & self.env["res.partner"].search(
            [("email", "=", "conta@example.com")]))

    def test_customer_default_payment_method_does_not_override_the_currency(self):
        # Customers with a default inbound payment method used to get the journal
        # account (or nothing) instead of the account of the invoice currency.
        self._archive_company_banks()
        eur = self._company_bank("ES7821002865591301038677", self.env.ref("base.EUR"))
        usd = self._company_bank("ES6115830001129366855586", self.env.ref("base.USD"))
        journal = self.env["account.journal"].search([("type", "=", "bank")], limit=1)
        line = journal.inbound_payment_method_line_ids[:1]
        self.partner.property_inbound_payment_method_line_id = line
        self.assertEqual(self._invoice(currency_id=self.env.ref("base.USD").id).partner_bank_id, usd)
        self.assertEqual(self._invoice(currency_id=self.env.ref("base.EUR").id).partner_bank_id, eur)

    def test_credit_note_also_gets_the_bank_of_its_currency(self):
        self._archive_company_banks()
        usd = self._company_bank("ES6115830001129366855586", self.env.ref("base.USD"))
        refund = self._invoice(move_type="out_refund", currency_id=self.env.ref("base.USD").id)
        self.assertEqual(refund.partner_bank_id, usd)
