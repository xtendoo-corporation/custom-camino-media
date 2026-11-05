from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    camino_location = fields.Char(string="Location", copy=False)
    camino_shoot_dates = fields.Char(string="Shoot Dates", copy=False)
    camino_contact = fields.Char(string="Contact", copy=False)
