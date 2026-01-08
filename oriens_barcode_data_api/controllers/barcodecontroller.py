from odoo import http
from odoo.http import request

import re
import json
import logging

_logger = logging.getLogger(__name__)

class BarcodeController(http.Controller):

    def is_integer(self, value):
        try: is_int = int(value)
        except Exception as e: is_int = False
        return is_int

    def _convert_in_float(self, value):
        raw_value = value.strip().replace(',', '.')
        match = re.search(r'[-+]?\d*\.?\d+', raw_value)
        return float(match.group()) if match else False
        
    @http.route('/barcode-api/is_cronometer_active', type = 'http', auth = 'user', methods = ['GET'], csrf = True)
    def is_cronometer_active(self, **kwargs):
        req_json = request.params
        
        if not 'record_id' in req_json or not self.is_integer(req_json['record_id']): 
            return self.return_error('Richiesta non corretta, parametri mancanti.')
            
        batch_id = request.env['stock.picking.batch'].browse(int(req_json['record_id']))
        
        if not batch_id.exists(): 
            return self.return_error(f"Record stock picking batch con ID {req_json['record_id']} non trovato.")
            
        return 'running' if batch_id.current_picking_start else 'stopped'

    
    @http.route('/barcode-api/set_cronometer', type = 'http', auth = 'user', methods = ['POST'], csrf = True)
    def set_cronometer(self, **kwargs):
        
        req_json = request.params
        if not req_json or 'state' not in req_json or 'record_id' not in req_json or not self.is_integer(req_json['record_id']): 
            return self.return_error('Richiesta non corretta, parametri mancanti.')
        
        state = req_json['state']
        batch_id = request.env['stock.picking.batch'].browse(int(req_json['record_id']))
        if not batch_id.exists(): return self.return_error('Richiesta non corretta, il record non esiste.')

        if str(state) == '0': batch_id.oriens_stop_picking()
        if str(state) == '1': batch_id.oriens_start_picking()
        
        return self.return_response({'record': batch_id.display_name})

    """
    @http.route('/barcode-api/set_product_location', type = 'http', auth = 'user', methods = ['GET'], csrf = True)
    def set_product_location(self, **kwargs):
        
        req_json = request.params
        if not req_json or 'name' not in req_json or 'location' not in req_json: 
            return self.return_error('Richiesta non corretta, parametri mancanti.')

        status = '0'
        product = request.env['product.product'].with_context(lang='it_IT').sudo().search([('name', '=', req_json['name'])], order='id desc', limit = 1)
        if not product: return self.return_error('Non è stato possibile rintracciare il prodotto')

        location_id = req_json['location']
        #location_id = request.env['stock.location'].with_context(lang='it_IT').sudo().search([('name', '=', req_json['location'])], order='id desc', limit = 1)

        if location_id:
            try:
                #product.location_id = location_id.id
                product.x_studio_ubicazione_magazzino_primaria = location_id
                status = '1'
            except Exception as e:
                _logger.warning(f"Impossibile associare la location {location_id.name} ({location_id.id}) al prodotto {product.name} ({product.id}): {e}")
        
        return self.return_response({'status': status})
    """


    @http.route('/barcode-api/set-pack-weight', type = 'http', auth = 'user', methods = ['POST'], csrf = True)
    def set_pack_weight(self, **kwargs):

        req_json = request.params
        if not req_json or 'name' not in req_json or 'weight' not in req_json: 
            return self.return_error('Richiesta non corretta, parametri mancanti.')
        
        weight = req_json['weight']
        raw_weight = self._convert_in_float(weight)
            
        package_name = req_json['name']
        package_id = request.env['stock.quant.package'].search([('name', '=', package_name)], order='id desc', limit = 1)
        if not package_id.exists(): return self.return_error('Richiesta non corretta, il record non esiste.')

        package_id.write({
          'shipping_weight': raw_weight,
          #'x_studio_peso_lordo': raw_weight
        })


        shipping_weight = '{:.2f}'.format(raw_weight)
        shipping_weight_str = f' - effettivo: {shipping_weight} {package_id.weight_uom_name or ""}'
        
        return self.return_response({'record': package_id.display_name, 'weight': shipping_weight_str})

    @http.route('/barcode-api/get-computed-pack-weight', type = 'http', auth = 'user', methods = ['GET'], csrf = True)
    def get_computed_pack_weight(self, **kwargs):
        
        req_json = request.params
        if not req_json or 'name' not in req_json or 'product_name' not in req_json or 'product_uom_qty' not in req_json: 
            return self.return_error('Richiesta non corretta, parametri mancanti.')
        
        package_name = req_json['name']
        package_id = request.env['stock.quant.package'].search([('name', '=', package_name)], order='id desc', limit = 1)
        if not package_id.exists(): return self.return_error('Richiesta non corretta, il record non esiste.')

        ## Peso effettivo ##
        shipping_weight_str = "{:.2f}".format(package_id.shipping_weight)
        actual_weight = f' - effettivo: {shipping_weight_str} {package_id.weight_uom_name or ""}' if package_id.shipping_weight else ''

        ## Peso calcolato ##
        weight = package_id._oriens_return_weight(req_json['product_name'], req_json['product_uom_qty'])

        ## Fallback peso ##
        if weight == 0:
            if 'product_code' in req_json and req_json['product_code']:
                product_id = request.env['product.product'].with_context(lang='it_IT').sudo().search([
                    ('default_code', '=', req_json['product_code'])
                ], limit = 1)
                
                if product_id and product_id.weight:
                    try:
                        quantity_float = float(req_json['product_uom_qty'])
                        weight = product_id.weight * quantity_float
                    except: weight = 0
                        
        weight_str = f'<span class="barcode_calc_weight">' + '{:.2f}'.format(weight) + '</span>'
        computed_weight = f'(Peso calcolato: {weight_str} {package_id.weight_uom_name or ""}<span class="actual_weight">{actual_weight}</span>)'

        return self.return_response({'weight': weight, 'computed_weight': computed_weight, 'id': package_id.id})

    
    @http.route('/barcode-api/get-product-data', type = 'http', auth = 'user', methods = ['GET'], csrf = True)
    def get_product_data(self, **kwargs):
        
        request_json = request.params
        if not request_json or 'name' not in request_json  or 'picking_name' not in request_json: 
            return self.return_error('La richiesta non è corretta, manca il parametro "name"')
        
        #Get Product
        product = request.env['product.product'].with_context(lang='it_IT').sudo().search([('name', '=', request_json['name'])], order='id desc', limit = 1)
        if not product: _logger.warning(f'Non è stato possibile rintracciare il prodotto {request_json["name"]}')

        #Get Stock Picking Batch
        note_picking = ''
        try: 
            picking_id = request.env['stock.picking'].with_context(lang='it_IT').sudo().search([('name', '=', request_json["picking_name"])], limit = 1)
            if picking_id: note_picking = picking_id.x_studio_note_interne
            
        except Exception as e:
            _logger.warning(f'Non è stato possibile effettuare il parsing del batch con ID {request_json["batch_id"]}: {e}')

        note_picking = str(note_picking).replace('False', '')
        if not note_picking.strip(): note_picking = '-'
        
        return self.return_response({
            'ubicazione_primaria': product.x_studio_ubicazione_magazzino_primaria if product and product.x_studio_ubicazione_magazzino_primaria else '',
            'ubicazione_secondaria': product.x_studio_ubicazione_magazzino_secondaria if product and product.x_studio_ubicazione_magazzino_secondaria else '',
            'posizione': product.x_studio_posizione.display_name if product and product.x_studio_posizione else '',
            'note_picking': str(note_picking).replace('False','')
        })

    @http.route('/barcode-api/get-product-description', type = 'http', auth = 'user', methods = ['GET'], csrf = True)
    def get_product_description(self, **kwargs):
        
        request_json = request.params
        if not request_json or 'name' not in request_json: 
            return self.return_error('La richiesta non è corretta, verificare i parametri utilizzati')
        
        #Get Picking Batch
        package_id = request.env['stock.picking'].with_context(lang='it_IT').sudo().search([('name', '=', request_json['name'])], limit = 1)
        if not package_id.exists(): _logger.warning(f'Non è stato possibile rintracciare il record stock.picking con nome {request_json["name"]}')

        return self.return_response({
            'descrizione': package_id.note or '',
        })
    
    @http.route('/barcode-api/set-product-description', type = 'http', auth = 'user', methods = ['POST'], csrf = True)
    def set_product_description(self, **kwargs):
        
        req_json = request.params
        if not req_json or 'name' not in req_json or 'descrizione' not in req_json: return self.return_error('Richiesta non corretta, parametri mancanti.')

        package_id = request.env['stock.picking'].with_context(lang='it_IT').sudo().search([('name', '=', req_json['name'])], limit = 1)
        if not package_id.exists(): _logger.warning(f'Non è stato possibile rintracciare il record stock.quant con nome {req_json["name"]}')
        package_id.write({'note': req_json['descrizione']})
        return self.return_response({'record': package_id.id})

    @http.route('/barcode-api/get-product-dimensions', type = 'http', auth = 'user', methods = ['GET'], csrf = True)
    def get_product_dimensions(self, **kwargs):
        
        request_json = request.params
        if not request_json or 'record_id' not in request_json: 
            return self.return_error('La richiesta non è corretta, verificare i parametri utilizzati')
        
        #Get Quant Package
        package_id = request.env['stock.quant.package'].with_context(lang='it_IT').sudo().search([('name', '=', request_json['record_id'])], limit = 1)
        if not package_id.exists(): _logger.warning(f'Non è stato possibile rintracciare il record stock.quant.package con nome {request_json["record_id"]}')

        return self.return_response({
            'altezza': package_id.x_studio_altezza,
            'larghezza': package_id.x_studio_larghezza,
            'profondita': package_id.x_studio_profondita
        })

    @http.route('/barcode-api/set-product-dimension', type = 'http', auth = 'user', methods = ['POST'], csrf = True)
    def set_product_dimension(self, **kwargs):
        
        req_json = request.params
        if not req_json or 'record_id' not in req_json: return self.return_error('Richiesta non corretta, parametri mancanti.')

        #Get Quant Package
        package_id = request.env['stock.quant.package'].with_context(lang='it_IT').sudo().search([('name', '=', req_json['record_id'])], limit = 1)
        if not package_id.exists(): _logger.warning(f'Non è stato possibile rintracciare il record stock.quant.package con ID {req_json["project_id"]}')

        if 'altezza' in req_json:
            float_altezza = self._convert_in_float(req_json['altezza'])
            if float_altezza != False: package_id.x_studio_altezza = float_altezza

        if 'larghezza' in req_json:
            float_larghezza = self._convert_in_float(req_json['larghezza'])
            if float_larghezza != False: package_id.x_studio_larghezza = float_larghezza

        if 'lunghezza' in req_json:
            float_lunghezza = self._convert_in_float(req_json['lunghezza'])
            if float_lunghezza != False: package_id.x_studio_profondita = float_lunghezza
            
        return self.return_response({'record': package_id.id})
    
    def return_error(self, error = ''):
        return http.Response(
            json.dumps({'error' : error}), 
            content_type='application/json', 
            status = 200
        )
        
    def return_response(self, response_json = {}):
        return http.Response(
            json.dumps(response_json), 
            content_type='application/json', 
            status = 200
        )
