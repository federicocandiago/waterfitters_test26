# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tools import float_compare, float_is_zero, formatLang, end_of
from odoo import fields, models, api
from dateutil.relativedelta import relativedelta
from datetime import datetime
from math import ceil

class AccountAsset(models.Model):
    _inherit = 'account.asset'

    delete_residual_calculation = fields.Boolean(
        string="Delete Residual Calculation",
        help="Enables residual calculation for prorata, useful for handling special depreciation cases.",
        default=True
    )
    normalize_dates_to_jan_first = fields.Boolean(
        string="Reset PRORATA Dates (Jan 1st)",
        help="If checked, prorata dates are normalized to January 1st of the current year.",
        default=True
    )
    # Studio Fields (Migrated from Studio)
    standard_coefficient = fields.Float()
    first_year_halving = fields.Boolean()
    gain_account_id = fields.Many2one('account.account', string='Gain Account')
    loss_account_id = fields.Many2one('account.account', string='Loss Account')
    first_year_percentage = fields.Float()
    assets_type = fields.Selection([('material', 'Material'), ('immaterial', 'Intangible')])
    code = fields.Char()
    accounting_value = fields.Monetary()

    # SEQUENCE
    prefix_code = fields.Char()
    sequence_number = fields.Integer(default=0)
    sequence_code = fields.Char()

    # ASSET RELATED
    is_account_asset_child = fields.Boolean()
    parent_account_asset_id = fields.Many2one('account.asset', string='Related Asset',
                                              domain=[('is_account_asset_child', '=', False),
                                                      ('state', 'not in', ('model', 'draft', 'cancelled'))], )

    @api.depends('first_year_percentage', 'standard_coefficient', 'first_year_halving')
    def _onchange_method_number(self):
        if self.standard_coefficient:
            value = 100 / self.standard_coefficient
            self.method_number = ceil(value)
            if self.first_year_halving:
                self.method_number += 1

    def _compute_board_amount(self, residual_amount, period_start_date, period_end_date, days_already_depreciated,
                              days_left_to_depreciated, residual_declining, start_yearly_period=None,
                              total_lifetime_left=None,
                              residual_at_compute=None, start_recompute_date=None):

        if float_is_zero(self.asset_lifetime_days, 2) or float_is_zero(residual_amount, 2):
            return 0, 0

        # Save the current prorata date to restore later
        # If normalization is enabled, reset the prorata and period dates to January 1st
        # This ensures depreciation calculations align with the start of the calendar year
        old_pro_rata_date = self.paused_prorata_date
        if self.normalize_dates_to_jan_first:
            last_day_asset = self._get_last_day_asset().replace(day=1)
            days_left_to_depreciated = self._get_delta_days(period_start_date, last_day_asset)

            self.paused_prorata_date = self.paused_prorata_date.replace(day=1, month=1)
            period_start_date = period_start_date.replace(day=1, month=1)
            start_recompute_date = start_recompute_date.replace(day=1, month=1)

        days_until_period_end = self._get_delta_days(self.paused_prorata_date, period_end_date)
        days_before_period = self._get_delta_days(self.paused_prorata_date, period_start_date + relativedelta(days=-1))
        days_before_period = max(days_before_period, 0)  # if disposed before the beginning of the asset for example
        number_days = days_until_period_end - days_before_period

        # The amount to depreciate are computed by computing how much the asset should be depreciated at the end of the
        # period minus how much it is actually depreciated. It is done that way to avoid having the last move to take
        # every single small difference that could appear over the time with the classic computation method.
        if self.method == 'linear':
            if self.normalize_dates_to_jan_first:
                if total_lifetime_left and float_compare(total_lifetime_left, 0, 2) > 0:
                    if total_lifetime_left > 1:
                        annual_percent = self.model_id.standard_coefficient
                        if self.model_id.first_year_halving and residual_amount == residual_at_compute and not self.env.context.get(
                                'skip_halving'):
                            annual_percent = annual_percent / 2
                        if self.accounting_value:
                            total_depreciable = self.accounting_value
                        else:
                            total_depreciable = self.total_depreciable_value
                        computed_linear_amount = total_depreciable * (annual_percent / 100.0)
                    else:
                        computed_linear_amount = residual_amount
                    # computed_linear_amount = residual_amount - residual_at_compute * (1 - self._get_delta_days(start_recompute_date, period_end_date) / total_lifetime_left)
                else:
                    computed_linear_amount = self._get_linear_amount(days_before_period, days_until_period_end,
                                                                     self.total_depreciable_value)
            else:
                if total_lifetime_left and float_compare(total_lifetime_left, 0, 2) > 0:
                    computed_linear_amount = residual_amount - residual_at_compute * (
                            1 - self._get_delta_days(start_recompute_date, period_end_date) / total_lifetime_left)
                else:
                    computed_linear_amount = self._get_linear_amount(days_before_period, days_until_period_end,
                                                                     self.total_depreciable_value)
            amount = min(computed_linear_amount, residual_amount, key=abs)
        elif self.method == 'degressive':
            # Linear amount
            # We first calculate the total linear amount for the period left from the beginning of the year
            # to get the linear amount for the period in order to avoid big delta at the end of the period
            effective_start_date = max(start_yearly_period,
                                       self.paused_prorata_date) if start_yearly_period else self.paused_prorata_date
            days_left_from_beginning_of_year = self._get_delta_days(effective_start_date,
                                                                    period_start_date - relativedelta(
                                                                        days=1)) + days_left_to_depreciated
            expected_remaining_value_with_linear = residual_declining - residual_declining * self._get_delta_days(
                effective_start_date, period_end_date) / days_left_from_beginning_of_year
            linear_amount = residual_amount - expected_remaining_value_with_linear

            amount = self._get_max_between_linear_and_degressive(linear_amount, effective_start_date)
        elif self.method == 'degressive_then_linear':
            if not self.parent_id:
                linear_amount = self._get_linear_amount(days_before_period, days_until_period_end,
                                                        self.total_depreciable_value)
            else:
                # we want to know the amount before the reeval for the parent so the child can follow the same curve,
                # so it transitions from degressive to linear at the same moment
                parent_moves = self.parent_id.depreciation_move_ids.filtered(
                    lambda mv: mv.date <= self.prorata_date).sorted(key=lambda mv: (mv.date, mv.id))
                parent_cumulative_depreciation = parent_moves[
                    -1].asset_depreciated_value if parent_moves else self.parent_id.already_depreciated_amount_import
                parent_depreciable_value = parent_moves[
                    -1].asset_remaining_value if parent_moves else self.parent_id.total_depreciable_value
                if self.currency_id.is_zero(parent_depreciable_value):
                    linear_amount = self._get_linear_amount(days_before_period, days_until_period_end,
                                                            self.total_depreciable_value)
                else:
                    # To have the same curve as the parent, we need to have the equivalent amount before the reeval.
                    # The child's depreciable value corresponds to the amount that is left to depreciate for the parent.
                    # So, we use the proportion between them to compute the equivalent child's total to depreciate.
                    # We use it then with the duration of the parent to compute the depreciation amount
                    depreciable_value = self.total_depreciable_value * (
                            1 + parent_cumulative_depreciation / parent_depreciable_value)
                    linear_amount = self._get_linear_amount(days_before_period, days_until_period_end,
                                                            depreciable_value) * self.asset_lifetime_days / self.parent_id.asset_lifetime_days

            amount = self._get_max_between_linear_and_degressive(linear_amount)

        amount = max(amount, 0) if self.currency_id.compare_amounts(residual_amount, 0) > 0 else min(amount, 0)

        if abs(residual_amount) < abs(amount) or days_until_period_end >= self.asset_lifetime_days:
            # If the residual amount is less than the computed amount, we keep the residual amount
            # If total_days is greater or equals to asset lifetime days, it should mean that
            # the asset will finish in this period and the value for this period is equal to the residual amount.
            amount = residual_amount
        """Reset prorata date to old value"""
        self.paused_prorata_date = old_pro_rata_date
        return number_days, self.currency_id.round(amount)

    def _create_move_before_date(self, date):
        """Cancel all the moves after the given date and replace them by a new one.

        The new depreciation/move is depreciating the residual value.
        """
        all_move_dates_before_date = (self.depreciation_move_ids.filtered(
            lambda x:
            x.date <= date
            and not x.reversal_move_id
            and not x.reversed_entry_id
            and x.state == 'posted'
        ).sorted('date')).mapped('date')

        beginning_fiscal_year = self.company_id.compute_fiscalyear_dates(date).get(
            'date_from') if self.method != 'linear' else False
        first_fiscalyear_move = self.env['account.move']
        if all_move_dates_before_date:
            last_move_date_not_reversed = max(all_move_dates_before_date)
            # We don't know when begins the period that the move is supposed to cover
            # So, we use the earliest beginning of a move that comes after the last move not cancelled
            future_moves_beginning_date = self.depreciation_move_ids.filtered(
                lambda m: m.date > last_move_date_not_reversed and (
                        not m.reversal_move_id and not m.reversed_entry_id and m.state == 'posted'
                        or m.state == 'draft'
                )
            ).mapped('asset_depreciation_beginning_date')
            beginning_depreciation_date = min(
                future_moves_beginning_date) if future_moves_beginning_date else self.paused_prorata_date

            if self.method != 'linear':
                # In degressive and degressive_then_linear, we need to find the first move of the fiscal year that comes after the last move not cancelled
                # in order to correctly compute the moves just before and after the pause date
                first_moves = self.depreciation_move_ids.filtered(
                    lambda m: m.asset_depreciation_beginning_date >= beginning_fiscal_year and (
                            not m.reversal_move_id and not m.reversed_entry_id and m.state == 'posted'
                            or m.state == 'draft'
                    )
                ).sorted(lambda m: (m.asset_depreciation_beginning_date, m.id))
                first_fiscalyear_move = next(iter(first_moves), first_fiscalyear_move)
        else:
            beginning_depreciation_date = self.paused_prorata_date

        residual_declining = first_fiscalyear_move.asset_remaining_value + first_fiscalyear_move.depreciation_value
        self._cancel_future_moves(date)

        """DIGIDUU Custom condition(residual calculation)"""
        if not self.delete_residual_calculation:
            imported_amount = self.already_depreciated_amount_import if not all_move_dates_before_date else 0
            value_residual = self.value_residual + self.already_depreciated_amount_import if not all_move_dates_before_date else self.value_residual
            residual_declining = residual_declining or value_residual

            last_day_asset = self._get_last_day_asset()
            lifetime_left = self._get_delta_days(beginning_depreciation_date, last_day_asset)
            days_depreciated, amount = self._compute_board_amount(self.value_residual, beginning_depreciation_date,
                                                                  date, False, lifetime_left, residual_declining,
                                                                  beginning_fiscal_year, lifetime_left, value_residual,
                                                                  beginning_depreciation_date)

            if abs(imported_amount) <= abs(amount):
                amount -= imported_amount
            if not float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                if self.asset_type == 'sale':
                    amount *= -1
                new_line = self._insert_depreciation_line(amount, beginning_depreciation_date, date, days_depreciated)
                new_line._post()

    def action_asset_modify(self):
        """ OVERRIDE: add gain and loss accounts to the asset modify model.
        """
        res = super().action_asset_modify()
        gain_account_id = self.model_id.gain_account_id.id if self.model_id.gain_account_id else False
        loss_account_id = self.model_id.loss_account_id.id if self.model_id.loss_account_id else False
        self.env['asset.modify'].browse(res['res_id']).write(
            {'gain_account_id': gain_account_id, 'loss_account_id': loss_account_id})
        return res

    def _get_next_sequence_number(self):
        self.ensure_one()

        self.model_id.sequence_number += 1
        return self.model_id.sequence_number

    def validate(self):
        res = super().validate()
        self.ensure_one()

        # 1° case: child asset validation (no next sequence number)
        if self.model_id and self.model_id.prefix_code and self.is_account_asset_child and self.parent_account_asset_id and self.parent_account_asset_id.sequence_code:
            existing_children = self.search_count([
                ('parent_account_asset_id', '=', self.parent_account_asset_id.id),
                ('is_account_asset_child', '=', True),
                ('id', '!=', self.id),
            ])
            child_number = str(existing_children + 1).zfill(2)
            self.sequence_code = f"{self.parent_account_asset_id.sequence_code}/{child_number}"

        # 2° case: father asset validation(without connection to child asset)
        if self.model_id and self.model_id.prefix_code and not self.sequence_code:
            next_number = self._get_next_sequence_number()
            formatted_number = str(next_number).zfill(5)

            self.sequence_number = formatted_number
            self.sequence_code = f"{self.model_id.prefix_code}{formatted_number}"

        return res
