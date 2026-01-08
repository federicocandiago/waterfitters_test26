# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, models
from odoo.tools.misc import formatLang

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('order_line.tax_id', 'order_line.price_unit', 'amount_total', 'amount_untaxed', 'currency_id')
    def _compute_tax_totals(self):

        res = super()._compute_tax_totals()

        for order in self:
            if order.name and order.name.startswith('OW'):
                currency = order.currency_id or order.company_id.currency_id
                totals = order.tax_totals

                if order.amount_untaxed and order.amount_total:
                    totals['amount_untaxed'] = currency.round(order.amount_untaxed)
                    totals['amount_total'] = currency.round(order.amount_total)

                    totals['formatted_amount_untaxed'] = formatLang(self.env, totals['amount_untaxed'], currency_obj=currency)
                    totals['formatted_amount_total'] = formatLang(self.env, totals['amount_total'], currency_obj=currency)

                    for groups in totals['groups_by_subtotal'].values():

                        if len(groups) == 1:
                            g = groups[0]

                            tax_amount = currency.round(totals['amount_total'] - totals['amount_untaxed'])
                            base_amount = totals['amount_untaxed']

                            g['tax_group_amount'] = tax_amount
                            g['tax_group_base_amount'] = base_amount

                            g['formatted_tax_group_amount'] = formatLang(self.env, tax_amount, currency_obj=currency)
                            g['formatted_tax_group_base_amount'] = formatLang(self.env, base_amount, currency_obj=currency)

                        for g in groups:
                            g['tax_group_amount'] = currency.round(g['tax_group_amount'])
                            g['tax_group_base_amount'] = currency.round(g['tax_group_base_amount'])

                            g['formatted_tax_group_amount'] = formatLang(self.env, g['tax_group_amount'], currency_obj=currency)
                            g['formatted_tax_group_base_amount'] = formatLang(self.env, g['tax_group_base_amount'], currency_obj=currency)

                    subtotals = totals.get('subtotals', [])
                    if len(subtotals) == 1:
                        subtotal = subtotals[0]
                        subtotal['amount'] = totals['amount_untaxed']
                        subtotal['formatted_amount'] = totals['formatted_amount_untaxed']

                    for subtotal in subtotals:
                        subtotal['amount'] = currency.round(subtotal['amount'])
                        subtotal['formatted_amount'] = formatLang(
                            self.env, subtotal['amount'], currency_obj=currency
                        )

                    order.tax_totals = totals

        return res
