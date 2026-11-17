from odoo import fields, models

CREDIT_NOTE_PREFIX = "CREDITNOTE/"


class AccountMove(models.Model):
    _inherit = "account.move"

    camino_location = fields.Char(string="Location", copy=False)
    camino_shoot_dates = fields.Char(string="Shoot Dates", copy=False)
    camino_contact = fields.Char(string="Contact", copy=False)

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
