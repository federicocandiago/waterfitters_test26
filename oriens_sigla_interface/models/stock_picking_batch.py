from odoo import models, fields
from suds.client import Client

import logging
_logger = logging.getLogger(__name__)

class StockPickingBatch(models.Model):
    _inherit = ["stock.picking.batch"]

    ### TEST ENV ###
    sigla_soap_url="http://185.191.104.234:8081/wsdl/IMONService"

    risposta_trasferimento_sigla = fields.Char('Risposta Trasferimento Sigla')

    def sigla_invia_record(self):
        for record in self:
            results = 'Non Elaborato'
            _logger.warning(f'Invio DDT a SIGLA (API GetImportaDDT). Id {record.id}')
            try:
                suds_client = Client(self.sigla_soap_url)
                if not suds_client:  _logger.warning(f'ERR: Impossibile inizializzare il client SOAP.')
                else:
                    suds_response = suds_client.service.GetImportaDDT(record.id)
                    _logger.warning(f'Risposta SIGLA (API GetImportaDDT). Id {record.id} - Res: {suds_response}')
                    results = str(suds_response)

            except Exception as e:
                _logger.warning(f'ERR: ECCEZIONE IN INTEGRAZIONE CON SIGLA: {e}')
                results = f'ECCEZIONE: {e}'

                exception_response = suds_client.service.GetErrori('BV' + str(record.id))
                odoo_exception_response = str(exception_response) if exception_response else 'Nessuna risposta'
                _logger.warning(f'ERR: LOG ERRORE DA SIGLA: {odoo_exception_response}')

            record.risposta_trasferimento_sigla = results
