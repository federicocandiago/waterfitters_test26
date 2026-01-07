# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, api, _, fields
from odoo.exceptions import UserError

import datetime
import logging

_logger = logging.getLogger(__name__)

class AssetsReport(models.AbstractModel):
    _name = 'report.mondeo_accounting.assets_report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        _logger.warning(f"input data: {data}")

        # Document-wide data
        company = self.env['res.company'].browse(data['company_id'][0]) if data.get('company_id') else self.env.company
        date_format = '%d/%m/%Y' if company.partner_id and company.partner_id.lang == 'it_IT' else '%Y-%m-%d'
        today_date_str = datetime.datetime.now().strftime(date_format)

        asset_ids = self.env['account.asset'].sudo().browse(data.get('asset_ids'))

        # Prepare categories dynamically
        categories_dict = {}

        for asset in asset_ids:
            model_id = asset.model_id
            model_uid = model_id.id if model_id else False

            # Create the categories if they don't exist
            if model_uid not in categories_dict:
                categories_dict[model_uid] = {
                    'id': model_uid,
                    'name': model_id.display_name if model_id else _('No Category'),
                    'type': model_id.journal_id.name if model_id.journal_id else '-',
                    'assets': []
                }

            # Add asset + its depreciation lines
            report_date_str = data.get('report_date')
            if report_date_str and len(report_date_str) == 10:
                max_date = datetime.datetime.strptime(report_date_str, '%Y-%m-%d').date()
                lines = asset.depreciation_move_ids.filtered(lambda l: l.date <= max_date)
            else:
                lines = asset.depreciation_move_ids

            halving = '✓' if asset.first_year_halving else 'x'

            categories_dict[model_uid]['assets'].append({
                'asset': asset,
                'ordinary_rate': asset.standard_coefficient,
                'first_year_halving': halving,
                'depreciation_lines': lines.sorted(key='date', reverse=True)
            })

        # Append the totals once the categories have been generated
        for category in categories_dict.values():

            tot_depreciation = 0.0
            tot_cumulative = 0.0
            tot_residual = 0.0
            tot_origin = 0.0

            for asset_data in category['assets']:
                asset = asset_data['asset']
                origin = asset.original_value
                tot_origin += origin

                for line in asset_data['depreciation_lines']:
                    tot_depreciation += line.depreciation_value
                    tot_cumulative += line.asset_depreciated_value

                if asset_data['depreciation_lines']:
                    most_recent_line = asset_data['depreciation_lines'][0]
                    tot_residual += most_recent_line.asset_remaining_value
                else:
                    tot_residual += origin

            perc = (tot_cumulative / tot_origin * 100) if tot_origin else 0.0

            category['totals'] = {
                'depreciation': tot_depreciation,
                'cumulative_depreciation': tot_cumulative,
                'residual_value': tot_residual,
                'perc_depreciated': round(perc, 2),
            }

        # Prepare report_data
        if data:
            report_data = {
                'company': company,
                'categories': list(categories_dict.values()),
                'today_date': today_date_str
            }
            _logger.warning(f"report_data: {report_data}")
            return report_data
        else:
            raise UserError(_('Unable to generate the report: no correct data has been passed.'))
