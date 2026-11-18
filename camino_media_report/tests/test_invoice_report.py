from odoo.tests import tagged
from odoo.tests.common import TransactionCase

NBSP = "\u00a0"
LOGO = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/"
    "q842iQAAAABJRU5ErkJggg=="
)


@tagged("post_install", "-at_install")
class TestCaminoInvoice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("base.EUR").active = True
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "20 Red Lights SRL",
                "street": "Via Procaccini 63",
                "zip": "20154",
                "city": "Milano",
                "country_id": cls.env.ref("base.it").id,
                "vat": "IT05539290964",
            }
        )

    # --- helpers --------------------------------------------------------------
    def _invoice(self, **values):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": "2026-06-18",
                **values,
            }
        )

    def _invoice_with_line(
        self, move_type="out_invoice", invoice_date="2026-06-18", **line_values
    ):
        account = self.env["account.account"].search(
            [("account_type", "=", "income")], limit=1
        )
        values = {
            "name": "Management fee 2026",
            "quantity": 1,
            "price_unit": 2000.0,
            "account_id": account.id,
            "tax_ids": [(5, 0, 0)],
            **line_values,
        }
        return self._invoice(
            move_type=move_type,
            invoice_date=invoice_date,
            invoice_line_ids=[(0, 0, values)],
        )

    def _html(self, invoice):
        html, _fmt = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices", invoice.ids
        )
        return html.decode()

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

    def _eur_bank(self, **values):
        self._archive_company_banks()
        return self._company_bank(
            "ES7821002865591301038677", self.env.ref("base.EUR"), **values
        )

    # --- fields ---------------------------------------------------------------
    def test_fields_are_stored_and_not_copied(self):
        invoice = self._invoice(
            camino_location="Madrid",
            camino_shoot_dates="1-3 marzo",
            camino_contact="Ana",
            camino_project_type="tv",
            camino_project_code="P1",
            camino_purchase_order="PO",
            camino_channel="partner",
            camino_internal_note="x",
        )
        self.assertEqual(invoice.camino_location, "Madrid")
        copy = invoice.copy()
        for name in (
            "camino_location", "camino_shoot_dates", "camino_contact",
            "camino_project_type", "camino_project_code", "camino_purchase_order",
            "camino_channel", "camino_internal_note",
        ):
            self.assertFalse(copy[name], name)

    def test_line_fields_are_stored_and_not_copied(self):
        invoice = self._invoice_with_line(
            camino_name_es="Gestión anual",
            camino_description="(12 July 2026 - 11 July 2027)",
            camino_project_code="PROJ583",
        )
        line = invoice.invoice_line_ids
        self.assertEqual(line.camino_project_code, "PROJ583")
        copy = invoice.copy().invoice_line_ids
        for name in ("camino_name_es", "camino_description", "camino_project_code"):
            self.assertFalse(copy[name], name)

    def test_brand_defaults_to_psn(self):
        self.assertEqual(self._invoice().camino_brand, "psn")

    def test_project_type_has_the_six_categories(self):
        values = dict(self.env["account.move"]._fields["camino_project_type"].selection)
        self.assertEqual(
            set(values),
            {"advertising", "film", "tv", "documentary", "spot", "still_photo"},
        )
        self._invoice(camino_project_type="film")
        found = self.env["account.move"].search([("camino_project_type", "=", "film")])
        self.assertTrue(found)

    def test_views_have_the_new_fields_and_filters(self):
        form = self.env["account.move"].get_view(view_type="form")["arch"]
        for name in (
            "camino_brand", "camino_project_type", "camino_project_code",
            "camino_purchase_order", "camino_channel", "camino_internal_note",
            "camino_description", "camino_location", "camino_shoot_dates",
            "camino_contact", "camino_name_es",
        ):
            self.assertIn(f'name="{name}"', form)
        search = self.env["account.move"].get_view(view_type="search")["arch"]
        for name in ("camino_type_film", "camino_type_spot", "camino_group_project_type"):
            self.assertIn(name, search)

    def _line_list_fields(self):
        from lxml import etree

        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        root = etree.fromstring(arch)
        lists = root.xpath("//field[@name='invoice_line_ids']/list")
        self.assertTrue(lists)
        fields = {}
        for field in lists[0].xpath("field"):
            # product_uom_id appears twice; keep the first (visible) occurrence
            fields.setdefault(field.get("name"), field)
        return fields

    def test_customer_lines_hide_product_quantity_unit_and_discount(self):
        fields = self._line_list_fields()
        for name in ("product_id", "quantity", "discount"):
            self.assertIn("out_invoice", fields[name].get("column_invisible") or "", name)

    def test_customer_line_columns_are_the_camino_ones(self):
        fields = self._line_list_fields()
        for name in (
            "name", "camino_project_code", "camino_description", "camino_name_es",
            "camino_channel", "price_unit",
        ):
            self.assertIn(name, fields)
            self.assertFalse(fields[name].get("column_invisible"), name)

    def test_taxes_stay_available_but_hidden_by_default(self):
        tax_field = self._line_list_fields()["tax_ids"]
        self.assertEqual(tax_field.get("optional"), "hide")

    def test_line_quantity_defaults_to_one(self):
        account = self.env["account.account"].search([("account_type", "=", "income")], limit=1)
        invoice = self._invoice(
            invoice_line_ids=[(0, 0, {"name": "Fee", "price_unit": 500.0, "account_id": account.id, "tax_ids": [(5, 0, 0)]})]
        )
        self.assertEqual(invoice.invoice_line_ids.quantity, 1.0)
        self.assertEqual(invoice.amount_total, 500.0)

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
        self.assertIn("camino_channel", self.env["account.move"].fields_get())

    # --- print helpers ----------------------------------------------------------
    def test_money_format(self):
        move = self._invoice()
        self.assertEqual(move._camino_money(11971.52), f"11{NBSP}971,52")
        self.assertEqual(move._camino_money(-2000), f"-2{NBSP}000,00")
        self.assertEqual(move._camino_money(0), "0,00")

    def test_date_is_printed_in_english(self):
        self.partner.lang = "es_ES"
        self.assertEqual(self._invoice()._camino_date(self._invoice().invoice_date), "18 June 2026")

    def test_vat_gets_a_space_after_the_country(self):
        self.assertEqual(self._invoice()._camino_vat(self.partner), "IT 05539290964")

    def test_vat_typed_with_its_own_format_is_left_alone(self):
        jordan = self.env["res.partner"].create(
            {"name": "Fluid", "vat": "VAT: 4081064", "country_id": self.env.ref("base.jo").id}
        )
        self.assertEqual(self._invoice()._camino_vat(jordan), "VAT: 4081064")

    def test_same_text_labels_are_not_repeated(self):
        label = str(self._invoice()._camino_label("sub_total"))
        self.assertEqual(label, "SUB TOTAL")

    def test_totals_table_is_not_wider_than_the_page(self):
        html = self._html(self._invoice_with_line())
        self.assertIn(".cm-invoice .cm-totals", html)
        self.assertIn("border: 0", html)

    def test_address_lines_end_with_the_country_in_capitals(self):
        lines = self._invoice()._camino_partner_lines(self.partner)
        self.assertEqual(lines, ["Via Procaccini 63", "20154 Milano", "ITALY"])

    def test_us_address_puts_the_state_after_the_city(self):
        us = self.env["res.partner"].create(
            {
                "name": "Six Continents Hotels, Inc.",
                "street": "3 Ravinia Drive, Suite 100",
                "city": "Atlanta",
                "zip": "30346",
                "country_id": self.env.ref("base.us").id,
                "state_id": self.env["res.country.state"].search(
                    [("country_id", "=", self.env.ref("base.us").id), ("code", "=", "GA")]
                ).id,
            }
        )
        lines = self._invoice()._camino_partner_lines(us)
        self.assertEqual(lines[1], "Atlanta, Georgia 30346")
        self.assertEqual(lines[2], "UNITED STATES")

    # --- report: structure --------------------------------------------------------
    def test_customer_documents_use_the_camino_template(self):
        for move_type in ("out_invoice", "out_refund"):
            self.assertEqual(
                self._invoice(move_type=move_type)._get_name_invoice_report(),
                "camino_media_report.report_camino_invoice_document",
            )

    def test_vendor_bills_keep_the_standard_template(self):
        bill = self._invoice(move_type="in_invoice")
        self.assertEqual(bill._get_name_invoice_report(), "account.report_invoice_document")

    def test_report_asks_for_small_page_margins(self):
        html = self._html(self._invoice_with_line())
        self.assertIn('data-report-margin-top="9"', html)
        self.assertIn('data-report-header-spacing="1"', html)
        self.assertIn('data-report-margin-bottom="16"', html)

    def test_vendor_bill_report_keeps_the_standard_margins(self):
        bill = self._invoice_with_line(move_type="in_invoice")
        html = self._html(bill)
        self.assertNotIn("cm-invoice", html)
        self.assertNotIn("data-report-margin-top", html)
        self.assertNotIn("data-report-margin-bottom", html)

    def test_report_has_no_standard_layout(self):
        html = self._html(self._invoice_with_line())
        self.assertIn("cm-invoice", html)
        self.assertNotIn("o_company_", html)

    def test_header_grid_labels_are_bilingual(self):
        html = self._html(self._invoice_with_line())
        for text in (
            "Invoice #", "Nº Factura", "Purchase Order #", "Nº orden de compra",
            "Date", "Fecha", "Location", "Localización", "Shoot Dates",
            "Fechas de rodaje", "Client", "Cliente", "Issued by", "Emitida por",
            "Telephone", "Teléfono", "VAT / CIF", "Email",
            "Description", "Descripción",
        ):
            self.assertIn(text, html)

    def test_spanish_labels_are_italic_grey_and_small(self):
        html = self._html(self._invoice_with_line())
        self.assertIn('class="camino-es"', html)
        self.assertIn("font-style: italic", html)
        self.assertIn("color: #6c757d", html)
        self.assertIn("font-size: 85%", html)

    def test_labels_stay_bilingual_whatever_the_customer_language(self):
        self.partner.lang = "en_US"
        html = self._html(self._invoice_with_line())
        self.assertIn("Fecha", html)
        self.assertIn("Cliente", html)

    def test_report_shows_the_invoice_data(self):
        invoice = self._invoice_with_line(
            camino_name_es="x"
        )
        invoice.write(
            {
                "camino_location": "Italy",
                "camino_shoot_dates": "27 May, 1 day",
                "camino_contact": "Luca de Angelis",
                "camino_purchase_order": "PO AKUSD-2001293271",
                "camino_project_code": "Project 583",
            }
        )
        invoice.action_post()
        html = self._html(invoice)
        for text in (
            "18 June 2026", "Italy", "27 May, 1 day", "Luca de Angelis",
            "PO AKUSD-2001293271", "Project 583", invoice.name,
        ):
            self.assertIn(text, html)

    def test_empty_optional_data_prints_na_on_invoices(self):
        html = self._html(self._invoice_with_line())
        self.assertEqual(html.count("N/A"), 3)

    def test_empty_optional_data_prints_na_on_credit_notes_too(self):
        refund = self._invoice_with_line(move_type="out_refund")
        self.assertEqual(self._html(refund).count("N/A"), 3)

    def test_client_and_issuer_blocks(self):
        html = self._html(self._invoice_with_line())
        for text in (
            "20 Red Lights SRL", "Via Procaccini 63", "20154 Milano", "ITALY",
            "IT 05539290964", self.env.company.partner_id.name,
        ):
            self.assertIn(text, html)
        phone = self.env.company.partner_id
        phone.write({"phone": "+34 699 92 62 49", "email": "finance@caminomedia.com"})
        html = self._html(self._invoice_with_line())
        self.assertIn("+34 699 92 62 49", html)
        self.assertNotIn("Tel:", html)
        self.assertIn("finance@caminomedia.com", html)

    def test_footer_is_a_real_page_footer(self):
        # Odoo moves div.footer to the bottom margin of every page (wkhtmltopdf footer).
        self.env.company.report_footer = "<p>Sociedad Limitada, inscrita en el Registro Mercantil</p>"
        html = self._html(self._invoice_with_line())
        self.assertRegex(html, r'<div class="footer" name="camino_footer">')
        self.assertNotIn("cm-footer", html)

    def test_footer_is_omitted_without_registry_text(self):
        self.env.company.report_footer = False
        self.assertNotIn('name="camino_footer"', self._html(self._invoice_with_line()))

    def test_footer_prints_the_company_registry_text(self):
        company = self.env.company
        company.report_footer = "<p>Sociedad Limitada, inscrita en el Registro Mercantil</p>"
        html = self._html(self._invoice_with_line())
        self.assertIn("Sociedad Limitada, inscrita en el Registro Mercantil", html)

    # --- report: lines ----------------------------------------------------------
    def test_report_keeps_only_description_and_amount_columns(self):
        html = self._html(self._invoice_with_line())
        for column in ("th_quantity", "th_priceunit", "th_discount", "th_taxes"):
            self.assertNotIn(f'name="{column}"', html)
        self.assertIn('name="th_description"', html)
        self.assertIn('name="th_subtotal"', html)

    def test_line_concept_description_and_translation(self):
        html = self._html(
            self._invoice_with_line(
                name="Fee corresponding to PROJ583 Kraken",
                camino_description="(Kode Media's shoot for Kraken in Italy)",
                camino_name_es="Gestión de servicios de producción en Italia",
            )
        )
        self.assertIn("Fee corresponding to PROJ583 Kraken", html)
        self.assertIn('class="cm-concept"', html)
        self.assertIn('class="cm-desc"', html)
        self.assertIn("(Kode Media&#39;s shoot for Kraken in Italy)", html)
        self.assertIn("Gestión de servicios de producción en Italia", html)
        self.assertIn("color: #6c757d", html)

    def test_extra_lines_of_the_name_are_kept(self):
        html = self._html(self._invoice_with_line(name="PSN PROJ552\n2 of 2 invoices, rest"))
        self.assertIn("2 of 2 invoices, rest", html)

    def test_project_code_chip_is_printed_unless_already_in_the_concept(self):
        html = self._html(self._invoice_with_line(camino_project_code="PROJ777"))
        self.assertIn('class="cm-code"', html)
        self.assertIn("PROJ777", html)
        html = self._html(
            self._invoice_with_line(name="Fee PROJ583 Kraken", camino_project_code="PROJ583")
        )
        self.assertNotIn('class="cm-code"', html)

    def test_work_origin_is_printed_on_representative_lines(self):
        html = self._html(self._invoice_with_line(camino_channel="london_rep"))
        self.assertIn("job from UK Rep", html)
        html = self._html(self._invoice_with_line(camino_channel="ny_rep"))
        self.assertIn("job from US Rep", html)

    def test_work_origin_is_not_printed_for_referrals_or_when_disabled(self):
        html = self._html(self._invoice_with_line(camino_channel="referral"))
        self.assertNotIn("job from", html)
        self.env.company.camino_print_line_origin = False
        html = self._html(self._invoice_with_line(camino_channel="london_rep"))
        self.assertNotIn("job from", html)

    def test_internal_data_is_never_printed(self):
        invoice = self._invoice_with_line()
        invoice.camino_internal_note = "Pay in 60 days, call Ana"
        invoice.camino_channel = "partner"
        html = self._html(invoice)
        self.assertNotIn("Pay in 60 days", html)
        self.assertNotIn("Partner", html.replace("Partnership", ""))

    # --- report: totals -------------------------------------------------------------
    def test_totals_are_bilingual_and_exempt_vat(self):
        invoice = self._invoice_with_line()
        invoice.currency_id = self.env.ref("base.EUR")
        invoice.action_post()
        html = self._html(invoice)
        for text in (
            "SUB TOTAL", "TAX BASE", "BASE IMPONIBLE", "VAT (EXEMPT)", "IVA (EXENTO)",
            "TOTAL INVOICE", "TOTAL FACTURA", f"2{NBSP}000,00{NBSP}€",
        ):
            self.assertIn(text, html)
        self.assertIn("EUROS €", html)

    def test_taxed_invoice_prints_the_vat_amount(self):
        tax = self.env["account.tax"].create(
            {"name": "IVA 21 test", "amount": 21.0, "amount_type": "percent", "type_tax_use": "sale"}
        )
        invoice = self._invoice_with_line(tax_ids=[(6, 0, tax.ids)])
        invoice.currency_id = self.env.ref("base.EUR")
        html = self._html(invoice)
        self.assertNotIn("VAT (EXEMPT)", html)
        self.assertIn("21%", html)
        self.assertIn(f"420,00{NBSP}€", html)

    def test_dollar_invoice_prefixes_the_currency(self):
        invoice = self._invoice_with_line(price_unit=24941.39)
        invoice.currency_id = self.env.ref("base.USD")
        html = self._html(invoice)
        self.assertIn('class="cm-cur"', html)
        self.assertIn(f"24{NBSP}941,39", html)
        self.assertNotIn("EUROS", html)
        self.assertIn(">USD<", html)

    def test_payment_term_note_is_printed_in_red(self):
        term = self.env["account.payment.term"].create(
            {"name": "Immediate", "note": "PAYMENT DUE UPON RECEIPT OF INVOICE"}
        )
        invoice = self._invoice_with_line()
        invoice.invoice_payment_term_id = term
        html = self._html(invoice)
        self.assertIn('name="camino_payment_due"', html)
        self.assertIn("PAYMENT DUE UPON RECEIPT OF INVOICE", html)

    def test_fiscal_position_legend_is_printed(self):
        position = self.env["account.fiscal.position"].create(
            {"name": "Extra", "note": "Operación no sujeta por reglas de localización"}
        )
        invoice = self._invoice_with_line()
        invoice.fiscal_position_id = position
        self.assertIn("Operación no sujeta", self._html(invoice))

    # --- report: credit note ----------------------------------------------------------
    def test_credit_note_has_the_red_box_and_no_bank_block(self):
        self._eur_bank()
        invoice = self._invoice_with_line()
        invoice.action_post()
        refund = self._invoice_with_line(move_type="out_refund", price_unit=2000.0)
        refund.reversed_entry_id = invoice
        html = self._html(refund)
        self.assertIn('name="camino_credit_note_box"', html)
        self.assertIn("CREDIT NOTE", html)
        self.assertIn(invoice.name, html)
        self.assertNotIn('name="camino_bank_block"', html)
        self.assertIn(f"-2{NBSP}000,00", html)

    def test_invoice_has_no_credit_note_box(self):
        self.assertNotIn('name="camino_credit_note_box"', self._html(self._invoice_with_line()))

    def test_credit_note_title_is_bilingual(self):
        html = self._html(self._invoice_with_line(move_type="out_refund"))
        self.assertIn("Factura rectificativa", html)

    # --- VAT legends (gestoría) ------------------------------------------------------------
    def _position(self, **values):
        return self.env["account.fiscal.position"].create({"name": "Test position", **values})

    def test_vat_legend_is_printed_under_the_totals_with_an_asterisk(self):
        invoice = self._invoice_with_line()
        invoice.fiscal_position_id = self._position(
            camino_legend_en="Reverse charge.",
            camino_legend_es="Operación no sujeta por inversión del sujeto pasivo",
        )
        html = self._html(invoice)
        self.assertIn('name="camino_vat_legend"', html)
        self.assertIn("* Reverse charge.", html)
        self.assertIn("Operación no sujeta por inversión del sujeto pasivo", html)
        # English first (black), Spanish after (grey, smaller)
        self.assertLess(html.index("* Reverse charge."), html.index("Operación no sujeta por inversión"))
        self.assertIn(".cm-invoice .cm-vl-es { font-size: 8pt; color: #8a909c; }", html)
        # the asterisk also marks the VAT row
        self.assertRegex(html, r"IVA \(EXENTO\)</span></strong>\s*<strong> \*</strong>")
        # and it comes after the totals
        self.assertLess(html.index('name="camino_totals"'), html.index('name="camino_vat_legend"'))

    def test_extra_community_legend_text(self):
        invoice = self._invoice_with_line()
        invoice.fiscal_position_id = self._position(
            camino_legend_en="Service not subject to Spanish VAT under Article 69 of the Spanish VAT Act (Ley 37/1992).",
            camino_legend_es="Operación no sujeta por estar localizada en sede del destinatario en virtud del artículo 69 de la Ley 37/1992",
        )
        html = self._html(invoice)
        self.assertIn("* Service not subject to Spanish VAT under Article 69", html)
        self.assertIn("artículo 69 de la Ley 37/1992", html)

    def test_short_legend_keeps_both_languages_on_one_line(self):
        invoice = self._invoice_with_line()
        invoice.fiscal_position_id = self._position(
            camino_legend_en="Reverse charge.", camino_legend_es="Operación no sujeta"
        )
        html = self._html(invoice)
        self.assertRegex(html, rf"Reverse charge\.</span>\s*{NBSP}{NBSP}")
        self.assertNotIn('class="cm-vl-es" style="display: block;"', html)

    def test_long_legend_puts_the_spanish_text_on_its_own_line(self):
        invoice = self._invoice_with_line()
        invoice.fiscal_position_id = self._position(
            camino_legend_en="Service not subject to Spanish VAT under Article 69 of the Spanish VAT Act (Ley 37/1992).",
            camino_legend_es="Operación no sujeta por estar localizada en sede del destinatario",
        )
        html = self._html(invoice)
        self.assertIn('class="cm-vl-es" style="display: block;"', html)

    def test_no_vat_legend_without_a_legend(self):
        html = self._html(self._invoice_with_line())
        self.assertNotIn('name="camino_vat_legend"', html)
        self.assertNotRegex(html, r"IVA \(EXENTO\)</span></strong>\s*<strong> \*</strong>")

    def test_fiscal_position_note_is_still_used_without_camino_legend(self):
        invoice = self._invoice_with_line()
        invoice.fiscal_position_id = self._position(note="Nota fiscal antigua")
        html = self._html(invoice)
        self.assertIn("Nota fiscal antigua", html)
        self.assertNotIn('name="camino_vat_legend"', html)

    def test_legends_are_loaded_on_intra_and_extra_community_positions(self):
        company = self.env.company
        positions = {}
        for suffix in ("fp_intra", "fp_extra"):
            position = self._position(name=suffix)
            self.env["ir.model.data"].create(
                {"module": "account", "name": f"{company.id}_{suffix}",
                 "model": "account.fiscal.position", "res_id": position.id}
            )
            positions[suffix] = position
        self.env["account.fiscal.position"]._camino_load_vat_legends()
        self.assertEqual(positions["fp_intra"].camino_legend_en, "Reverse charge.")
        self.assertEqual(
            positions["fp_intra"].camino_legend_es,
            "Operación no sujeta por inversión del sujeto pasivo",
        )
        self.assertIn("Article 69 of the Spanish VAT Act (Ley 37/1992).", positions["fp_extra"].camino_legend_en)
        self.assertIn("artículo 69 de la Ley 37/1992", positions["fp_extra"].camino_legend_es)

    def test_loading_the_legends_never_overwrites_an_edited_one(self):
        company = self.env.company
        position = self._position(name="fp_intra", camino_legend_en="Mi texto")
        self.env["ir.model.data"].create(
            {"module": "account", "name": f"{company.id}_fp_intra",
             "model": "account.fiscal.position", "res_id": position.id}
        )
        self.env["account.fiscal.position"]._camino_load_vat_legends()
        self.assertEqual(position.camino_legend_en, "Mi texto")
        self.assertFalse(position.camino_legend_es)

    def test_fiscal_position_form_has_the_legend_fields(self):
        arch = self.env["account.fiscal.position"].get_view(view_type="form")["arch"]
        self.assertIn('name="camino_legend_en"', arch)
        self.assertIn('name="camino_legend_es"', arch)

    # --- credit note texts (gestoría) -------------------------------------------------------
    def _rectified_invoice(self):
        invoice = self._invoice_with_line(invoice_date="2026-08-18")
        invoice.action_post()
        refund = self._invoice_with_line(move_type="out_refund", invoice_date="2026-10-19")
        refund.reversed_entry_id = invoice
        return invoice, refund

    def test_credit_note_texts_name_the_invoice_and_its_date(self):
        invoice, refund = self._rectified_invoice()
        english, spanish = refund._camino_credit_note_texts()
        self.assertEqual(english, f"{invoice.name} OF 18 AUG 2026")
        self.assertEqual(spanish, f"{invoice.name} DE 18 AGOSTO 2026")

    def test_credit_note_has_a_red_english_box_and_a_grey_spanish_box(self):
        invoice, refund = self._rectified_invoice()
        html = self._html(refund)
        self.assertIn('name="camino_credit_note_box"', html)
        self.assertIn('name="camino_credit_note_box_es"', html)
        for text in (
            "CREDIT NOTE", f"TO INVOICE {invoice.name} OF 18 AUG 2026",
            "FACTURA RECTIFICATIVA", f"DE LA FACTURA {invoice.name} DE 18 AGOSTO 2026",
        ):
            self.assertIn(text, html)
        # English box first, grey Spanish one after
        self.assertLess(html.index('name="camino_credit_note_box"'), html.index('name="camino_credit_note_box_es"'))
        self.assertIn(".cm-invoice .cm-credit-es", html)

    def test_credit_note_without_a_rectified_invoice_uses_the_reference(self):
        refund = self._invoice_with_line(move_type="out_refund")
        refund.ref = "035-26"
        self.assertEqual(refund._camino_credit_note_texts(), ("035-26", "035-26"))
        self.assertIn("TO INVOICE 035-26", self._html(refund))

    def test_credit_note_header_has_the_red_tag_and_red_spanish_label(self):
        refund = self._invoice_with_line(move_type="out_refund", invoice_date="2026-10-19")
        refund.action_post()
        html = self._html(refund)
        self.assertIn("Factura rectificativa", html)
        self.assertRegex(html, r"Factura rectificativa</span>")
        self.assertIn("color: #c62828 !important", html)
        # CREDITNOTE/... already says it: no second tag
        self.assertNotIn('name="camino_credit_tag"', html)

    def test_credit_note_red_tag_is_added_when_the_number_does_not_say_it(self):
        refund = self._invoice_with_line(move_type="out_refund", invoice_date="2026-10-19")
        refund.action_post()
        refund.name = "065-26"
        html = self._html(refund)
        self.assertIn('name="camino_credit_tag"', html)
        self.assertIn("- CREDIT NOTE", html)

    def test_total_label_carries_the_invoice_number(self):
        invoice = self._invoice_with_line(invoice_date="2026-06-18")
        invoice.action_post()
        html = self._html(invoice)
        self.assertRegex(html, rf"TOTAL INVOICE {invoice.name}\s*<span[^>]*>TOTAL FACTURA</span>")

    # --- brand --------------------------------------------------------------------------
    def test_brand_header_shows_the_psn_logo(self):
        self.env.company.camino_psn_logo = LOGO
        html = self._html(self._invoice_with_line())
        self.assertIn('name="camino_brand_header"', html)
        self.assertIn('alt="Production Service Network"', html)
        self.assertNotIn('alt="Camino Media"', html)

    def test_camino_brand_shows_the_camino_header(self):
        self.env.company.camino_media_logo = LOGO
        invoice = self._invoice_with_line()
        invoice.camino_brand = "camino"
        html = self._html(invoice)
        self.assertIn('alt="Camino Media"', html)
        self.assertNotIn('alt="Production Service Network"', html)

    def test_brand_falls_back_to_its_name_without_logo(self):
        self.env.company.camino_psn_logo = False
        self.assertIn("Production Service Network", self._html(self._invoice_with_line()))

    # --- bank accounts ------------------------------------------------------------------
    def test_bank_account_stores_invoice_details(self):
        bank = self._eur_bank(
            camino_intermediary_bic="CHASGB2L",
            camino_bank_address="Calle Mayor 16, 28013 Madrid",
            camino_invoice_warning="Payments must be ordered in euros (EUR).",
            camino_payment_title="Payment in euros (EUR) by wire/bank transfer.",
            camino_account_notice="ACCOUNT IN EUROS ONLY",
        )
        self.assertEqual(bank.camino_intermediary_bic, "CHASGB2L")
        self.assertIn("ordered in euros", bank.camino_invoice_warning)
        self.assertEqual(bank.camino_account_notice, "ACCOUNT IN EUROS ONLY")

    def test_invoice_picks_the_bank_account_of_its_currency(self):
        self._archive_company_banks()
        eur = self._company_bank("ES7821002865591301038677", self.env.ref("base.EUR"))
        usd = self._company_bank("ES6115830001129366855586", self.env.ref("base.USD"))
        self.assertEqual(self._invoice(currency_id=self.env.ref("base.USD").id).partner_bank_id, usd)
        self.assertEqual(self._invoice(currency_id=self.env.ref("base.EUR").id).partner_bank_id, eur)

    def test_invoice_in_pounds_picks_the_pound_account(self):
        self._archive_company_banks()
        self._company_bank("ES7821002865591301038677", self.env.ref("base.EUR"))
        gbp = self._company_bank("ES0000000000000000000001", self.env.ref("base.GBP"))
        self.assertEqual(self._invoice(currency_id=self.env.ref("base.GBP").id).partner_bank_id, gbp)

    def test_changing_the_currency_changes_the_bank_account(self):
        self._archive_company_banks()
        eur = self._company_bank("ES7821002865591301038677", self.env.ref("base.EUR"))
        usd = self._company_bank("ES6115830001129366855586", self.env.ref("base.USD"))
        invoice = self._invoice(currency_id=self.env.ref("base.EUR").id)
        self.assertEqual(invoice.partner_bank_id, eur)
        invoice.currency_id = self.env.ref("base.USD")
        self.assertEqual(invoice.partner_bank_id, usd)

    def test_customer_default_payment_method_does_not_override_the_currency(self):
        self._archive_company_banks()
        eur = self._company_bank("ES7821002865591301038677", self.env.ref("base.EUR"))
        usd = self._company_bank("ES6115830001129366855586", self.env.ref("base.USD"))
        journal = self.env["account.journal"].search([("type", "=", "bank")], limit=1)
        self.partner.property_inbound_payment_method_line_id = journal.inbound_payment_method_line_ids[:1]
        self.assertEqual(self._invoice(currency_id=self.env.ref("base.USD").id).partner_bank_id, usd)
        self.assertEqual(self._invoice(currency_id=self.env.ref("base.EUR").id).partner_bank_id, eur)

    def test_credit_note_also_gets_the_bank_of_its_currency(self):
        self._archive_company_banks()
        usd = self._company_bank("ES6115830001129366855586", self.env.ref("base.USD"))
        refund = self._invoice(move_type="out_refund", currency_id=self.env.ref("base.USD").id)
        self.assertEqual(refund.partner_bank_id, usd)

    def test_bank_account_is_in_the_header_filtered_by_currency(self):
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        self.assertIn("('currency_id', '=', currency_id)", arch)

    def test_report_shows_the_bank_details(self):
        self._archive_company_banks()
        self._company_bank(
            "ES6115830001129366855586",
            self.env.ref("base.USD"),
            camino_intermediary_bic="CHASGB2L",
            camino_bank_address="Calle Príncipe de Vergara 132",
            camino_payment_title="Payment in USD by wire/bank transfer",
            camino_account_notice="ACCOUNT IN US DOLLARS ONLY",
            camino_invoice_warning="ALL TRANSACTION EXPENSES TO BE PAID BY THE PAYER.\nClients have agreed to select OUR.",
        )
        invoice = self._invoice_with_line()
        invoice.currency_id = self.env.ref("base.USD")
        html = self._html(invoice)
        self.assertIn('name="camino_bank_block"', html)
        for text in (
            "ES6115830001129366855586", "CHASGB2L", "Calle Príncipe de Vergara 132",
            "Payment in USD by wire/bank transfer", "Please cite invoice number",
            "Beneficiario", "Código SWIFT/BIC",
        ):
            self.assertIn(text, html)
        self.assertIn('name="camino_account_notice"', html)
        self.assertIn("ACCOUNT IN US DOLLARS ONLY", html)
        self.assertIn("ALL TRANSACTION EXPENSES TO BE PAID BY THE PAYER.", html)
        self.assertIn("Clients have agreed to select OUR.", html)

    def test_default_payment_texts_when_the_bank_has_none(self):
        self._eur_bank()
        html = self._html(self._invoice_with_line(currency_id=self.env.ref("base.EUR").id))
        self.assertIn("Payment by wire/bank transfer.", html)
        self.assertIn("All bank charges are for the account of the payer", html)
        self.assertIn("Todos los gastos bancarios corren a cargo del pagador", html)
        self.assertNotIn('name="camino_account_notice"', html)

    def test_bank_specific_warning_replaces_the_default_notice(self):
        self._eur_bank(camino_invoice_warning="CUSTOM WARNING")
        html = self._html(self._invoice_with_line(currency_id=self.env.ref("base.EUR").id))
        self.assertIn("CUSTOM WARNING", html)
        self.assertNotIn("All bank charges", html)

    def test_red_box_is_red(self):
        self._eur_bank()
        html = self._html(self._invoice_with_line(currency_id=self.env.ref("base.EUR").id))
        self.assertIn("cm-redbox", html)
        self.assertIn("#c62828", html)

    def test_report_hides_bank_block_without_account(self):
        self._archive_company_banks()
        self.assertNotIn('name="camino_bank_block"', self._html(self._invoice_with_line()))

    def test_optional_bank_lines_are_omitted_when_empty(self):
        self._eur_bank()
        html = self._html(self._invoice_with_line(currency_id=self.env.ref("base.EUR").id))
        self.assertNotIn("BIC intermediario", html)
        self.assertNotIn("Dirección", html)

    # --- numbering, currency, followers ---------------------------------------------------
    def test_invoice_gets_the_standard_invoice_sequence(self):
        invoice = self._invoice_with_line(invoice_date="2040-03-01")
        invoice.action_post()
        self.assertEqual(invoice.name, "INV/2040/00001")

    def test_credit_note_gets_its_own_sequence(self):
        refund = self._invoice_with_line(move_type="out_refund", invoice_date="2040-03-01")
        refund.action_post()
        self.assertEqual(refund.name, "CREDITNOTE/2040/00001")

    def test_credit_notes_are_numbered_consecutively(self):
        first = self._invoice_with_line(move_type="out_refund", invoice_date="2040-03-01")
        first.action_post()
        second = self._invoice_with_line(move_type="out_refund", invoice_date="2040-03-01")
        second.action_post()
        self.assertEqual(second.name, "CREDITNOTE/2040/00002")

    def test_invoices_and_credit_notes_keep_separate_sequences(self):
        invoice = self._invoice_with_line(invoice_date="2040-03-01")
        invoice.action_post()
        refund = self._invoice_with_line(move_type="out_refund", invoice_date="2040-03-01")
        refund.action_post()
        self.assertEqual(invoice.name, "INV/2040/00001")
        self.assertEqual(refund.name, "CREDITNOTE/2040/00001")

    def test_pound_sterling_is_available_and_usable(self):
        self.assertTrue(self.env.ref("base.GBP").active)
        invoice = self._invoice_with_line(invoice_date="2040-03-01")
        invoice.currency_id = self.env.ref("base.GBP")
        invoice.action_post()
        self.assertEqual(invoice.currency_id, self.env.ref("base.GBP"))

    def test_company_followers_are_subscribed_to_new_invoices(self):
        accounting = self.env["res.partner"].create(
            {"name": "Contabilidad", "email": "conta@example.com"}
        )
        self.env.company.camino_invoice_follower_ids = accounting
        invoice = self._invoice()
        self.assertIn(accounting, invoice.message_partner_ids)
        message = invoice.message_post(
            body="Invoice", subtype_xmlid="mail.mt_comment", partner_ids=self.partner.ids
        )
        self.assertIn(accounting, message.notified_partner_ids)

    def test_no_followers_added_without_configuration(self):
        self.env.company.camino_invoice_follower_ids = False
        invoice = self._invoice()
        self.assertFalse(
            invoice.message_partner_ids
            & self.env["res.partner"].search([("email", "=", "conta@example.com")])
        )
