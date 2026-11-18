from babel.dates import format_date
from markupsafe import Markup

from odoo import api, fields, models

CREDIT_NOTE_PREFIX = "CREDITNOTE/"

PROJECT_TYPES = [
    ("advertising", "Advertising"),
    ("film", "Film"),
    ("tv", "TV"),
    ("documentary", "Documentary"),
    ("spot", "Spot"),
    ("still_photo", "Still Photography"),
]
CHANNELS = [
    ("ny_rep", "New York Representative"),
    ("london_rep", "London Representative"),
    ("hollywood_rep", "Hollywood Representative"),
    ("referral", "Referral"),
    ("partner", "Partner"),
]
BRANDS = [
    ("psn", "Production Service Network"),
    ("camino", "Camino Media"),
]
# Fixed (English, Spanish) pairs: the invoice always prints both languages,
# regardless of the customer language.
LABELS = {
    "invoice": ("Invoice", "Factura"),
    "credit_note": ("Credit Note", "Factura rectificativa"),
    "invoice_date": ("Invoice Date", "Fecha de factura"),
    "credit_note_date": ("Credit Note Date", "Fecha de la nota de crédito"),
    "due_date": ("Due Date", "Fecha de vencimiento"),
    "reference": ("Reference", "Referencia"),
    "description": ("Description", "Descripción"),
    "amount": ("Amount", "Importe"),
    "project_code": ("Project", "Proyecto"),
    "invoice_number": ("Invoice #", "Nº Factura"),
    "purchase_order_number": ("Purchase Order #", "Nº orden de compra"),
    "date": ("Date", "Fecha"),
    "client": ("Client", "Cliente"),
    "issued_by": ("Issued by", "Emitida por"),
    "telephone": ("Telephone", "Teléfono"),
    "vat_cif": ("VAT / CIF", "CIF"),
    "email": ("Email", "Correo"),
    "sub_total": ("SUB TOTAL", "SUB TOTAL"),
    "tax_base": ("TAX BASE", "BASE IMPONIBLE"),
    "vat_exempt": ("VAT (EXEMPT)", "IVA (EXENTO)"),
    "vat": ("VAT", "IVA"),
    "total": ("TOTAL INVOICE", "TOTAL FACTURA"),
    "credit_note_to": ("CREDIT NOTE", "FACTURA RECTIFICATIVA"),
    "to_invoice": ("TO INVOICE", "DE LA FACTURA"),
    "payment_default": (
        "Payment by wire/bank transfer.",
        "Pago por transferencia bancaria.",
    ),
    "contact_label": ("Contact", "Contacto"),
    "purchase_order": ("Purchase Order", "Orden de compra"),
    "location": ("Location", "Localización"),
    "shoot_dates": ("Shoot Dates", "Fechas de rodaje"),
    "contact": ("Contact", "Contacto"),
    "beneficiary": ("Beneficiary", "Beneficiario"),
    "bank": ("Bank", "Banco"),
    "swift": ("SWIFT/BIC Code", "Código SWIFT/BIC"),
    "iban": ("IBAN", "IBAN"),
    "intermediary_bic": ("Intermediary BIC", "BIC intermediario"),
    "bank_address": ("Address", "Dirección"),
    "cite_invoice": (
        "Please cite invoice number for our reference.",
        "Indique el número de factura como referencia.",
    ),
    "payment_notice": (
        "All bank charges are for the account of the payer. "
        "Payment must be made in the currency of the account.",
        "Todos los gastos bancarios corren a cargo del pagador. "
        "El pago debe hacerse en la moneda de la cuenta.",
    ),
}
# How the representative that brought a job is printed on the line ("job from UK Rep").
ORIGIN_PRINT = {
    "ny_rep": "US Rep",
    "london_rep": "UK Rep",
    "hollywood_rep": "US Rep (Hollywood)",
}
STATE_AFTER_CITY = ("US", "CA", "AU")
NBSP = "\u00a0"
ES_STYLE = "font-style: italic; color: #6c757d; font-size: 85%;"


class AccountMove(models.Model):
    _inherit = "account.move"

    camino_location = fields.Char(string="Location", copy=False)
    camino_shoot_dates = fields.Char(string="Shoot Dates", copy=False)
    camino_contact = fields.Char(string="Contact", copy=False)
    camino_brand = fields.Selection(
        BRANDS,
        string="Brand",
        default="psn",
        required=True,
        help="Brand whose header is printed on the invoice.",
    )
    camino_project_type = fields.Selection(
        PROJECT_TYPES,
        string="Project Type",
        index=True,
        copy=False,
        help="Classifies the invoice for the year-end review.",
    )
    camino_project_code = fields.Char(
        string="Project Code",
        copy=False,
        help="Matches the project code in the customer's CRM (e.g. Project 583).",
    )
    camino_purchase_order = fields.Char(string="Purchase Order", copy=False)
    camino_channel = fields.Selection(
        CHANNELS,
        string="Work Origin",
        copy=False,
        groups="account.group_account_invoice,account.group_account_readonly",
        help="Internal: who brought the job. Never printed on the invoice.",
    )
    camino_internal_note = fields.Text(
        string="Internal Note",
        copy=False,
        groups="account.group_account_invoice,account.group_account_readonly",
        help="Internal: payment agreements and collection reminders.",
    )

    def _get_name_invoice_report(self):
        # EXTENDS account: customer invoices and credit notes use the Camino Media format.
        if self.move_type in ("out_invoice", "out_refund"):
            return "camino_media_report.report_camino_invoice_document"
        return super()._get_name_invoice_report()

    # --- print helpers ----------------------------------------------------
    def _camino_money(self, amount):
        """Spanish number format used on the invoices: 11 971,52."""
        text = f"{abs(amount or 0.0):,.2f}".replace(",", NBSP).replace(".", ",")
        negative = round(amount or 0.0, 2) < 0
        return ("-" if negative else "") + text

    def _camino_amount_header(self):
        self.ensure_one()
        if self.currency_id.name == "EUR":
            return "EUROS €"
        return self.currency_id.name

    def _camino_date(self, date):
        return format_date(date, "d MMMM yyyy", locale="en_US") if date else ""

    def _camino_vat(self, partner):
        vat = (partner.vat or "").strip()
        prefix = vat[:2].upper()
        if len(vat) > 2 and vat[2] != " " and prefix in (partner.country_id.code, "EL"):
            return f"{vat[:2]} {vat[2:]}"
        return vat

    def _camino_partner_lines(self, partner):
        """Address lines of a partner, the country in capitals."""
        country = partner.country_id
        city = partner.city or ""
        zip_code = partner.zip or ""
        if country.code in STATE_AFTER_CITY and partner.state_id:
            locality = f"{city}, {partner.state_id.name} {zip_code}".strip()
        else:
            locality = f"{zip_code} {city}".strip()
        lines = [partner.street, partner.street2, locality, (country.name or "").upper()]
        return [line for line in lines if line]

    def _camino_line_origin(self, line):
        """"job from UK Rep": only when the company asks to print it."""
        self.ensure_one()
        if not self.company_id.sudo().camino_print_line_origin:
            return ""
        origin = ORIGIN_PRINT.get(line.sudo().camino_channel)
        return f"job from {origin}" if origin else ""

    def _camino_credit_target(self):
        self.ensure_one()
        return self.reversed_entry_id.name or self.ref or ""

    def _camino_credit_note_texts(self):
        """("051-26 OF 18 AUG 2026", "051-26 DE 18 AGOSTO 2026") for the rectified invoice."""
        self.ensure_one()
        target = self.reversed_entry_id
        number = target.name or self.ref or ""
        date = target.invoice_date
        if not date:
            return number, number
        english = format_date(date, "d MMM yyyy", locale="en_US").upper()
        spanish = format_date(date, "d MMMM yyyy", locale="es_ES").upper()
        return f"{number} OF {english}", f"{number} DE {spanish}"

    def _camino_vat_legend(self):
        """(English, Spanish) legend of the fiscal position, or None when it has none."""
        self.ensure_one()
        position = self.fiscal_position_id
        if position.camino_legend_en or position.camino_legend_es:
            return position.camino_legend_en or "", position.camino_legend_es or ""
        return None

    def _camino_vat_label(self):
        """VAT row label and the taxes it covers."""
        self.ensure_one()
        if not self.currency_id.is_zero(self.amount_tax):
            percents = sorted({t.amount for t in self.invoice_line_ids.tax_ids})
            names = ", ".join(f"{p:g}%" for p in percents)
            return "vat", names
        return "vat_exempt", ""

    @api.model
    def _camino_pair(self, key):
        """(English, Spanish) texts of a fixed label."""
        return LABELS[key]

    @api.model
    def _camino_label(self, key, block=False, color=None, middle=None):
        """Bilingual label: English followed by the Spanish one (italic, grey, small).

        ``block`` puts the Spanish text on its own line (narrow table columns), ``color``
        paints it with another colour (e.g. red) and ``middle`` goes between both texts.
        """
        english, spanish = LABELS[key]
        if middle:
            english = f"{english} {middle}"
        if english.lower() == spanish.lower():
            return Markup("{}").format(english)
        style = ES_STYLE + (" display: block;" if block else "")
        if color:
            style += f" color: {color} !important;"
        return Markup('{} <span class="camino-es" style="{}">{}</span>').format(
            english, style, spanish
        )

    def _compute_partner_bank_id(self):
        # EXTENDS account: on customer documents the collecting account must match the
        # invoice currency. The standard compute lets the customer's default payment
        # method (journal account) win, which ignores the currency.
        super()._compute_partner_bank_id()
        for move in self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund")):
            bank = move.partner_bank_id
            if bank and bank.active and bank.currency_id == move.currency_id:
                continue
            candidates = move.company_id.partner_id.bank_ids.filtered("active")
            match = candidates.filtered(lambda b: b.currency_id == move.currency_id)
            if match:
                move.partner_bank_id = match[:1]
            elif not bank:
                move.partner_bank_id = candidates.filtered(lambda b: not b.currency_id)[:1]

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves.filtered(
            lambda m: m.move_type in ("out_invoice", "out_refund")
        ):
            followers = move.company_id.camino_invoice_follower_ids
            if followers:
                move.message_subscribe(partner_ids=followers.ids)
        return moves

    def _get_last_sequence_domain(self, relaxed=False):
        # EXTENDS account: continue the credit note series only from credit notes
        # that already use CREDIT_NOTE_PREFIX, never from standard "R" refunds.
        where_string, param = super()._get_last_sequence_domain(relaxed=relaxed)
        if self.move_type == "out_refund" and self.journal_id.refund_sequence:
            where_string += " AND sequence_prefix LIKE %(credit_note_prefix)s "
            param["credit_note_prefix"] = CREDIT_NOTE_PREFIX + "%"
        return where_string, param

    def _get_starting_sequence(self):
        # EXTENDS account: credit notes use CREDIT_NOTE_PREFIX, not "R<journal code>/".
        starting_sequence = super()._get_starting_sequence()
        if self.move_type != "out_refund" or not self.journal_id.refund_sequence:
            return starting_sequence
        standard_prefix = f"R{self.journal_id.code}/"
        if starting_sequence.startswith(standard_prefix):
            return CREDIT_NOTE_PREFIX + starting_sequence[len(standard_prefix) :]
        return starting_sequence
