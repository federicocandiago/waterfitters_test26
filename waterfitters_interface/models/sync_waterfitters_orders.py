# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import _, models
import requests
import datetime
import json

import logging
_logger = logging.getLogger(__name__)

# Mapping metodi di pagamento #
payment_methods_map = {
    'payment_term_1': 'customer_payment_term',
    'custom_payment_4': 'CO06',
    'oro_paypal_express_6': 'CACR',
    'stripe_payment_11_apple_google_pay': 'CACR',
    'stripe_payment_11': 'CACR'
}

## Mapping metodi di spedizone #
#shipping_methods_map = {
#    'order_amount_shipping_3': {'shipping_method': 'Vettore', 'incoterm': '011'},
#    'flat_rate_7': {'shipping_method': 'Destinatario', 'incoterm': '012'},
#    'flat_rate_10': {'shipping_method': 'Destinatario', 'incoterm': '012'}
#}

class SyncWaterfitters(models.Model):
    _name = "sync.waterfitters"
    _inherit = ["waterfitters.shared"]

    # Paese indirizzo di spedizione
    def _get_partner_country(self, add_elem):
        add_rels = add_elem['relationships'] if 'relationships' in add_elem else False
        add_country = add_rels['country'] if add_rels and 'country' in add_rels else False
        add_country_data = add_country['data'] if add_country and 'data' in add_country else False
        add_country_id = add_country_data['id'] if add_country_data and 'id' in add_country_data else False

        return add_country_id

    ### PARSE DATE HELPER ###
    def _parse_date(self, date_str):
        if not date_str: return False
        date_str = str(date_str)
        if len(date_str) > 10: date_str = date_str[0:10]
        try:
            parsed_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            parsed_date = False
        return parsed_date

    ### GENERIC FETCH FUNCTION - MULTI GET ###
    def _fetch_paginated_data(self, model_uri, start_date_str=False, sort_str=False):

        token = self._wf_get_token()
        if not token:
            _logger.error(_('Unable to obtain a token - Cannot proceed'))
            return None

        connection_data = self._get_connection_data()
        base_url = str(connection_data.get('endpoints_url', '')).rstrip('/')
        page_dimension_setting = connection_data.get('customers_batch_limit', '')
        page_dimension = int(page_dimension_setting) if page_dimension_setting.strip().isdigit() else 50

        uri_sort_str = f"&sort={sort_str}" if sort_str else ''

        # Gestione della data di inizio: se non definita in start_date, quella attuale
        if start_date_str and 'T' in start_date_str and 'Z' in start_date_str:

            iso_start_date_str = start_date_str
        else:
            start_date = False
            if start_date_str:
                try:
                    start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
                except:
                    _logger.warning(f"Sync Waterfitters - Formato data non valido: {start_date_str}")
            iso_start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ") if start_date else False

        # DOVREBBE ESSERE updatedAt MA ANCHE SE IN SPECIFICHE NON E' PRESENTE NEI FILTRI DELLE API DI OROCOMMERCE **TODO**
        date_uri = f"&filter[createdAt][gte]={iso_start_date_str}" if iso_start_date_str else ''

        get_next_page = True
        next_page = 0
        incoming_data = []
        concatenator_char = '&' if '?' in model_uri else '?'

        while get_next_page:
            next_page += 1
            url = f"{base_url}/admin/api/{model_uri}{concatenator_char}page[number]={next_page}&page[size]={page_dimension}{uri_sort_str}{date_uri}"

            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.api+json"
            }

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                response_json = response.json()
                response_data = response_json.get('data', [])

                # Pagination: as long as there are future results it will iterate the next page, otherwise it will exit
                if not response_data:
                    get_next_page = False
                else:
                    if len(response_data) < page_dimension:
                        get_next_page = False

                    for response_element in response_data:
                        incoming_data.append({
                            'id': response_element.get('id'),
                            'attributes': response_element.get('attributes')
                        })

            else:
                _logger.warning(
                    f"Sync Waterfitters - Error fetching {model_uri}: {url} --- {response.status_code}, {response.text}")
                return None

        return incoming_data

    ### GENERIC FETCH FUNCTION - SINGLE GET ###
    def _fetch_element(self, model_name, model_id, post_model_str=False, join_model_string='/', return_attr='data'):

        token = self._wf_get_token()
        if not token:
            _logger.error(_('Unable to obtain a token - Cannot proceed'))
            return None

        connection_data = self._get_connection_data()
        base_url = str(connection_data['endpoints_url']).rstrip('/')

        uri_post_model_str = f'/{post_model_str}' if post_model_str else ''
        url = f"{base_url}/admin/api/{model_name}{join_model_string}{model_id}{uri_post_model_str}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.api+json"
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            response_json = response.json()
            response_data = response_json.get(return_attr, [])
            return response_data

        else:
            _logger.warning(
                f"Sync Waterfitters - Error fetching {model_name}: {url} --- {response.status_code}, {response.text}")
            return None

    ### ORDER METHOD - CALLED FOR EACH ELEMENT, LOGIG INSIDE ###

    def order(self, token, order_id=False):

        Partner = self.env['res.partner'].sudo()
        now = datetime.datetime.now()
        today = datetime.date.today()

        order_elem = self._fetch_element("orders", f'{order_id}')

        # Order retrieval
        order_attrs = order_elem['attributes'] if order_elem and 'attributes' in order_elem else None
        if not order_attrs:
            _logger.warning(f"Attributo 'attributes' non presente per il record: {order_elem}")
            return

        # Check if the order is too recent - if it is less than 30 mins old, skip it
        order_created_at_str = order_attrs.get('createdAt')
        if order_created_at_str:
            try:
                order_created_at = datetime.datetime.strptime(order_created_at_str, "%Y-%m-%dT%H:%M:%SZ")
                # Compute the difference
                order_time_diff = now - order_created_at

                # Check if the order is older than 30 minutes
                if order_time_diff < datetime.timedelta(minutes=30):
                    _logger.info("The order is too recent. Skipping...")
                    return

            except Exception as e:
                _logger.info(f"Unable to verify the order createdAt attribute: {e}. Ignoring it")

        _logger.warning(f"data: {order_elem}")

        order_rel = order_elem['relationships'] if 'relationships' in order_elem else []

        ### MAIN / BILLING PARTNER RETRIEVAL - START ###

        partner_id = False
        order_included = self._fetch_element("orders", f'{order_id}?include=customer', False, '/', 'included')
        if order_included:
            partner_erp_id = order_included[0].get('attributes', {}).get('erp_id')

            if partner_erp_id:
                partner_id = Partner.search([
                    ('is_company', '=', True), ('x_studio_codice_soggetto', '=', partner_erp_id)
                ], limit=1)

        # If no partner is found, we'll cycle over and display just an alert.
        if not partner_id:
            _logger.error(
                f"Couldn't find the customer in Odoo matching by erp_id. Skipping Waterfitters order.")
            return

        # Set partner as customer if former prospect
        if partner_id.category_id.ids == [12]: partner_id.category_id = [1]

        ### MAIN / BILLING PARTNER RETRIEVAL - END ###

        ### PAYMENT METHODS - START ###

        # Recupero Metodo di pagamento
        PaymentTerm = self.env['account.payment.term'].sudo().with_context({'lang': 'it_IT'})
        payment_method_id = False

        payment_elems = self._fetch_element(
            "paymenttransactions",
            f"filter[entityClass]=Oro\Bundle\OrderBundle\Entity\Order&filter[entityIdentifier]={order_id}&page[number]=1&page[size]=10&sort=-createdAt",
            False,
            "?"
        )

        _logger.warning("**** ORDER PAYMENT ELEM ****")
        _logger.warning(f"{payment_elems}")
        _logger.warning("**** ORDER PAYMENT ELEM ****")

        is_customer_payment = False
        if len(payment_elems) and 'attributes' in payment_elems[0]:
            payment_attrs = payment_elems[0]['attributes']

            if 'paymentMethod' in payment_attrs and 'action' in payment_attrs and 'successful' in payment_attrs:

                if payment_attrs['paymentMethod'] in payment_methods_map:
                    payment_methods_str = payment_methods_map[payment_attrs['paymentMethod']]

                    if payment_methods_str == 'customer_payment_method':
                        payment_method_id = partner_id.with_context({'lang': 'it_IT'}).property_payment_method_id
                        is_customer_payment = True

                    else:
                        payment_method_id = PaymentTerm.search([('x_studio_codice', '=', payment_methods_str)], limit=1)

        # Fallback on credit card if no payment method set
        if not payment_method_id: payment_method_id = PaymentTerm.search([('x_studio_codice', '=', 'CACR')], limit=1)

        # Payment: if the customer-defined method is selected, let if be registered unless the method is CACR
        if is_customer_payment and payment_method_id and payment_method_id.x_studio_codice != 'CACR':
            payment_notes = _("Payment set as for the payment method.")

        # Payment: if the order has been made via credit card, check it's been paid.
        elif payment_method_id and payment_method_id.x_studio_codice == 'CACR':
            if payment_attrs['action'] == 'capture' and payment_attrs['successful']:
                payment_notes = _("Paid on purchase with Credit Card.")
            else:
                _logger.warning("The current order has been set but not paid for. Skipping...")
                return

        # Payment: residual case, let it go through
        else:
            payment_notes = _("Payment terms as specified by the user.")

        ### PAYMENT METHODS - END  ###

        ### SHIPPING PARTNER RETRIEVAL - START ###
        shipping_partner_id = False

        shipping_add_data = order_rel['shippingAddress']['data'] \
            if 'shippingAddress' in order_rel and 'data' in order_rel['shippingAddress'] \
            else False

        if shipping_add_data and 'type' in shipping_add_data and shipping_add_data['type'] == 'orderaddresses':
            shipping_add_id = shipping_add_data['id']

            shipping_order_elem = self._fetch_element("orderaddresses", shipping_add_id)

            _logger.warning(f"orderaddresses id: {shipping_add_id} - shipping_order_elem: {shipping_order_elem}")

            # Shipping orderaddress retrieval
            shipping_order_rel = shipping_order_elem[
                'relationships'] if shipping_order_elem and 'relationships' in shipping_order_elem else None
            if shipping_order_rel and 'customerAddress' in shipping_order_rel and 'data' in shipping_order_rel[
                'customerAddress']:
                if 'id' in shipping_order_rel['customerAddress']['data']:
                    try:
                        shipping_customer_add_id = int(shipping_order_rel['customerAddress']['data']['id'])
                    except:
                        shipping_customer_add_id = False

                    shipping_partner_id = Partner.search([
                        ('type', '=', 'delivery'), ('waterfitters_id', '=', shipping_customer_add_id)
                    ], limit=1)

            if not shipping_partner_id:
                _logger.warning(f'*********** TODO: importare lo shipping partner id! ***********')

        if shipping_partner_id: _logger.info(
            f'shipping_partner_id: {shipping_partner_id.id} - {shipping_partner_id.display_name}')

        ### SHIPPING PARTNER RETRIEVAL - END ###

        order_create_date = order_attrs['createdAt'][0:10] if order_attrs['createdAt'] else now.strftime('%Y-%m-%d')
        order_elem_id = order_elem['id']
        order_elem_year = order_create_date[2:4] if order_attrs['createdAt'] else now.strftime('%y')
        order_name = 'OW' + order_elem_year + '/' + order_elem_id.zfill(5)
        codice_sigla = order_attrs['erp_id'] if order_attrs['erp_id'] and order_attrs['is_erp_exported'] else False
        odoo_order_id = self.env['sale.order'].search([('name', '=', order_name)], limit=1)

        # Se l'ordine non esiste, lo creo
        if not odoo_order_id:

            # Crea riferimento cliente #
            client_order_ref = f"WF {order_elem_id}"
            if order_attrs['poNumber']: client_order_ref += f" ({order_attrs['poNumber']})"

            # Gestione metodo di spedizione e termini di resa #
            order_shipping_method = order_attrs['shippingMethod']
            shipping_method = False
            incoterms_id = False

            #if order_shipping_method and order_shipping_method in shipping_methods_map:
            #    shipping_method = shipping_methods_map[order_shipping_method]['shipping_method']
            #    incoterm_code = shipping_methods_map[order_shipping_method]['incoterm']
            #    incoterms = self.env['account.incoterms'].search([('code', '=', incoterm_code)], limit=1)
            #    if incoterms: incoterms_id = incoterms.id

            # Define Wf Shipping method
            shipping_method_rec = self.env['wf.shippingmethod'].search([('name', '=', order_shipping_method)], limit=1)
            if shipping_method_rec:
                shipping_method = shipping_method_rec.method

                # Define Incoterm Odoo id
                incoterm_code = shipping_method_rec.incoterm
                incoterms_id  = self.env['account.incoterms'].search([('code', '=', incoterm_code)], limit=1)

            # Gestione data richiesta #
            ship_until = self._parse_date(order_attrs.get("shipUntil"))
            if not ship_until: ship_until = self._parse_date(order_attrs.get("createdAt"))

            # Calcolo extra sconto #
            try:
                net_subtotal = float(order_attrs['subtotalValue']) if order_attrs['subtotalValue'] else False
            except:
                net_subtotal = False

            try:
                disc_subtotal = float(order_attrs['subtotalWithDiscounts']) if order_attrs[
                    'subtotalWithDiscounts'] else False
            except:
                disc_subtotal = False

            extra_discount_percent = 0
            if net_subtotal and disc_subtotal:
                extra_discount_percent = (net_subtotal - disc_subtotal) / net_subtotal

            pricelist = partner_id.property_product_pricelist.id if partner_id and partner_id.property_product_pricelist else 10184
            internal_note = order_attrs['customerNotes'] or ''
            if payment_notes: internal_note += f'\n\n{payment_notes}'

            odoo_order_id = self.env['sale.order'].create({
                'partner_id': partner_id.id,
                'partner_shipping_id': shipping_partner_id.id if shipping_partner_id else partner_id.id,
                'client_order_ref': client_order_ref,
                'name': order_name,
                'internal_note': internal_note,
                'origin': f"Waterfitters id: {order_elem_id} - {order_attrs['erp_id']}",
                'x_studio_trasferito_in_sigla': order_attrs['is_erp_exported'],
                'x_studio_data_invio_a_sigla': now if order_attrs['is_erp_exported'] else False,
                'x_studio_codice_sigla': codice_sigla,
                'company_id': 1,  # Hardcoded su Mondeo
                'tag_ids': [9],  # Hardcoded - Waterftters
                'sale_order_template_id': 2,  # Hardcoded
                'incoterm': incoterms_id.id if incoterms_id else False,
                'x_studio_data_riferimento_cliente': order_create_date,
                'x_studio_percentuale_sconto_di_testata': extra_discount_percent,
                'x_studio_modalit_di_spedizione': shipping_method,
                'x_studio_trasporto_a_cura_di': shipping_method,
                'x_studio_data_richiesta': ship_until,
                'payment_term_id': payment_method_id.id if payment_method_id else False,
                'pricelist_id': pricelist
            })

            self.env.cr.commit()
            _logger.warning(f"ORDER ELEM: {order_elem['id']} - ODOO ID: {odoo_order_id.id}")

            # Recupero righe ordine
            order_lines_data = order_rel['lineItems']['data'] \
                if odoo_order_id and 'customer' in order_rel and 'data' in order_rel['lineItems'] \
                else False

            # Shipping dates
            planned_dates_list = []
            try:
                order_create_date_dt = datetime.datetime.strptime(order_create_date, '%Y-%m-%d')
            except Exception as e:
                _logger.warning(f"Cannot parse the order_create string {order_create_date}, skipping..")

            lines_total_to_be_rounded = 0.0

            # Calculate the shipping costs for the order
            try:
                shipping_price = order_attrs[
                    'estimatedShippingCostAmount'] if 'estimatedShippingCostAmount' in order_attrs else False
                shipping_price = float(shipping_price)
            except:
                shipping_price = 0

            if order_lines_data:
                order_lines_dict = self._fetch_paginated_data(f"orderlineitems?filter[order]={order_elem_id}")
                if order_lines_dict:

                    total_lines_gross_amount = 0.0

                    for order_line_dict in order_lines_dict:

                        order_line_id = order_line_dict.get('id', '0')

                        order_line_attrs = order_line_dict[
                            'attributes'] if order_line_dict and 'attributes' in order_line_dict else False

                        if 'productSku' in order_line_attrs and 'productName' in order_line_attrs:

                            order_line_product_id = self.env['product.product'].search(
                                [('default_code', '=', order_line_attrs['productSku'])], limit=1)

                            if not order_line_product_id:
                                _logger.warning(
                                    f"Prodotto non trovato: {order_line_attrs['productSku']} - Impossibile salvare la riga ordine.")
                            else:

                                # Gestione valuta #
                                currency_id = self.env['res.currency'].search(
                                    [('name', '=', order_line_attrs['currency'])], limit=1)
                                if not currency_id: currency_id = self.env['res.currency'].search(
                                    [('id', '=', 1)],
                                    limit=1)

                                # Gestione prezzo #
                                try:
                                    price = float(order_line_attrs['value']) if order_line_attrs['value'] else 0.0
                                except:
                                    price = 0.0

                                line_quantity = float(order_line_attrs['quantity'])

                                # Creazione riga ordine #
                                odoo_order_line_id = self.env['sale.order.line'].create({
                                    'order_id': odoo_order_id.id,
                                    'product_id': order_line_product_id.id,
                                    'product_uom_qty': line_quantity,
                                    'product_uom': 1,
                                    'price_unit': price,
                                    'currency_id': currency_id.id,
                                    'x_studio_data_richiesta': ship_until,
                                    'wf_order_line_item_id': order_line_id,
                                    'discount': 0,
                                    'name': f"[{order_line_attrs['productSku']}] {order_line_attrs['productName']}",
                                })

                                # Gestione prezzi per confezione
                                if 'productUnitCode' in order_line_attrs and order_line_attrs[
                                    'productUnitCode'] == 'pack':
                                    total_line_quantity = line_quantity
                                    pz_x_conf = 1.0
                                    if odoo_order_line_id and odoo_order_line_id.x_studio_pzxconf:
                                        try:
                                            pz_x_conf = float(odoo_order_line_id.x_studio_pzxconf)
                                            total_line_quantity = line_quantity * pz_x_conf
                                        except Exception as e:
                                            _logger.warning(
                                                f'Unable to parse x_studio_pzxconf on order line {odoo_order_line_id.id}: {e}')

                                    odoo_order_line_id.write({
                                        'product_uom_qty': total_line_quantity,
                                        'price_unit': (price / pz_x_conf),
                                        'discount': 0,
                                        'price_subtotal': price * line_quantity
                                    })

                                lines_total_to_be_rounded += price * line_quantity

                                # Gestione lead time - come in azione server, verifica la data del product.template collegato alla riga d'ordine

                                line_tmpl_id = order_line_product_id.product_tmpl_id
                                internal_location_uid = 8

                                if line_tmpl_id:
                                    available_qty = sum(
                                        q.available_quantity
                                        for q in self.env['stock.quant'].search([
                                            ('product_id', '=', odoo_order_line_id.product_id.id)
                                        ])
                                        if
                                        q.location_id.id == internal_location_uid or q.location_id.location_id.id == internal_location_uid
                                    )

                                    if available_qty >= odoo_order_line_id.product_uom_qty:
                                        cutoff = now.replace(hour=11, minute=0, second=0, microsecond=0)
                                        base_days = 3 if now > cutoff else 2

                                    else:
                                        base_days = line_tmpl_id.sale_delay

                                    def add_business_days(start_date, days):
                                        dt = start_date + datetime.timedelta(days=days)
                                        if dt.weekday() == 5:
                                            dt += datetime.timedelta(days=2)  # Sabato
                                        elif dt.weekday() == 6:
                                            dt += datetime.timedelta(days=1)  # Domenica
                                        return dt

                                    planned_date = add_business_days(now, base_days)
                                    planned_dates_list.append(planned_date)

                                self.env.cr.commit()
                                total_lines_gross_amount += price * line_quantity

                                _logger.warning(
                                    f'ORDER LINE SINGOLA: {order_line_dict} - {odoo_order_line_id.id}')

                    ### Calcolo riga di spese trasporto ###

                    if shipping_price and shipping_price > 0:
                        odoo_shipping_line_id = self.env['sale.order.line'].create({
                            'order_id': odoo_order_id.id,
                            'name': _('TRANSPORTATION'),
                            'product_id': 963,
                            'product_uom': 1,
                            'price_unit': shipping_price,
                            'product_uom_qty': 1,
                            'sequence': 500,
                            'x_studio_data_richiesta': ship_until,  # TODO: Studio field, to be reviewed
                        })

                        lines_total_to_be_rounded += shipping_price

                        self.env.cr.commit()

                    ### Calcolo riga residua di aggiornamento prezzo (Sconto!) ###

                    # Fallback in case it's not working
                    discounted_subtotal = float(order_attrs['subtotalValue'])

                    try:
                        discounted_subtotal = float(order_attrs['subtotalWithDiscounts'])
                    except Exception as e:
                        # discounted_subtotal = total_lines_gross_amount
                        _logger.warning(f"Couln't calculate discounted_subtotal for row: {e}")

                    if total_lines_gross_amount != discounted_subtotal:
                        discount_amount = discounted_subtotal - total_lines_gross_amount

                        odoo_order_line_id = self.env['sale.order.line'].create({
                            'order_id': odoo_order_id.id,
                            'price_unit': discount_amount,
                            'name': _('EXTRA DISCOUNT'),
                            'product_id': 965,
                            'product_uom': 1,
                            'product_uom_qty': 1,
                            'sequence': 500,
                            'x_studio_data_richiesta': ship_until,  # TODO: Studio field, to be reviewed
                            # 'tax_id':False
                        })

                        lines_total_to_be_rounded += discount_amount

                        self.env.cr.commit()

            ### ROUNDING LINE - START ###
            substotal_with_discounts = order_attrs.get("subtotalWithDiscounts", 0)

            try:
                substotal_with_discounts = round(float(substotal_with_discounts), 2)
                wf_subtotal_value = round(substotal_with_discounts + shipping_price, 2)
                lines_total_to_be_rounded = round(lines_total_to_be_rounded, 2)

                if substotal_with_discounts:
                    diff_amount = wf_subtotal_value - lines_total_to_be_rounded

                    # Solo se la differenza è significativa
                    if abs(diff_amount) >= 0.005:
                        self.env['sale.order.line'].create({
                            'order_id': odoo_order_id.id,
                            'product_id': 965,
                            'product_uom': 1,
                            'product_uom_qty': 1,
                            'price_unit': diff_amount,
                            'name': _('ROUNDING'),
                            'sequence': 500,
                            'x_studio_data_richiesta': ship_until,  # TODO: Studio field, to be reviewed
                        })
                        self.env.cr.commit()

            except Exception as e:
                _logger.error(f'Could not verify the totals for order {odoo_order_id.id}: {e}, values might be unbalanced')

            ### ROUNDING LINE - STOP ###

            ### SET THE SHIPPING DATE FOR EACH LINE - START ###
            latest_date = max(planned_dates_list) if planned_dates_list else None
            if latest_date: self.env['sale.order.line'].search([('order_id', '=', odoo_order_id.id)]).write({
                'x_studio_data_spedizione_confermata': latest_date.strftime('%Y-%m-%d')
            })

            # Rounding the grand total
            order_total_value = order_attrs.get('totalValue')
            if order_total_value:
                try:
                    order_total_value = float(order_total_value)
                    odoo_order_id.amount_untaxed = wf_subtotal_value
                    odoo_order_id.amount_tax = order_total_value - wf_subtotal_value
                    odoo_order_id.amount_total = order_total_value

                    _logger.warning(f'++++++ order values: {odoo_order_id.amount_untaxed} . {odoo_order_id.amount_tax} . {odoo_order_id.amount_total}')
                except:
                    _logger.warning('Cannot parse the totalValue passed by Waterfitters. Using the calculated total.')

            odoo_order_id.action_confirm()
            self.env.cr.commit()
            _logger.warning(f"Sale order {odoo_order_id.display_name} ({odoo_order_id.id}) confirmed.")

            ### SET THE SHIPPING DATE FOR EACH LINE - STOP ###

            ### PATCH THE ORIGINAL WATERFITTERS ORDER - START ###
            patch_payload = {
                "data": {
                    "type": "orders",
                    "id": str(order_elem_id),
                    "attributes": {
                        "is_erp_exported": True,
                        "erp_exported_at": now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        "erp_id": order_name
                    }
                }
            }

            patch_response = self._wf_payload_request(
                'orders', patch_payload, token, 'PATCH', order_elem_id
            )
            _logger.info(_(f'Order PATCH payload: {patch_payload}'))
            _logger.info(_(f'Order PATCH response: {patch_response}'))

            ### PATCH THE ORIGINAL WATERFITTERS ORDER - STOP ###

    ### LIST GET API METHODS ###

    def orders(self, sync_from_datetime=False):

        token = self._wf_get_token()
        if not token:
            _logger.error(_('Unable to obtain a token - Cannot proceed'))
            return None

        now = datetime.datetime.now()
        now_string = now.strftime('%d/%m/%Y')

        if not sync_from_datetime: sync_from_datetime = now - datetime.timedelta(hours=4)
        sync_from_iso = sync_from_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

        order_data = self._fetch_paginated_data("orders", sync_from_iso)

        if order_data:
            order_ids = [element['id'] for element in order_data if 'id' in element]
            for order_id in order_ids: self.order(token, order_id)

    def products(self, start_date_str=False):
        product_data = self._fetch_paginated_data("products", start_date_str)
        if product_data:
            _logger.warning(f"Sync Waterfitters - Products Data: {product_data}")