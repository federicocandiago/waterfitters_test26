from odoo import http
from odoo.http import request

import json
import logging

_logger = logging.getLogger(__name__)

token = "e15417ea-6172-4efa-9e80-207da3c0d9a5-70058b08-67fc-4155-9d5d-fee745ba6c160"

contact_cause_map = {
    '13': '03_Assistenza ed aiuto',
    '14': '04_Apertura di un reclamo',
    '15': '05_Maggiori informazioni sulla gestione dei dati forniti',
    '16': '06_Richiesta affidamento operativo',
    '17': '07_Suggerimenti per migliorare',
    '19': '09_ Altra tipologia di richiesta', 
}

contact_method_map = {
    'oro.contactus.contactrequest.method.phone': 'phone',
    'oro.contactus.contactrequest.method.email': 'mail',
    'oro.contactus.contactrequest.method.both': 'both',
}

class WaterfittersController(http.Controller):
    
    def _response(self, res_json, res_code = 200):
        return request.make_response(
            json.dumps(res_json),
            headers = [('Content-Type', 'application/json')],
            status = res_code
        )
    
    def _create_attachment(self, element, model_name, record_uid):
        try:
            attachment_id = False if not element['file_name'] or not element['file_data'] else request.env['ir.attachment'].sudo().create({
                'name': element['file_name'],
                'datas': element['file_data'],
                'res_model': model_name,
                'res_id': record_uid,
                'type': 'binary',
            })

            return attachment_id.id if attachment_id else False
        
        except Exception as e:  
            _logger.error(f'ERRORE CREAZIONE ALLEGATO: {e}')
            return False

    @http.route('/waterfitters-api/contattaci', type = 'http', auth = 'public', methods = ['POST'], csrf = False)
    def form_contattaci(self, **kwargs):

        raw_body = request.httprequest.data
        body_text = raw_body.decode('utf-8')

        try: req_json = json.loads(body_text)
        except json.JSONDecodeError: req_json = []
        
        form_received_keys = set(req_json.keys())

        # Validazione formale dei dati
        form_keys_set = {
            "token", "motivo", "nome", "cognome", "company_name", "metodo_contatto", "telefono", "email", "order", "oggetto", "commento", "files",
        }

        if not form_keys_set.issubset(form_received_keys): 
            error_message = f"Campi mancanti: {list(form_keys_set - form_received_keys)}"
            return self._response({"error": error_message}, 400)
        
        # Validazione del token
        if req_json['token'] != token: return self._response({"error": "Token di validazione non corretto"}, 401)

        contact_cause = str(req_json['motivo'])
        contact_method = contact_method_map.get(req_json.get('metodo_contatto'), False)
        files = req_json.get('files')
        
        partner_name = f"{req_json.get('nome', '')} {req_json.get('cognome', '')}".strip()

        try:
            # Gestione partner - unificata 

            partner_id = request.env['res.partner'].sudo().search(
                [('email', '=', req_json.get('email'))], 
                order = 'is_company, parent_id',
                limit = 1
            )

            if not partner_id: 
                partner_company_id = request.env['res.partner'].sudo().create({
                    'email': req_json.get('email'),
                    'name': req_json.get('company_name'),
                    'is_company': True
                })
                                
                partner_id = request.env['res.partner'].sudo().create({
                    'email': req_json.get('email'),
                    'name': partner_name,
                    'is_company': False,
                    'parent_id': partner_company_id.id
                })

            # Gestione descrizione - unificata

            description = req_json.get('commento')
            order_value = req_json.get('order')
            if order_value: description = f'<p><strong>ORDINE {order_value}:</strong></p>' + description

            # Caso 1: Helpdesk
            if contact_cause in ['13', '14', '15', '16', '17', '19']:

                ticket_type_id = request.env['helpdesk.ticket.type'].sudo().with_context({'lang': 'it_IT'}).search(
                    [('name', '=', contact_cause_map.get(contact_cause, False))], limit = 1
                )

                ticket_id = request.env['helpdesk.ticket'].sudo().create({
                    'name': req_json.get('oggetto') or "Richiesta da Waterfitters",
                    'partner_id': partner_id.id,
                    'description': description,
                    'order_string': str(req_json.get('order', '')),
                    'partner_name': partner_name,
                    'partner_email': req_json.get('email'),
                    'partner_phone': req_json.get('telefono'),
                    'partner_name': req_json.get('company_name'),
                    'ticket_type_id': ticket_type_id.id if ticket_type_id else False,
                    'contact_method': contact_method
                })

                ticket_uid = ticket_id.id
                if ticket_uid and files:
                    for file in files: self._create_attachment(file, 'helpdesk.ticket', ticket_uid) 
                
                return self._response({'record': 'helpdesk.ticket', 'id': ticket_uid})

            # Caso 2: Lead
            else:
                motivo = req_json.get('motivo')
                lead_id = request.env['crm.lead'].sudo().create({
                    'name': req_json.get('oggetto') or "Richiesta da Waterfitters",
                    'partner_id': partner_id.id,
                    'description': description,
                    'order_string': str(req_json.get('order', '')),
                    'partner_name': partner_name,
                    'mobile': req_json.get('telefono'),
                    'contact_cause': str(motivo) if motivo else False,
                    'contact_method': contact_method
                })

                lead_uid = lead_id.id
                if lead_uid and files:
                    for file in files: self._create_attachment(file, 'crm.lead', lead_uid)
                
                return self._response({'record': 'crm.lead', 'id': lead_uid})

        except Exception as e: 
            _logger.error(f'ERRORE ELABORAZIONE FORM: {e}')
            _logger.error(f'CHIAMATA INIZIALE.')
            return self._response({"error": "Errore nel salvataggio dati"}, 500)
