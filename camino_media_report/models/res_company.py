from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    camino_psn_logo = fields.Binary(string="PSN Logo", attachment=True)
    camino_media_logo = fields.Binary(string="Camino Media Logo", attachment=True)
    camino_invoice_follower_ids = fields.Many2many(
        "res.partner",
        "camino_company_invoice_follower_rel",
        "company_id",
        "partner_id",
        string="Invoice Followers",
        help="Partners (partners and accounting) subscribed to every customer invoice "
        "and credit note, so they receive a copy of the sent emails.",
    )
    camino_print_line_origin = fields.Boolean(
        string="Print Work Origin on Lines",
        default=True,
        help='Prints "job from UK Rep" under the concept of the lines that have a '
        "representative as work origin.",
    )
