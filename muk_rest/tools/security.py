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

import base64
import urllib
import functools
import werkzeug

from odoo import http, api, registry, SUPERUSER_ID
from odoo.exceptions import AccessDenied

from odoo.addons.muk_rest import validators, tools


def decode_http_basic_authentication(encoded_header):
    header_values = encoded_header.strip().split(' ')

    def decode_http_basic_authentication_value(value):
        try:
            username, password = base64.b64decode(value).decode().split(':', 1)
            return urllib.parse.unquote(username), urllib.parse.unquote(password)
        except:
            return None, None
    if len(header_values) == 1:
        return decode_http_basic_authentication_value(header_values[0])
    if len(header_values) == 2 and header_values[0].strip().lower() == 'basic':
        return decode_http_basic_authentication_value(header_values[1])
    return None, None


def get_response_type(grant_type):
    return tools.common.GRANT_RESPONSE_MAP.get(grant_type, [])
