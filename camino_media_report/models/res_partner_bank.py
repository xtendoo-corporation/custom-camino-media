from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    camino_intermediary_bic = fields.Char(string="Intermediary BIC")
    camino_bank_address = fields.Text(string="Bank Address")
    camino_invoice_warning = fields.Text(
        string="Invoice Warning",
        help="Red bold text printed under the bank details of invoices.",
    )
    camino_payment_title = fields.Text(
        string="Payment Instructions",
        help='Header of the payment block, e.g. "Payment in euros (EUR) by wire/bank '
        'transfer or direct deposit." One line per sentence.',
    )
    camino_account_notice = fields.Char(
        string="Account Notice",
        help='Red bold line above the payment block, e.g. "ACCOUNT IN US DOLLARS ONLY".',
    )
