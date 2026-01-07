from odoo import api, fields, models
from datetime import datetime

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def oriens_data_for_mrp_report(self):
        if not self or self.id == 0 : return False

        title = 'ODP OVERVIEW - ' + self.name 

        # Basic objects for the report
        moves = self.env['stock.move'].search([('x_studio_odp_padre', 'ilike', '%' + self.name + '%'), ('state', '!=', 'cancel')], order='create_date desc')
        group_ids_list = moves.mapped('group_id.id') if moves else []
        groups = self.env['procurement.group'].search([('id', 'in', group_ids_list)], order = 'create_date')
        
        group_data = {}
        move_data = {}

        if groups:
            for group in groups:
                
                # Group Data
                group_moves = moves.filtered(lambda m: m.group_id.id == group.id)
                main_moves = group_moves.filtered(lambda m: not m.raw_material_production_id)

                # Move Data (inserted directly in the relative dict)
                main_move = main_moves[0] if len(main_moves) else False

                if group_moves: 
                    for group_move in group_moves: 
                        move_data[group_move.id] = self._oriens_populate_move_data(group_move)

                        if main_move and group_move.id == main_move.id:
                            move_data[group_move.id]['is_main_move'] = True

                group_data[group.id] = {
                    'is_purchase': bool(self.env['purchase.order'].search([('group_id', '=', group.id)])),
                    'group_moves': group_moves,
                    'linked_move': False, 
                    'main_moves': main_moves,
                    'main_move': main_move,
                    'sub_group_moves': group_moves.filtered(lambda m: m.raw_material_production_id),
                    'concat_name': f"{main_move.product_id.display_name}_{main_move.product_qty}" if main_move else f'none_{group.id}'
                }

            
            for m_id, m_data in move_data.items():
                for g_id, g_data in group_data.items():
                    
                    #Associazione gruppi - Sottogruppi lato Move
                    if not m_data['is_main_move'] and m_data['product_id'] and g_data['main_move'] and g_data['main_move'].product_id:
                        if g_data['main_move'].product_id.id == m_data['product_id']:
                            if g_data['main_move'].product_qty == m_data['product_qty']:
                                move_data[m_id]['linked_group'] = g_id
                                group_data[g_id]['linked_move'] = True
                                
                    #Associazione gruppi - Righe
                    if g_data['concat_name'] == m_data['concat_name']:
                        hydrated_group = self.env['procurement.group'].browse(g_id)
                        if hydrated_group: move_data[m_id]['show_group_instead'] = g_id
                        if hydrated_group.mrp_production_ids: move_data[m_id]['hydrated_order'] = hydrated_group.mrp_production_ids[0]
                        
                                

        return {
            'title': title,
            'groups': groups,
            'group_data': group_data,
            'move_data': move_data,
            'moves': moves
        }
    
    def _oriens_populate_move_data(self, group_move):
        
        move_supplier_info = self.env['product.supplierinfo'].search([
            ('product_tmpl_id', '=', group_move.product_id.product_tmpl_id.id), 
            '|', 
                ('date_end', '=', False), 
                ('date_end', '<', str(datetime.now())
            )], limit = 1) if group_move.product_id else False
        
        document_orders = group_move.x_studio_documento_di_riferimento.split(',') if group_move.x_studio_documento_di_riferimento else False
        forecast_is_late = group_move.forecast_expected_date < group_move.date_deadline if (group_move.forecast_expected_date and group_move.date_deadline) else False
        forecast_will_be_fulfilled = group_move.forecast_availability - group_move.product_qty

        #Link Creation
        order_links = []
        if document_orders:
            for document_order in document_orders:

                # Caso ordine d'acquisto
                purchase_order = self.env['purchase.order'].search([('name', '=', document_order.strip())], limit = 1)
                if purchase_order: order_links.append({
                    'link_name': purchase_order.name,
                    'link_href': '/web#id=' + str(purchase_order.id) + '&menu_id=250&cids=1&action=371&model=purchase.order&view_type=form'
                })
                    
                # Caso Ordine di produzione
                production_order = self.env['mrp.production'].search([('name', '=', document_order.strip())], limit = 1)
                if production_order: order_links.append({
                    'link_name': production_order.name,
                    'link_href': '/web#id=' + str(production_order.id) + '&cids=1&menu_id=323&action=497&model=mrp.production&view_type=form'
                })

        #Data for line
        quantity = str(group_move.product_uom_qty) + ('  ' + group_move.product_uom.with_context(lang='IT').name if group_move.product_uom else '').replace('Units', 'Unità')
        supplier_name = move_supplier_info.display_name if move_supplier_info else '-'
        delay = str(move_supplier_info.delay) + ' gg.' if move_supplier_info and move_supplier_info.delay else '0'

        return {
            'move_supplier_info': move_supplier_info,
            'document_orders' : document_orders,
            'forecast_is_late': forecast_is_late,
            'forecast_will_be_fulfilled' : forecast_will_be_fulfilled,
            'order_links': order_links,
            'quantity': quantity,
            'supplier_name': supplier_name,
            'delay': delay,
            'product_id': group_move.product_id.id if group_move.product_id else False,
            'product_qty': group_move.product_qty,
            'is_main_move': False,
            'linked_group': False,
            'concat_name': f"{group_move.product_id.display_name}_{group_move.product_qty}",
            'show_group_instead': False,
            'hydrated_order': False
        }
