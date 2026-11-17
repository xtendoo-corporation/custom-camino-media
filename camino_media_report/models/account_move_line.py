from odoo import api, fields, models

from .account_move import CHANNELS


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    camino_name_es = fields.Text(string="Description (ES)", copy=False)
    camino_description = fields.Text(
        string="Job Description",
        copy=False,
        help="Printed in italics under the concept, which is printed in bold. "
        "Write the brackets yourself if you want them.",
    )
    camino_project_code = fields.Char(
        string="Project Code",
        copy=False,
        help="Project of this line (e.g. PROJ583). Printed before the concept "
        "unless the concept already contains it.",
    )
    camino_channel = fields.Selection(
        CHANNELS,
        string="Work Origin",
        compute="_compute_camino_channel",
        store=True,
        readonly=False,
        copy=False,
        groups="account.group_account_invoice,account.group_account_readonly",
        help="Internal: representative that brought this job. Defaults from the invoice.",
    )

    @api.depends("move_id.camino_channel")
    def _compute_camino_channel(self):
        for line in self:
            if not line.camino_channel:
                line.camino_channel = line.move_id.sudo().camino_channel
