###################################################################################
#
#    Copyright (c) 2017-today MuK IT GmbH.
#
#    This file is part of MuK REST for Odoo
#    (see https://mukit.at).
#
#    MuK Proprietary License v1.0
#
#    This software and associated files (the "Software") may only be used
#    (executed, modified, executed after modifications) if you have
#    purchased a valid license from MuK IT GmbH.
#
#    The above permissions are granted for a single database per purchased
#    license. Furthermore, with a valid license it is permitted to use the
#    software on other databases as long as the usage is limited to a testing
#    or development environment.
#
#    You may develop modules based on the Software or that use the Software
#    as a library (typically by depending on it, importing it and using its
#    resources), but without copying any source code or material from the
#    Software. You may distribute those modules under the license of your
#    choice, provided that this license is compatible with the terms of the
#    MuK Proprietary License (For example: LGPL, MIT, or proprietary licenses
#    similar to this one).
#
#    It is forbidden to publish, distribute, sublicense, or sell copies of
#    the Software or modified copies of the Software.
#
#    The above copyright notice and this permission notice must be included
#    in all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
###################################################################################

import datetime
import collections

from odoo import models, fields


class Base(models.AbstractModel):
    
    _inherit = 'base'
    

    #----------------------------------------------------------
    # Helper
    #----------------------------------------------------------
    
    def _rest_extract_fields(self, fields):
        infinitedict = lambda: collections.defaultdict(
            infinitedict
        )
        
        def build_fields(x):
            field_list = []
            for key, val in x.items():
                field_list.append(
                    [key, build_fields(val)]
                )
            return field_list
        
        fields_to_extract = infinitedict()
        for field in fields:
            current = fields_to_extract
            for fname in field.split('/'):
                current = current[fname]
            current = infinitedict()
        return build_fields(fields_to_extract)
    
    def _rest_extract_data(self, fields, metadata, toplevel=True):
        record_splittor = lambda records: records

        def subset_splittor(records):
            for idx in range(0, len(records), 1000):
                subset = records[idx:idx+1000]
                for record in subset:
                    yield record
                subset.invalidate_recordset()
        
        if toplevel:
            record_splittor = subset_splittor
        
        extracted_data = []
        for record in record_splittor(self):
            record_values = (
                {'id-integer': record.id}
                if metadata else {'id': record.id}
            )
            for fnames in fields:
                record_values_key = fnames[0]
                value = record[record_values_key]
                field = record._fields[record_values_key]
                
                if metadata:
                    record_values_key = '{}-{}'.format(
                        record_values_key,
                        field.type
                    )
                    if field.relational:
                        record_values_key = '{}/{}'.format(
                            record_values_key,
                            field.comodel_name
                        )
                        
                if isinstance(value, models.BaseModel):
                    extract_data = (
                        value._rest_extract_data(
                            fnames[1], metadata, toplevel=False,
                        )
                        if fnames[1]
                        else value.ids
                    )
                    if field.type == 'many2one':
                        record_values[record_values_key] = (
                            extract_data[0] if extract_data else False
                        )
                    else:
                        record_values[record_values_key] = extract_data
                else:
                    output = record._fields[fnames[0]].convert_to_read(
                        value, record, False
                    )
                    record_values[record_values_key] = output
            extracted_data.append(record_values)
        return extracted_data
    
    #----------------------------------------------------------
    # Functions
    #----------------------------------------------------------
    
    def rest_extract_data(self, fields=None, metadata=False):
        input_fields = self._rest_extract_fields(fields or list(self._fields))
        return self._rest_extract_data(input_fields, metadata, toplevel=True)
