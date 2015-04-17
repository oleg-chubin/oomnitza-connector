
import logging

from requests import ConnectionError, HTTPError
from lib.connector import UserConnector

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


class Connector(UserConnector):
    MappingName = 'Okta'
    Settings = {
        'url':              {'order': 1, 'default': "https://oomnitza1-admin.okta.com"},
        'api_token':        {'order': 2, 'example': "00kS9y1nRuNo1WJAuFixx-BB0K2Yd1RXZcLPuDFJrF"},
        'default_role':     {'order': 3, 'example': 25, 'type': int},
        'default_position': {'order': 4, 'example': 'Employee'},
    }

    FieldMappings = {
        'USER':           {'source': "login"},
        'FIRST_NAME':     {'source': "firstName"},
        'LAST_NAME':      {'source': "lastName"},
        'EMAIL':          {'source': "email"},
        'PHONE':          {'source': "mobilePhone"},
        'PERMISSIONS_ID': {'setting': "default_role"},
        'POSITION':       {'setting': "default_position"},
    }

    def __init__(self, settings):
        super(Connector, self).__init__(settings)

    def get_headers(self):
        return {
            'contentType': 'application/json',
            'Authorization': 'SSWS %s' % self.settings['api_token']
        }

    def test_connection(self, options):
        try:
            url = "{0}/api/v1/users?limit=1".format(self.settings['url'])
            response = self.get(url)
            response.raise_for_status()
            return {'result': True, 'error': ''}
        except ConnectionError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}
        except HTTPError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def _load_records(self, options):
        next = "{0}/api/v1/users?limit={1}".format(self.settings['url'], options.get('limit', 100))
        while next:
            response = self.get(next)
            for user in response.json():
                yield user['profile']
            next = response.links.get('next', {}).get('url', None)