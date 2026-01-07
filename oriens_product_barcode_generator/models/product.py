# -*- coding: utf-8 -*-
from odoo import models, fields
import datetime

import logging
_logger = logging.getLogger(__name__)

import barcode
from barcode.writer import SVGWriter

import segno

fallback_qrcode_string = 'https://www.mondeovalves.com/'

class ProductProduct(models.Model):
    _inherit = 'product.template'

    def getBarcode128(self):
        if not self.barcode: return ''

        barcode_options = {
            'module_width': 1.2,
            'module_height': 24,
            'font_size': 0,
            'write_text': False
        }

        barcode_class = barcode.get_barcode_class('code128')
        my_barcode = barcode_class(self.barcode, writer=SVGWriter())
        barcode_bytes = my_barcode.render(barcode_options)
        return barcode_bytes.decode("utf-8") if barcode_bytes else ''

    def getQrcodeString(self, qrcode_string = False):

        qrcode_string = qrcode_string or fallback_qrcode_string
        qr = segno.make(qrcode_string.ljust(120))
        svg_data = qr.svg_inline(scale = 2.2, border = 0)
        return svg_data.replace('<?xml version="1.0" encoding="utf-8"?>', '')

    def hexadecimalDatetime(self):
        datetime_integer = int(datetime.datetime.now().strftime('%Y%m%d'))
        datetime_hexadecimal = hex(datetime_integer)
        return str(datetime_hexadecimal)