from odoo import models

from suds.client import Client

import logging
_logger = logging.getLogger(__name__)

sigla_soap_url="http://185.191.104.234:8081/wsdl/IMONService"

class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = "sale.order"

    def sigla_invia_record(self):
        for record in self:
            results = 'Non Elaborato'
            _logger.warning(f'Invio ordine a SIGLA (API GetImportaOrd). Id {record.id}')
            try:
                suds_client = Client(sigla_soap_url)
                if not suds_client:  _logger.warning(f'ERR: Impossibile inizializzare il client SOAP.')
                else:
                    suds_response = suds_client.service.GetImportaOrd(record.id)
                    _logger.warning(f'Risposta SIGLA (API GetImportaOrd). Id {record.id} - Res: {suds_response}')
                    results = str(suds_response)

            except Exception as e:
                _logger.warning(f'ERR: ECCEZIONE IN INTEGRAZIONE CON SIGLA: {e}')
                results = f'ECCEZIONE: {e}'

                exception_response = suds_client.service.GetErrori('OC' + str(record.id))
                odoo_exception_response = str(exception_response) if exception_response else 'Nessuna risposta'
                _logger.warning(f'ERR: LOG ERRORE DA SIGLA: {odoo_exception_response}')

            record['x_studio_risposta_trasferimento_sigla'] = results

