# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class DigiduuAssetsReportWizard(models.TransientModel):
    _name = 'digiduu.assets.report.wizard'

    report_date = fields.Date(string='Assets value up to date', required=True)
    company_id = fields.Many2one('res.company', required=True)
    asset_ids = fields.Many2many('account.asset')
    category_ids = fields.Many2many(
        'account.asset',
        string='Asset Category',
        relation='digiduu_wizard_asset_category_rel',
        column1='wizard_id',
        column2='asset_id',
        domain="[('model_id', '=', False)]"
    )

    @api.onchange('company_id', 'category_ids')
    def _compute_assets(self):

        for record in self:
            Asset = self.env['account.asset']

            # To select the assets, the company needs to be selected first: domain and assets are set to none if no company.
            domain = {'asset_ids': [('id', 'in', [])], 'category_ids': [('id', 'in', [])]}
            asset_ids = Asset

            if record.company_id:
                # Assets domain: filtered for company + no company, and then for category (if selected)
                category_ids = record.category_ids
                asset_domain = [('company_id', 'in', [False, record.company_id.id])] + (
                    [('model_id', '!=', False)] if not category_ids else [('model_id', 'in', category_ids.ids)]
                )

                asset_ids = Asset.search(asset_domain)
                domain['asset_ids'] = asset_domain

                # Category domain and selection: all the categories for that companies
                category_assets = Asset.search(
                    [('model_id', '!=', False), ('company_id', 'in', [False, record.company_id.id])])
                domain['category_ids'] = [('id', 'in', category_assets.ids)]

            record.asset_ids = asset_ids

    def print_digiduu_assets_report(self):
        datas = self.read()
        if not datas: raise UserError(_("Cannot generate the report. Please refresh the page and try again."))
        data = datas[0]

        res = self.env.ref('mondeo_accounting.digiduu_assets_report_action').report_action(self, data=data)
        return res
