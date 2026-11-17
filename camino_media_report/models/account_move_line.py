from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    camino_name_es = fields.Text(string="Description (ES)", copy=False)
