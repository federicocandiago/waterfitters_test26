from odoo import http
from odoo.http import request

import re
import json
import logging

_logger = logging.getLogger(__name__)

token = "26ecadd4-2c8d-410c-a7b1-2b986e84dbcb-a5295eb3-4d77-4356-a459-d0d7283a878e"

class WebsiteController(http.Controller):
    @http.route('/website-mondeo-api/contact-2', type = 'http', auth = 'public', methods = ['POST'], csrf = False)
    def form_contatto(self, **kwargs):

        # FORM DATA
        request_json = request.params
        
        #_logger.warning(f'WEBSITE CONTROLLER REQUEST - FORM DATA: {request_json}')

        # Validazione formale dei dati
        form_received_keys = set(request_json.keys())
        form_keys_set = {
            "token", "your-name", "your-surname", "email", "your-country", "your-message",
        }

        if not form_keys_set.issubset(form_received_keys): 
            error_message = f"Campi mancanti: {list(form_keys_set - form_received_keys)}"
            return self._response({"error": error_message}, 400)
        
        # Validazione del token
        if request_json['token'] != token: return self._response({"error": "Token di validazione non corretto"}, 401)
        
        partner_name = f"{request_json.get('your-name', '')} {request_json.get('your-surname', '')}".strip()
        country_id = request.env['res.country'].sudo().search([('name', 'ilike', request_json.get('your-country', False))], limit = 1)

        try:
            partner_id = request.env['res.partner'].sudo().search(
                [('email', '=', request_json.get('email'))], 
                order = 'is_company, parent_id',
                limit = 1
            )

            if not partner_id: 
                partner_id = request.env['res.partner'].sudo().create({
                    'email': request_json.get('email'),
                    'name': request_json.get('company_name'),
                    'country_id': country_id.id if country_id else False,
                    'is_company': True
                })

            motivo = request_json.get('motivo')
            lead_id = request.env['crm.lead'].sudo().create({
                'name': "Richiesta da Sito Web Mondeo",
                'partner_id': partner_id.id,
                'description': request_json.get('your-message'),
                'partner_name': partner_name,
            })

        except Exception as e: 
            _logger.error(f'ERRORE ELABORAZIONE FORM: {e}')
            _logger.error(f'CHIAMATA INIZIALE.')
            return self._response({"error": "Errore nel salvataggio dati"}, 500)
