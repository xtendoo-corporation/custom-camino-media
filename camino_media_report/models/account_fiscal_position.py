from odoo import api, fields, models

# Frases de la gestoría para las operaciones no sujetas, por posición fiscal de la plantilla es.
VAT_LEGENDS = {
    "fp_intra": (
        "Reverse charge.",
        "Operación no sujeta por inversión del sujeto pasivo",
    ),
    "fp_extra": (
        "Service not subject to Spanish VAT under Article 69 of the Spanish VAT Act (Ley 37/1992).",
        "Operación no sujeta por estar localizada en sede del destinatario en virtud del "
        "artículo 69 de la Ley 37/1992",
    ),
}


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    camino_legend_en = fields.Text(
        string="Invoice Legend (EN)",
        help="Printed in black under the totals, preceded by an asterisk.",
    )
    camino_legend_es = fields.Text(
        string="Invoice Legend (ES)",
        help="Printed in grey and smaller, after the English legend.",
    )

    @api.model
    def _camino_load_vat_legends(self):
        """Load the legends on the intra/extra-community positions that still have none."""
        for company in self.env["res.company"].search([]):
            for suffix, (english, spanish) in VAT_LEGENDS.items():
                position = self.env.ref(
                    f"account.{company.id}_{suffix}", raise_if_not_found=False
                )
                if position and not (position.camino_legend_en or position.camino_legend_es):
                    position.write({"camino_legend_en": english, "camino_legend_es": spanish})
