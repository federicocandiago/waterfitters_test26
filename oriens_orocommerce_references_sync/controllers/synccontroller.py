from odoo import http
from odoo.http import request

import re
import json
import datetime
import logging

update_hours_cycle = 40000
access_token = '7b2b6498-106d-4b63-a5bc-62f5b03837dc-2dda8785-9c8f-4060-bc46-ec550083217b'
_logger = logging.getLogger(__name__)


class SyncController(http.Controller):
    
    def _strip_tags(self, text): return re.sub(r'<[^>]+>', '', text or '')
    def _error(self, text): return json.dumps({'error': text})

    @http.route('/waterfitters-api/product_references', type = 'http', auth = 'public', methods = ['POST'], csrf = False)
    def product_references(self, **kwargs):

        raw_body = request.httprequest.data
        body_text = raw_body.decode('utf-8')

                
        _logger.warning(f'WATERFITTERS CONTROLLER RAW BODY: {raw_body}')
        _logger.warning(f'WATERFITTERS CONTROLLER REQUEST: {body_text}')

        try:
            body = json.loads(body_text)
            _logger.warning(f'WATERFITTERS CONTROLLER JSON: {body["token"]}')
            
            if 'token' not in body or body['token'] != access_token: return self._error('Token di accesso non valido')
        except Exception as e: 
            _logger.warning(f"Errore di accesso: {e}")
            return self._error('Errore di accesso')

        now = datetime.datetime.now()

        hours_delta = body.get('update_interval', False)

        try: hours_delta = float(hours_delta)
        except: hours_delta = False
        if not hours_delta: hours_delta = update_hours_cycle
        last_update = now - datetime.timedelta(hours = hours_delta)
        
        codici_env = request.env['x_codici_prodotto_clie'].sudo()

        ## TODO CTRL TOKEN
        codici_uids = codici_env.search([]).ids
        codici_ids = codici_env.search([('write_date', '>=', last_update)])
        codici_dict = [
            {
                'id': c.id, 
                'name': c.x_name, 
                'codice_prodotto_cliente': c.x_studio_codice_prodotto_cliente,
                'prodotto': c.x_studio_many2one_field_EZbJC.display_name if c.x_studio_many2one_field_EZbJC else False,
                'id_contatto': self._strip_tags(c.x_studio_notes)
            }
            for c in codici_ids if self._strip_tags(c.x_studio_notes)
        ] if codici_ids else []

        return json.dumps({
            'edited_references': codici_dict,
            'existing_references': codici_uids
        })

