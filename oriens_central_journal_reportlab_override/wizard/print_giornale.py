from reportlab.platypus.paragraph import Paragraph

from odoo import _, api, fields, models

class WizardGiornaleReportlab(models.TransientModel):
    _inherit = "wizard.giornale.reportlab"

    def get_data_header_report_giornale(self):
        style_header = self.get_styles_report_giornale_line()["style_header"]
        style_header_number = self.get_styles_report_giornale_line()["style_header_number"]

        return [
            [
                Paragraph("Progr.", style_header),
                Paragraph("Data Reg.", style_header),
                Paragraph("Rif.", style_header),
                Paragraph("Protocollo", style_header),
                Paragraph("Conto", style_header),
                Paragraph("Descrizione movimento", style_header),
                Paragraph("Dare", style_header_number),
                Paragraph("Avere", style_header_number),
            ]
        ]
