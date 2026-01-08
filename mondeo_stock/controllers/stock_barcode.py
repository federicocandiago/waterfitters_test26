# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from collections import defaultdict

from odoo import http, _
from odoo.http import request

class StockBarcodeController(http.Controller):

    def _get_allowed_company_ids(self):
        cids = request.httprequest.cookies.get('cids', str(request.env.user.company_id.id))
        return [int(cid) for cid in cids.split(',')]

    @http.route('/stock_barcode/get_barcode_data', type='json', auth='user')
    def get_barcode_data(self, model, res_id):
        if not res_id:
            target_record = request.env[model].with_context(allowed_company_ids=self._get_allowed_company_ids())
        else:
            target_record = request.env[model].browse(res_id).with_context(allowed_company_ids=self._get_allowed_company_ids())
        data = target_record._get_stock_barcode_data()
        data['records'].update(self._get_barcode_nomenclature())
        data['precision'] = request.env['decimal.precision'].precision_get('Product Unit of Measure')
        return {
            'data': data,
            'groups': self._get_groups_data(),
        }
