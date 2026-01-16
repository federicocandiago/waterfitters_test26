# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, fields, _, api
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ["res.partner", "waterfitters.shared"]

    international_vat_code = fields.Char()
    industry_group_id = fields.Many2one('industry.group')
    solvency_block_status = fields.Selection([
        ('N', 'Valid'), ('A', 'Attention'), ('B', 'Blocked')
    ], default="N")

    waterfitters_id = fields.Integer('Waterfitters ID')
    wf_account_id = fields.Integer('Waterfitters account ID')
    wf_billing_address_id = fields.Integer('WF billing addr. ID')
    wf_shipping_address_id = fields.Char('WF shipping addr. ID')
    wf_customer_user_id = fields.Char('WF customer user ID')
    wf_is_ready_to_sync = fields.Boolean('To be synched with WF?')
    wf_is_default_shipping_address = fields.Boolean('Is a default shipping address?', default=True)

    def _extract_numeric_value(self, value):
        return int(value) if isinstance(value, str) and value.isdigit() else None

    def sync_waterfitters_customers(self):
        batch_limit = self.env['ir.config_parameter'].sudo().get_param('waterfitters_customers_batch_limit')
        limit = int(batch_limit) if batch_limit else None

        synchable_partner_ids = self.env['res.partner'].sudo().search(
            [('wf_is_ready_to_sync', '=', True), ('type', '=', 'contact')], order='write_date', limit=limit
        ).filtered(lambda p: any(so.name.startswith('OW') for so in p.sale_order_ids))

        if synchable_partner_ids: synchable_partner_ids.wf_post_customers()

    def _get_address_code_from_erp_id(self, erp_id):
        if isinstance(erp_id, str) and '_' in erp_id: return erp_id.split('_', 1)[1]
        return ''

    def _get_new_resource_data(self, response):
        if response and 'json' in response:
            res_json = response['json']
            return int(res_json['data']['id']) if res_json and 'data' in res_json and 'id' in res_json['data'] else 0

    def _define_sync_status(self, vals):
        wf_tracked_fields = [
            'name', 'email', 'x_studio_codice_categoria_sconto', 'fiscalcode', 'x_studio_iban',
            'is_erp_exported', 'x_studio_codice_soggetto', 'industry_group_id', 'international_vat_code',
            'l10n_it_pec_email', 'phone', 'x_studio_codice_sdi', 'vat', 'x_studio_pagamento',
            'x_studio_assoggettamento_iva', 'x_studio_partita_iva_testo', 'parent_id',
            'is_company', 'street', 'street2', 'city', 'country_id', 'state_id'
        ]

        for partner in self:
            try:
                parent = partner.parent_id

                # Se modifico un contatto, aggiorno il parent
                if partner.type == 'contact' and any(f in vals for f in wf_tracked_fields):
                    (parent or partner).sudo().write({'wf_is_ready_to_sync': True})

                # Se modifico un indirizzo, aggiorno il cliente principale
                elif parent and (
                        parent.wf_billing_address_id == partner.id or parent.wf_shipping_address_id == partner.id):
                    parent.sudo().write({'wf_is_ready_to_sync': True})

            except Exception as e:
                _logger.error(f"Couldn't set partner {partner.id} as synchable in Waterfitters: {e}")

    def write(self, vals):
        self._define_sync_status(vals)
        return super().write(vals)

    def create(self, vals):
        res = super().create(vals)
        res._define_sync_status(vals)
        return res

    def _get_fiscal_position(self, address):
        is_italian = address.get('odoo_country_code') == 'IT'
        country_id = address.get('odoo_country_id')

        # Fiscal position
        fiscal_position = 4  # Extra UE
        if not country_id or is_italian:
            fiscal_position = 1  # Italian
        elif country_id.in_eu:
            fiscal_position = 3  # Intra UE

        return {'fiscal_position': fiscal_position, 'is_italian': is_italian}

    def _build_customer_address(self, customer_id, name, is_company, is_shipping, country_code, street, street2, city,
                                postal_code, region_code=None, erp_id=None, is_default_shipping=False,
                                is_primary=False):

        types = [{'addressType': 'shipping', 'default': is_default_shipping}]
        if not is_shipping: types.append({'addressType': 'billing', 'default': True})

        # Base dict
        address_dict = {
            'data': {
                'type': 'customeraddresses',
                'attributes': {
                    'city': city,
                    'erp_id': erp_id,
                    'postalCode': postal_code or '00000',
                    'primary': is_primary,
                    'street': street or '-',
                    'street2': street2 or None,
                    'types': types,
                },
                'relationships': {
                    'customer': {'data': {'type': 'customers', 'id': str(customer_id)}},
                    'country': {'data': {'type': 'countries', 'id': country_code}}
                }
            }
        }

        if region_code:
            address_dict['data']['relationships']['region'] = {
                'data': {'type': 'regions', 'id': f'{country_code}-{region_code}' if region_code else ''}}

        # Name in the address
        address_dict['data']['attributes']['organization'] = name

        return address_dict

    # Creates customers in Waterfitters (to be used as an internal function?)
    def wf_post_customers(self):

        Partner = self.env['res.partner'].sudo()
        if not hasattr(self, '_connection_data'): self._get_connection_data()

        token = self._wf_get_token()
        if not token:
            _logger.error(_('Unable to obtain a token - Cannot proceed'))
            return None

        # Only cycle through contacts - not addresses, etc.
        contacts = [partner_id for partner_id in self if partner_id.type == 'contact']

        for partner_id in contacts:

            # Step 1: Base Account Creation (if not registered already)
            if not partner_id.wf_account_id:
                account_payload = {"data": {"type": "accounts", "attributes": {"name": partner_id.name}}}

                account_response = self._wf_payload_request('accounts', account_payload, token)
                account_json = account_response['json']

                if account_json and 'data' in account_json and 'id' in account_json['data']:
                    partner_id.wf_account_id = int(account_json['data']['id'])
                else:
                    _logger.error(
                        _(f'Unable to create the customer for record {partner_id.name} ({partner_id.id}) - Passing to next..'))
                    pass

            # Step 2: Base Customer Creation

            # Tax Code Mapping
            is_taxable_str = partner_id.x_studio_assoggettamento_iva

            non_taxable_keywords = [
                'N.IMP', 'NON', 'ESENTE', 'ESCLUSO', 'F.C.', 'FUORI'
            ]  # TODO: shouldn't be hardcoded

            tax_code = 2 if is_taxable_str and any(k in is_taxable_str.upper() for k in non_taxable_keywords) else 1

            # Partner vat management
            partner_vat = None
            if partner_id.vat:
                partner_vat = partner_id.vat
            elif partner_id.x_studio_partita_iva_testo:
                partner_vat = partner_id.x_studio_partita_iva_testo

            # Discount Category Management
            discount_cat = ''
            if partner_id.property_product_pricelist:
                discount_cat = partner_id.property_product_pricelist.x_studio_codice_sigla

            attributes_dict = {
                'name': partner_id.name if partner_id.name else f'{partner_id.email} (Odoo)',
                'email': partner_id.email,
                'erp_discount_cat': discount_cat,
                'erp_id': partner_id.x_studio_codice_soggetto or None,  # TODO: studio field, to be edited
                'fiscal_code': partner_id.fiscalcode or None,
                'iban': partner_id.x_studio_iban or None,  # TODO: studio field, to be edited
                'is_erp_exported': True,
                'is_exportable': False,
                'pec': partner_id.l10n_it_pec_email or None,
                'phone': partner_id.phone or None,
                'sdi': partner_id.x_studio_codice_sdi or None,  # TODO: studio field, to be edited
                'vat_code': partner_vat,
                'taxCode': tax_code  # TODO: studio field, to be edited
            }

            # Wf shipping method
            if partner_id.x_studio_many2one_field_GTsiS:  # TODO: studio field, to be edited
                wf_shipping_method_id = self.env['wf.shippingmethod'].search([
                    ('incoterm', '=', partner_id.x_studio_many2one_field_GTsiS.code)
                ], limit=1)
                if wf_shipping_method_id: attributes_dict['shippingMethod'] = wf_shipping_method_id.name

            # Payment Term Mapping
            wf_payment_term = 79  # Default payment term: pre-paid
            payment_term = partner_id.property_payment_term_id
            if payment_term and payment_term.x_studio_codice:  # TODO: studio field, to be edited
                payment_record = self.env['wf.paymentterm'].search([('code', '=', payment_term.x_studio_codice)],
                                                                   limit=1)
                if payment_record: wf_payment_term = str(payment_record.waterfitters_id)

            # Groups mapping (using industry.group records)
            industry_group = 1
            industry_id = partner_id.industry_group_id
            if industry_id and industry_id.waterfitters_id: industry_group = industry_id.waterfitters_id

            customer_payload = {
                'data': {
                    'type': 'customers',
                    'attributes': attributes_dict,
                    'relationships': {
                        'origin': {'data': []},
                        'group': {'data': {'type': 'customergroups', 'id': str(industry_group)}},
                        'account': {'data': {'type': 'accounts', 'id': str(partner_id.wf_account_id)}},
                        "taxCode": {'data': {'type': 'customertaxcodes', 'id': str(tax_code)}},
                        "paymentTerm": {'data': {'type': 'paymentterms', 'id': str(wf_payment_term)}}
                    }
                }
            }

            # Add customer block status if there's one
            if partner_id.solvency_block_status:
                customer_payload['data']['relationships']['erpBlockStatus'] = {
                    'data': {
                        'type': 'algoritmaerpblockstatuses',
                        'id': partner_id.solvency_block_status
                    }
                }

            _logger.warning('*** customer_payload ***')
            _logger.warning(f'{customer_payload} ***')

            if partner_id.waterfitters_id:
                # Case 1: PATCH if it's an existing record
                customer_payload['data']['id'] = str(partner_id.waterfitters_id)
                post_response = self._wf_payload_request('customers', customer_payload, token, 'PATCH',
                                                         partner_id.waterfitters_id)
            else:
                # Case 2: POST it as a new record
                customer_payload['data']['relationships']['origin']['data'] = {'type': 'waterfittersorigins', 'id': 'M'}
                ### TODO - TO BE RESET IN THE FUTURE - WHEN SIGLA WILL NOT BE MASTER ANYMORE ####

                post_response = self._wf_payload_request('customers', customer_payload, token)

            if not partner_id.waterfitters_id: partner_id.waterfitters_id = self._get_new_resource_data(post_response)

            # Step 3: Customer Addresses Creation

            # Billing Address
            wf_billing_partner_id = partner_id.wf_billing_address_id

            billing_country_code = partner_id.country_id.code[:2].upper() if partner_id.country_id else 'IT'
            billing_region_code = partner_id.state_id.code[:2].upper() if partner_id.state_id else None
            if not billing_region_code and billing_country_code == 'IT': billing_region_code = 'VI'

            billing_erp_id = False
            if partner_id.x_studio_codice_soggetto and '_' in partner_id.x_studio_codice_soggetto:
                billing_erp_id = partner_id.x_studio_codice_soggetto
            elif partner_id.x_studio_codice_soggetto:
                billing_erp_id = f'{partner_id.x_studio_codice_soggetto}_0'

            billing_payload = self._build_customer_address(
                partner_id.waterfitters_id, partner_id.name, partner_id.is_company, False,
                billing_country_code,
                partner_id.street, partner_id.street2, partner_id.city, partner_id.zip,
                billing_region_code,
                billing_erp_id
            )

            if not wf_billing_partner_id:
                billing_response = self._wf_payload_request('customeraddresses', billing_payload, token)
                _logger.info(_(f'billing POST payload: {billing_payload}'))
                _logger.info(_(f'billing POST response: {billing_response}'))

                wip_billing_res = self._get_new_resource_data(billing_response)
                if wip_billing_res: partner_id.write({'wf_billing_address_id': wip_billing_res})
            else:
                billing_payload['data']['id'] = str(wf_billing_partner_id)
                self._wf_payload_request('customeraddresses', billing_payload, token, 'PATCH',
                                         partner_id.wf_billing_address_id)

            # Avoid double POST/PATCH when the address is both billing and shipping
            wf_billing_id = partner_id.wf_billing_address_id
            wf_shipping_id = (
                str(partner_id.wf_shipping_address_id).split(',')[0]
                if partner_id.wf_shipping_address_id else False
            )

            if wf_billing_id and wf_shipping_id and str(wf_billing_id) == wf_shipping_id:
                partner_id.wf_shipping_address_id = str(wf_billing_id)
                billing_types = billing_payload['data']['attributes']['types']
                has_shipping_type = any(t.get('addressType') == 'shipping' for t in billing_types)

                if not has_shipping_type:
                    billing_types.append({'addressType': 'shipping', 'default': True})
                else:
                    for t in billing_types:
                        if t['addressType'] == 'shipping': t['default'] = True

                billing_payload['data']['attributes']['types'] = billing_types
                partner_id.wf_is_ready_to_sync = False
                continue

            # Shipping Addresses

            # 1. Get the addresses (new - without waterfitters_id - and existing), fallback to partner_id if none found - not the shipping id
            shipping_partners = Partner.search([('parent_id', '=', partner_id.id), ('type', '=', 'delivery')])
            if not shipping_partners: shipping_partners = partner_id

            wf_shipping_ids = []

            for shipping_partner in shipping_partners:

                shipping_partner_erp_id = shipping_partner.x_studio_codice_soggetto
                if shipping_partner_erp_id and not shipping_partner.x_studio_codice_indirizzo_spedizione:

                    # 2. Find other delivery addresses with same ERP id
                    shipping_siblings = Partner.search([
                        ('type', '=', 'delivery'),
                        ('x_studio_codice_soggetto', '=', shipping_partner_erp_id),
                        ('id', '!=', shipping_partner.id)
                    ])

                    numeric_codes = [
                        self._extract_numeric_value(p.x_studio_codice_indirizzo_spedizione)
                        for p in shipping_siblings
                    ]
                    numeric_codes = [n for n in numeric_codes if n is not None]

                    shipping_address_next_code = max(numeric_codes) + 1 if numeric_codes else 1
                    shipping_partner.x_studio_codice_indirizzo_spedizione = str(shipping_address_next_code)

                shipping_country_code = 'IT'
                if shipping_partner.country_id:
                    shipping_country_code = shipping_partner.country_id.code[:2].upper() if shipping_partner.country_id else 'IT'
                shipping_region_code = shipping_partner.state_id.code[:2].upper() if shipping_partner.state_id else None

                if not shipping_region_code and shipping_country_code == 'IT': shipping_region_code = 'VI'

                shipping_name = shipping_partner.name or partner_id.name
                #shipping_erp_id = f"{shipping_partner.x_studio_codice_soggetto or ''}_{shipping_partner.x_studio_codice_indirizzo_spedizione or ''}"
                shipping_erp_id = ''
                if shipping_partner.x_studio_codice_soggetto:
                    if '_' in shipping_partner.x_studio_codice_soggetto:
                        shipping_erp_id = shipping_partner.x_studio_codice_soggetto
                    elif shipping_partner.x_studio_codice_indirizzo_spedizione:
                        shipping_erp_id = f'{shipping_partner.x_studio_codice_soggetto}_{shipping_partner.x_studio_codice_indirizzo_spedizione}'

                shipping_payload = self._build_customer_address(
                    partner_id.waterfitters_id, shipping_name, shipping_partner.is_company, True, shipping_country_code,
                    shipping_partner.street, shipping_partner.street2, shipping_partner.city, shipping_partner.zip,
                    shipping_region_code, shipping_erp_id, shipping_partner.wf_is_default_shipping_address
                )

                new_shipping_address_id = self._get_new_resource_data(shipping_response)
                wf_shipping_ids.append(str(new_shipping_address_id))

                if not shipping_partner.waterfitters_id:
                    shipping_response = self._wf_payload_request('customeraddresses', shipping_payload, token)
                    shipping_partner.waterfitters_id = new_shipping_address_id
                else:
                    shipping_payload['data']['id'] = str(shipping_partner.waterfitters_id)
                    shipping_response = self._wf_payload_request('customeraddresses', shipping_payload, token, 'PATCH',
                                                                 shipping_partner.waterfitters_id)
                    self._get_new_resource_data(shipping_response)

                _logger.info(_(f'shipping_payload POST payload: {shipping_payload}'))
                _logger.info(_(f'shipping_response POST response: {shipping_response}'))

            partner_id.wf_shipping_address_id = ','.join(map(str, wf_shipping_ids))
            partner_id.wf_is_ready_to_sync = False

    def wf_get_customers(self, sync_from_datetime=False):
        Partner = self.env['res.partner'].sudo()
        if not hasattr(self, '_connection_data'): self._get_connection_data()

        token = self._wf_get_token()
        if not token:
            _logger.error(_('Unable to obtain a token - Cannot proceed'))
            return None

        now = datetime.now()
        now_string = now.strftime('%d/%m/%Y')
        now_zulu = now.strftime('%Y-%m-%dT%H:%M:%SZ')

        if not sync_from_datetime: sync_from_datetime = now - timedelta(minutes=30)
        sync_from_zulu = sync_from_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

        customer_response = self._wf_get_paginated('customers', token, f'[createdAt][gt]={sync_from_zulu}', 'createdAt')

        _logger.warning(f'customer_response: {customer_response}')

        if customer_response:
            for partner_dict in customer_response:

                partner_elem = partner_dict.get('element', {})
                partner_rel = partner_elem.get('relationships', {})
                _logger.warning(f'partner_elem: {partner_elem}')
                partner_attrs = partner_elem.get('attributes', {})
                waterfitters_id = int(partner_elem.get('id', 0))

                # Addresses
                shipping_addresses_list = []
                billing_address = {}
                addresses_data = partner_rel.get('addresses', {}).get('data', [])
                if addresses_data:
                    for address in addresses_data:
                        address_id = int(address.get('id', 0))
                        address_elem = self._wf_get_element("customeraddresses", address_id, token)
                        address_attrs = address_elem.get('attributes') if address_elem else {}
                        address_types_dict = address_attrs.get('types') if address_attrs else {}

                        address_country_id = self._get_partner_country(address_elem) if address_elem else False
                        country_id = self.env['res.country'].search([('code', '=', str(address_country_id).upper())],
                                                                    limit=1)

                        address_attrs['wf_id'] = address_id
                        address_attrs['odoo_country_id'] = country_id
                        address_attrs['odoo_country_code'] = country_id.code if country_id else False

                        # Region\Province\State management
                        region_id = False
                        region_data = address_attrs.get('region', {}) if address_attrs else {}
                        region_code = region_data.get('data', {}).get('id')
                        if region_code:
                            region_code = str(region_code).strip().upper()
                            region_id = self.env['res.country.state'].search([('code', '=', region_code)], limit=1)
                        address_attrs['odoo_region_id'] = region_id.id if region_id else False

                        address_types = [addr.get('addressType') for addr in address_types_dict]
                        if 'billing' in address_types: billing_address = address_attrs
                        if 'shipping' in address_types:
                            address_attrs['is_default_shipping'] = any(
                                t.get('addressType') == 'shipping' and t.get('default', False) for t in
                                address_types_dict)
                            shipping_addresses_list.append(address_attrs)

                # Customer Block Status
                block_status_id = False
                block_status_data = partner_rel.get('erpBlockStatus', {}).get('data')
                block_status_wf_id = block_status_data.get('id', False) if block_status_data else False
                if block_status_wf_id in dict(self._fields['solvency_block_status'].selection).keys():
                    block_status_id = block_status_wf_id

                # Customer Industry group
                industry_group_id = False
                group_id = self.get_relationship_id(token, partner_rel, 'group')
                _logger.warning(f'industry group_id: {group_id}')
                if group_id:
                    industry_group_id = self.env['industry.group'].sudo().search(
                        [('waterfitters_id', '=', group_id), ('is_wf_primary_match', '=', True)], limit=1
                    )
                    _logger.warning(f'industry industry_group_id: {industry_group_id}')

                # Customer Payment Term
                PaymentTerm = self.env['account.payment.term'].sudo()
                WfPaymentTerm = self.env['wf.paymentterm'].sudo()

                payment_term_id = False
                term_id = self.get_relationship_id(token, partner_rel, 'paymentTerm')
                if term_id:
                    wf_term_id = WfPaymentTerm.search([('waterfitters_id', '=', term_id)], limit=1)
                    if wf_term_id:
                        payment_term_id = PaymentTerm.search([('x_studio_codice', '=', wf_term_id.code)], limit=1)

                if not payment_term_id: payment_term_id = PaymentTerm.search([
                    ('x_studio_codice', '=', 'CACR')
                ], limit=1)

                # Customer Account
                wf_account_id = self.get_relationship_id(token, partner_rel, 'account')

                # Search existing partner
                partner_id = Partner.search(
                    [('type', '=', 'contact'), ('waterfitters_id', '=', waterfitters_id)],
                    limit=1)

                # PARTNER CREATION - ONLY IF NOT ALREADY IN ODOO
                if not partner_id:

                    # Get the price category (both for the m2o record and the x_studio string)
                    price_category = partner_attrs.get('erp_discount_cat', False)

                    pricelist_id = False
                    Pricelist = self.env['product.pricelist'].sudo()
                    if price_category: pricelist_id = Pricelist.search(
                        [('x_studio_codice_sigla', '=', price_category)],
                        limit=1)

                    # If creating a new user and pricelist_id is not found, se standard Price List (WP1) # TODO: studio field, to be edited
                    if not pricelist_id and not partner_id: pricelist_id = Pricelist.search(
                        [('x_studio_codice_sigla', '=', 'WF1')],
                        limit=1)

                    fiscal_position_res = self._get_fiscal_position(billing_address)
                    fiscal_position = fiscal_position_res.get('fiscal_position')
                    is_italian = fiscal_position_res.get('is_italian')
                    odoo_country_id = billing_address.get('odoo_country_id')

                    partner_domain = {
                        'parent_id': False,
                        'is_company': True,
                        'lang': 'it_IT' if fiscal_position == 1 else 'en_US',
                        'type': 'contact',
                        'street': billing_address.get('street'),
                        'street2': billing_address.get('street2'),
                        'city': billing_address.get('city'),
                        'zip': billing_address.get('postalCode'),
                        'state_id': billing_address.get('odoo_region_id'),
                        'country_id': odoo_country_id.id if odoo_country_id else False,
                        'name': partner_attrs.get('name') or _('Waterfitters customer ')+partner_attrs.get('email',''),
                        'x_studio_codice_indirizzo_spedizione': '0', # TODO: studio field, to be edited
                        'email': partner_attrs.get('email'),
                        'x_studio_codice_soggetto': partner_attrs.get('erp_id'),  # TODO: studio field, to be edited
                        'phone': partner_attrs.get('phone'),
                        'fiscalcode': partner_attrs.get('fiscal_code'),
                        'x_studio_iban': partner_attrs.get('iban'),  # TODO: studio field, to be edited
                        'x_studio_codice_sdi': partner_attrs.get('sdi'),  # TODO: studio field, to be edited
                        'x_studio_partita_iva_testo': partner_attrs.get('vat_code', ''),  # TODO: studio field, tbe
                        'solvency_block_status': block_status_id,
                        'x_studio_codice_categoria_sconto': price_category,  # TODO: studio field, to be edited
                        'comment': _('Imported from Waterfitters on ') + now_string,
                        'category_id': [1],
                        'industry_group_id': industry_group_id.id if industry_group_id else False,
                        'property_payment_term_id': payment_term_id.id if payment_term_id else False,
                        'property_account_position_id': fiscal_position,
                        'waterfitters_id': waterfitters_id,
                        'wf_billing_address_id': billing_address.get('wf_id', 0),
                        'wf_shipping_address_id': ','.join([str(s['wf_id']) for s in shipping_addresses_list]),
                        'wf_account_id': wf_account_id,
                    }

                    # Intl Vat code - if it has an international code, it gets priority first (for extra-ue and foreign customers)
                    int_identifier = partner_attrs.get('international_identifier_code')
                    intl_vat_code = int_identifier if not is_italian else False
                    if intl_vat_code: partner_domain['international_vat_code'] = intl_vat_code

                    if pricelist_id: partner_domain['property_product_pricelist'] = pricelist_id.id

                    # Create an ERP ID if not set from origin
                    partner_erp_id = partner_domain.get('x_studio_codice_soggetto')
                    if not partner_erp_id:
                        Sequence = self.env['ir.sequence'].sudo()

                        # Avoid assigning non-unique codes
                        while not partner_erp_id:
                            candidate_code = Sequence.next_by_code('seq.partner.waterfitters.id') or 'CW000001'
                            code_alreay_exists = self.env['res.partner'].sudo().search_count([
                                ('x_studio_codice_soggetto', '=', candidate_code)
                            ])
                            if not code_alreay_exists: partner_erp_id = candidate_code

                        partner_domain['x_studio_codice_soggetto'] = partner_erp_id

                    # Create the partner in Odoo, then if created PATCH the data back to
                    partner_id = Partner.create(partner_domain)
                    if not partner_id:
                        _logger.error(f'Unable to create a customer partner for the following domain: {partner_domain}')
                    if partner_id:
                        _logger.info(f'Waterfitters customer {waterfitters_id} saved ad Odoo Partner {partner_id.id}')

                        # PATCH the updated data back to Waterfitters
                        patch_payload = {
                            "data": {
                                "type": "customers",
                                "id": str(waterfitters_id),
                                "attributes": {
                                    "is_exportable": False,
                                    "is_erp_exported": True, "erp_exported_at": now_zulu,
                                    "erp_discount_cat": "WF1", "erp_id": partner_erp_id
                                },
                            }
                        }

                        # Pass payment term
                        if payment_term_id:

                            wf_payment_term_id = self.env['wf.paymentterm'].search([
                                ('code', '=', payment_term_id.x_studio_codice)
                            ], limit=1)

                            if wf_payment_term_id:
                                patch_payload['data']['relationships'] = {"paymentTerm":
                                                                              {'data': {'type': 'paymentterms',
                                                                                        'id': str(
                                                                                            wf_payment_term_id.waterfitters_id)}}
                                                                          }

                        patch_response = self._wf_payload_request(
                            'customers', patch_payload, token, 'PATCH', waterfitters_id
                        )
                        _logger.info(_(f'Customers PATCH payload: {patch_payload}'))
                        _logger.info(_(f'Customers PATCH response: {patch_response}'))

                # Customer Users
                customer_users_list = []

                customer_users_data = partner_rel.get('users', {}).get('data', [])

                if customer_users_data:
                    for customer_user_data in customer_users_data:
                        wf_customer_user_id = int(customer_user_data.get('id', 0))
                        if wf_customer_user_id:
                            customer_user_elem = self._wf_get_element("customerusers", wf_customer_user_id, token)
                            customer_user_attrs = customer_user_elem.get('attributes') if customer_user_elem else {}

                            name_parts = [
                                customer_user_attrs.get('namePrefix') or '',
                                customer_user_attrs.get('firstName') or '',
                                customer_user_attrs.get('middleName') or '',
                                customer_user_attrs.get('lastName') or '',
                                customer_user_attrs.get('nameSuffix') or ''
                            ]

                        customer_user_odoo_dict = {
                            'name': ' '.join(name_parts),
                            'parent_id': partner_id.id,
                            'type': 'contact',
                            'active': customer_user_attrs.get('enabled', True),
                            'email': customer_user_attrs.get('email'),
                            'wf_customer_user_id': wf_customer_user_id,
                            'customer_rank': 1,
                            'category_id': [11],
                            'is_company': False
                        }

                        # Write if existing else create the new shipping address
                        customer_user_id = Partner.search([
                            ('type', '=', 'contact'),
                            ('parent_id', '=', partner_id.id),
                            '|', '|', '|',
                            ('wf_customer_user_id', '=', str(wf_customer_user_id)),
                            ('wf_customer_user_id', '=like', f'{wf_customer_user_id},%'),
                            ('wf_customer_user_id', '=like', f'%,{wf_customer_user_id},%'),
                            ('wf_customer_user_id', '=like', f'%,{wf_customer_user_id}')
                        ], limit=1)

                        if not customer_user_id: Partner.create(customer_user_odoo_dict)
                        else: customer_user_id.write(customer_user_odoo_dict)

                        customer_users_list.append(str(wf_customer_user_id))

                partner_id.wf_customer_user_id = ','.join(customer_users_list)

                # Shipping addresses creation and update
                if shipping_addresses_list:
                    for shipping_address in shipping_addresses_list:
                        shipping_name = shipping_address.get('organization', _('Shipping Address'))
                        shipping_wf_id = shipping_address.get('wf_id')
                        shipping_erp_id = shipping_address.get('erp_id')
                        erp_subject = shipping_erp_id.split('_', 1)[0] if shipping_erp_id and '_' in shipping_erp_id else shipping_erp_id
                        shipping_erp_address_code = self._get_address_code_from_erp_id(shipping_erp_id)

                        country_id = shipping_address.get('odoo_country_id')
                        fiscal_position_res = self._get_fiscal_position(shipping_address)
                        fiscal_position = fiscal_position_res.get('fiscal_position')

                        shipping_odoo_dict = {
                            'parent_id': partner_id.id,
                            'commercial_partner_id': partner_id.id,
                            'category_id': [10],
                            'is_company': False,
                            'type': 'delivery',
                            'street': shipping_address.get('street'),
                            'street2': shipping_address.get('street2'),
                            'city': shipping_address.get('city'),
                            'zip': shipping_address.get('postalCode'),
                            'state_id': shipping_address.get('odoo_region_id'),
                            'country_id': country_id.id if country_id else False,
                            'name': shipping_name,
                            'email': partner_attrs.get('email'),
                            'x_studio_codice_soggetto': erp_subject, # TODO: studio field, to be edited
                            'x_studio_codice_indirizzo_spedizione': shipping_erp_address_code,
                            'phone': shipping_address.get('phone'),
                            'comment': _('Imported from Waterfitters on ') + now_string,
                            'waterfitters_id': shipping_wf_id,
                            'wf_is_default_shipping_address': shipping_address.get('is_default_shipping', False),
                        }

                        # Write if existing else create the new shipping address
                        shipping_partner_id = Partner.search(
                            [('type', '=', 'delivery'), ('waterfitters_id', '=', shipping_wf_id)], limit=1)

                        # Fallback: take the delivery address from erp_id and address_code
                        if not shipping_partner_id:
                            erp_code = shipping_address.get('erp_code')
                            if isinstance(erp_code, str) and '_' in erp_code:
                                erp_subject, erp_addr_code = erp_code.split('_', 1)
                                erp_shipping_address_int = self._extract_numeric_value(erp_addr_code)

                                domain = [
                                    ('type', '=', 'delivery'),
                                    ('x_studio_codice_soggetto', '=', erp_subject)
                                ]
                                candidate_shipping_partners = Partner.search(domain)

                                if erp_shipping_address_int is not None and candidate_shipping_partners:
                                    for shipping_candidate in candidate_shipping_partners:
                                        shipping_candidate_int = self._extract_numeric_value(
                                            shipping_candidate.x_studio_codice_indirizzo_spedizione)
                                        if shipping_candidate_int == erp_shipping_address_int:
                                            shipping_partner_id = shipping_candidate
                                            break
                                else:
                                    shipping_partner_id = candidate_shipping_partners.filtered(
                                        lambda p: p.x_studio_codice_indirizzo_spedizione == erp_addr_code)[:1]

                        # In not even the fallback finds a correspondence, create a new one
                        if not shipping_partner_id:
                            shipping_partner_id = Partner.create(shipping_odoo_dict)
                            # property_account_position_id is edited after the full write to avoid triggering
                            if shipping_partner_id: shipping_partner_id.write({
                                'property_account_position_id': fiscal_position
                            })
                            _logger.warning(f'shipping dict IN CREATE: {shipping_odoo_dict}')
                        else:
                            shipping_partner_id.write(shipping_odoo_dict)
                            shipping_partner_id.write({'property_account_position_id': fiscal_position})
                            _logger.warning(
                                f'shipping dict IN EDIT: {shipping_odoo_dict} - partner: {shipping_partner_id.id}')

                _logger.warning(f'partner_id: {partner_id}')
                self.env.cr.commit()

    def wf_get_users(self, sync_from_datetime=False):
        Partner = self.env['res.partner'].sudo()
        if not hasattr(self, '_connection_data'): self._get_connection_data()

        token = self._wf_get_token()
        if not token:
            _logger.error(_('Unable to obtain a token - Cannot proceed'))
            return None

        now = datetime.now()
        now_zulu = now.strftime('%Y-%m-%dT%H:%M:%SZ')

        if not sync_from_datetime: sync_from_datetime = now - timedelta(minutes=30)
        sync_from_zulu = sync_from_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

        user_response = self._wf_get_paginated('customerusers', token, f'[updatedAt][gt]={sync_from_zulu}', 'createdAt')

        if user_response:
            for user_dict in user_response:
                user_elem = user_dict.get('element', {})
                user_rel = user_elem.get('relationships', {})
                user_id = user_elem.get('id')
                user_attrs = user_elem.get('attributes', {})
                customer_rel = user_rel.get('customer', {})
                customer_data = customer_rel.get('data', {})
                customer_id = customer_data.get('id')

                if not user_attrs.get('is_erp_exported', False):
                    patch_payload = {
                        "data": {
                            "type": "customerusers",
                            "id": str(user_id),
                            "attributes": {
                                "is_erp_exported": True,
                                "erp_exported_at": now_zulu
                            }
                        }
                    }

                if customer_id:
                    partners_with_updated_users = Partner.search(
                        [('is_company', '=', True), ('waterfitters_id', '=', customer_id)]
                    )
                    if partners_with_updated_users: partners_with_updated_users.write({'wf_is_ready_to_sync': True})

