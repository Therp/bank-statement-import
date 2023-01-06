# Copyright 2022 Therp BV <https://therp.nl>.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Define model to hold data retrieved from Ponto."""
import json
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PontoBuffer(models.Model):
    """Define model to hold data retrieved from Ponto."""

    _name = "ponto.buffer"
    _description = "Group transactions retrieved from Ponto."
    _order = "date desc"
    _rec_name = "date"

    provider_id = fields.Many2one(
        comodel_name="online.bank.statement.provider",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    date = fields.Date(readonly=True, required=True)
    buffer_line_ids = fields.One2many(
        comodel_name="ponto.buffer.line",
        inverse_name="buffer_id",
        readonly=True,
        string="Buffer Lines",
    )

    def _store_transactions(self, provider, transactions):
        """Store transactions retrieved from Ponto in buffer, preventing duplicates."""
        # Start by sorting all transactions per date.
        transactions_per_date = {}
        for transaction in transactions:
            date_time = provider._ponto_get_transaction_datetime(transaction)
            # Odoo does not support real isoformat, with "T":
            date_time_iso = date_time.isoformat().replace("T", " ")
            transaction["date_time"] = date_time_iso
            key = date_time_iso[0:10]
            if key not in transactions_per_date:
                transactions_per_date[key] = []  # Initialize transaction array.
            transactions_per_date[key].append(transaction)
        # Now store the transactions, but not when already present.
        for key, date_transactions in transactions_per_date.items():
            _logger.debug(
                "For date %s we retrieved %d transactions",
                key,
                len(date_transactions),
            )
            ponto_buffer = self.search(
                [
                    ("provider_id", "=", provider.id),
                    ("date", "=", key),
                ],
                limit=1,
            ) or self.create(
                {
                    "provider_id": provider.id,
                    "date": key,
                }
            )
            already_present = ponto_buffer.buffer_line_ids.mapped("ponto_id")
            new_lines = [
                (
                    0,
                    0,
                    {
                        "buffer_id": ponto_buffer.id,
                        "ponto_id": t.get("id"),
                        "date_time": t.get("date_time"),
                        "transaction_data": json.dumps(t),
                    },
                )
                for t in date_transactions
                if t.get("id") not in already_present
            ]
            if new_lines:
                ponto_buffer.write({"buffer_line_ids": new_lines})
