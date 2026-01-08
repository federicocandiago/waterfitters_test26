# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import markupsafe
import datetime
from odoo import models, _
from odoo.tools import config

import logging
_logger = logging.getLogger(__name__)

class AccountReport(models.Model):
    _inherit = 'account.report'
    #_name = 'account.report'

    
    def testfede(self):
        _logger.info('Prova')

    def export_to_pdf(self, options):
        _logger.warning('ORIENS: export_to_pdf invoked!!!!!!!!!')
        
        self.ensure_one()
        # As the assets are generated during the same transaction as the rendering of the
        # templates calling them, there is a scenario where the assets are unreachable: when
        # you make a request to read the assets while the transaction creating them is not done.
        # Indeed, when you make an asset request, the controller has to read the `ir.attachment`
        # table.
        # This scenario happens when you want to print a PDF report for the first time, as the
        # assets are not in cache and must be generated. To workaround this issue, we manually
        # commit the writes in the `ir.attachment` table. It is done thanks to a key in the context.
        if not config['test_enable']:
            self = self.with_context(commit_assetsbundle=True)

        print_mode_self = self.with_context(print_mode=True)
        print_options = print_mode_self._get_options(previous_options=options)

        # ORIENS FC START: Exception for report #

        oriens_content = self._filter_out_folded_children(print_mode_self._get_lines(print_options))
        
        # Get the year from the document, otherwise nope
        oriens_year = datetime.datetime.now().strftime('%Y')
        for element in reversed(oriens_content):
            if 'date_from' in element:
                value = element['date_from']
                if isinstance(value, str) and len(value) >= 4:
                    oriens_year = value[:4] 
                break 
        
        _logger.warning(f"!!!!!! Oriens Year: {oriens_year}")

        
        base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        rcontext = {
            'mode': 'print',
            'base_url': base_url,
            'company': self.env.company,
            'oriens_year': oriens_year
        }
        
            
        body_html = print_mode_self.get_html(print_options, oriens_content)
        body = self.env['ir.ui.view']._render_template(
            "account_reports.print_template",
            values=dict(rcontext, body_html=body_html),
        )
        
        # Alternate footer for given report
        if self.id and self.id in [16]:
           _logger.warning('TEMPLATE OVERRIDDEN')

        footer = self.env['ir.actions.report']._render_template("web.internal_layout", values=rcontext)
        footer = self.env['ir.actions.report']._render_template("web.minimal_layout", values=dict(rcontext, subst=True, body = markupsafe.Markup(footer.decode())))

        # ORIENS FC END: Exception for report #

        landscape = False
        if len(print_options['columns']) > 5 or self._context.get('force_landscape_printing'):
            landscape = True

        file_content = self.env['ir.actions.report']._run_wkhtmltopdf(
            [body],
            footer = footer.decode(),
            landscape = landscape,
            specific_paperformat_args = {
                'data-report-margin-top': 10,
                'data-report-header-spacing': 10,
                'data-report-margin-bottom': 15,
            }
        )

        return {
            'file_name': self.get_default_report_filename('pdf'),
            'file_content': file_content,
            'file_type': 'pdf',
        }

