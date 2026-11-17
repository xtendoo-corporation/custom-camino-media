from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    camino_intermediary_bic = fields.Char(string="Intermediary BIC")
    camino_bank_address = fields.Text(string="Bank Address")
    camino_invoice_warning = fields.Text(
        string="Invoice Warning",
        help="Red bold text printed under the bank details of invoices.",
    )
