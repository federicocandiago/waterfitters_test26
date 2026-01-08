# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import _, models, fields, api
from odoo.exceptions import UserError
from datetime import datetime

import requests
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Mondeo website privacy settings
    mondeo_web_privacy = fields.Boolean(string='Privacy')
    mondeo_web_consent = fields.Boolean(string='Consent')
    mondeo_web_form_en = fields.Boolean(string='Form - English')
    mondeo_web_form_it = fields.Boolean(string='Form - Italian')
    mondeo_web_form_de = fields.Boolean(string='Form - German')

    # Waterfitters e-commerce privacy settings
    wf_offers_and_promotions = fields.Boolean(string='Offers and promotions')
    wf_data_privacy = fields.Boolean(string='Data Privacy')
    wf_contract_clauses = fields.Boolean(string='Contract Clauses')
    wf_general_conditions = fields.Boolean(string='General Conditions')

    def _sync_iubenda_get_records(self, apikey, datetime_from, batch_size):

        datetime_zulu = False
        if datetime_from:
            try: datetime_zulu = datetime_from.strftime("%Y-%m-%dT%H:%M:%SZ")
            except: _logger.warning(f"_sync_iubenda_get_records: Cannot parse datetime {datetime_from}")

        if not datetime_zulu:
            datetime_from = datetime.now()
            datetime_from = datetime_from.replace(hour=0, minute=0, second=0, microsecond=0)
            datetime_zulu = datetime_from.strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"https://consent.iubenda.com/consent?from_time={datetime_zulu}&limit={batch_size}"
        headers = {"ApiKey": apikey, "Accept": "application/json"}
        response = requests.get(url, headers=headers)

        res_data = None
        if response.status_code != 200:
            _logger.error(f"_sync_iubenda_get_records: response code: {response.status_code} - {response.text}")
        else:
            try: res_data = response.json()
            except: _logger.error(f"_sync_iubenda_get_records: Cannot parse response {response.text}")

        return res_data


    def _create_or_write_partner(self, partner_vals, create_vals, res_email):
        odoo_partners = self.env['res.partner'].search([('email', '=', res_email), ('is_company', '=', False)])

        # Update existing partners
        if odoo_partners:
            odoo_partners.write(partner_vals)
            _logger.info(f"Partners {odoo_partners.ids} updated: {partner_vals}")

        # Create a new partner
        else:
            partner_vals.update(create_vals)
            odoo_partner = self.env['res.partner'].create(partner_vals)
            _logger.info(f"Partner {odoo_partner.id} created: {partner_vals}")


    def sync_iubenda_privacy_settings(self, datetime_from = None, batch_size=100):

        now_string = datetime.now().strftime('%d/%m/%Y')

        ConfigParameter = self.env['ir.config_parameter'].sudo()
        mondeo_apikey = ConfigParameter.get_param('iubenda_mondeo_web_apikey')
        wf_apikey = ConfigParameter.get_param('iubenda_wf_portal_apikey')

        # NOTE: it's not DRY because the structures of both elements are quite different

        # MONDEO WEBSITE SYNC #
        if mondeo_apikey:
            _logger.info('Syncing Mondeo Website records:')
            results = self._sync_iubenda_get_records(mondeo_apikey, datetime_from, batch_size)
            if results:
                for result in results:
                    res_preferences = result.get('preferences', {})
                    res_subject = result.get('subject', {})
                    res_email = res_subject.get('email')
                    if not res_subject or not res_email: continue

                    partner_vals = {
                        'mondeo_web_privacy': res_preferences.get('Privacy', False),
                        'mondeo_web_consent': res_preferences.get('Marketing', False),
                        'mondeo_web_form_en': res_preferences.get('Form Contatto ENG', False),
                        'mondeo_web_form_it': res_preferences.get('Form Contatto ITA', False),
                        'mondeo_web_form_de': res_preferences.get('Form Contatto DE', False)
                    }
                    create_vals = {
                        'name': res_subject.get('first_name', '') + ' ' + res_subject.get('last_name', ''),
                        'email': res_email,
                        'is_company': False,
                        'comment': _('Imported from Iubenda (%s) on date: %s') % (_('Mondeo website'), now_string)
                    }

                    self._create_or_write_partner(partner_vals, create_vals, res_email)

        # WATERFITTERS WEBSITE SYNC #

        if wf_apikey:
            _logger.info('Syncing Waterfitters records:')
            results = self._sync_iubenda_get_records(wf_apikey, datetime_from, batch_size)
            if results:
                for result in results:
                    res_preferences = result.get('preferences', {})
                    res_subject = result.get('subject', {})
                    res_email = res_subject.get('email')
                    if not res_subject or not res_email: continue

                    partner_vals = {
                        'wf_offers_and_promotions': res_preferences.get('offerte_e_promozioni', False),
                        'wf_data_privacy': res_preferences.get('privacy_dati', False),
                        'wf_contract_clauses': res_preferences.get('clausole_contrattuali', False),
                        'wf_general_conditions': res_preferences.get('condizioni_generali_di_vendita', False),
                    }
                    create_vals = {
                        'name': res_email,
                        'email': res_email,
                        'is_company': False,
                        'comment': _('Imported from Iubenda (%s) on date: %s') % (_('Waterfitters Portal'), now_string)
                    }

                    self._create_or_write_partner(partner_vals, create_vals, res_email)
