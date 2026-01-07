# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import _, models, fields, api
from odoo.exceptions import UserError
from datetime import datetime

import requests
import logging

_logger = logging.getLogger(__name__)

class WaterfittersShared(models.AbstractModel):
    _name = "waterfitters.shared"

    def _get_connection_data(self):
        config = self.env['ir.config_parameter'].sudo()
        conn_data = {
            'client_id': config.get_param('waterfitters_client_id'),
            'client_secret': config.get_param('waterfitters_client_secret'),
            'endpoints_url': config.get_param('waterfitters_endpoints_url'),
            'customers_batch_limit': config.get_param('waterfitters_customers_batch_limit', 50)
        }

        if not conn_data['client_id'] or not conn_data['client_secret'] or not conn_data['endpoints_url']:
            raise UserError(_('The connection data for the Waterfitters interface needs to be set in the Odoo Settings. Cannot proceed'))

        return conn_data

    def _wf_get_token(self):
        connection_data = self._get_connection_data()
        endpoints_url = connection_data['endpoints_url'].rstrip('/')

        url = f"{endpoints_url}/oauth2-token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": connection_data['client_id'],
            "client_secret": connection_data['client_secret']
        }
        headers = {"Content-Type": "application/json", "Accept": "application/vnd.api+json"}
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            return access_token
        else:
            _logger.warning(_(f"Login Error: {url} --- {response.status_code}, {response.text}"))
            return None

    def _wf_payload_request(self, model_name, payload, token, method = 'POST', url_parameters = None):
        connection_data = self._get_connection_data()
        base_url = str(connection_data['endpoints_url']).rstrip('/')

        response = None
        url = f"{base_url}/admin/api/{model_name}"
        if url_parameters: url = f"{url}/{url_parameters}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/vnd.api+json"}

        if method == 'POST': response = requests.post(url, json = payload, headers = headers)
        if method == 'PUT': response = requests.put(url, json = payload, headers = headers)
        if method == 'PATCH': response = requests.patch(url, json = payload, headers = headers)

        _logger.info(f"WF Request URL: {url}")
        _logger.info(f"WF Response Status: {response.status_code}")

        try: response_json = response.json()
        except: response_json = False

        return {'code': response.status_code, 'json': response_json}

    # TODO: to be left for future use
    def _wf_get_paginated(self, model_name, token, filter_str=False, sort_str=False, page_dimension = False):
        connection_data = self._get_connection_data()
        base_url = str(connection_data['endpoints_url']).rstrip('/')

        page_dimension = page_dimension or connection_data['customers_batch_limit']
        uri_sort_str = f"&sort={sort_str}" if sort_str else ''
        uri_filter_str = f"&filter{filter_str}" if filter_str else ''

        get_next_page = True
        next_page = 0
        incoming_data = []
        concatenator = '&' if '?' in model_name else '?'

        while get_next_page:

            next_page += 1
            url = f"{base_url}/admin/api/{model_name}{concatenator}page[number]={next_page}&page[size]={page_dimension}{uri_sort_str}{uri_filter_str}"
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.api+json"}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                res_data = response.json().get('data', [])

                # Loop through the paginated requests until there's no more content
                if not res_data: get_next_page = False
                else:
                    if len(res_data) < int(page_dimension or 0): get_next_page = False
                    for elem in res_data: incoming_data.append({ 'id': elem.get('id'), 'element': elem})

            else:
                _logger.error(f"Error fetching {model_name} - {url} ({response.status_code}) {response.text}")
                return None

        return incoming_data

    def _wf_get_element(self, model_name, model_id, token, post_model_str=False, join_model_string='/'):

        connection_data = self._get_connection_data()
        base_url = str(connection_data['endpoints_url']).rstrip('/')

        uri_post_model_str = f'/{post_model_str}' if post_model_str else ''
        url = f"{base_url}/admin/api/{model_name}{join_model_string}{model_id}{uri_post_model_str}"

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.api+json"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200: return response.json().get('data', [])

        else:
            _logger.error(f"Error fetching {model_name} - {url} ({response.status_code}) {response.text}")
            return None


    def _get_partner_country(self, add_elem):
        add_rels = add_elem['relationships'] if 'relationships' in add_elem else False
        add_country = add_rels['country'] if add_rels and 'country' in add_rels else False
        add_country_data = add_country['data'] if add_country and 'data' in add_country else False
        add_country_id = add_country_data['id'] if add_country_data and 'id' in add_country_data else False

        return add_country_id

    def get_relationship_id(self, token, relationships, relationship_name):
        relationship_data = relationships.get(relationship_name, {}).get('data', {})
        return int(relationship_data.get('id', 0)) if relationship_data else 0
