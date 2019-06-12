""" Abstracts creating Google Services.
"""
import os
import httplib2
from apiclient import discovery
from oauth2client import tools
from oauth2client import client
from oauth2client.file import Storage

_APP_NAME = 'Scheduler'
_SECRET_DIR = 'credentials'
_APP_SECRET = 'scheduler_secret.json'
_CLIENT_SECRET = 'client_secret.json'

GMAIL = {
    'name': 'gmail',
    'scope': 'https://mail.google.com/',
    'args': ['gmail', 'v1'],
    'kwargs': {}
}

SHEETS = {
    'name': 'sheets',
    'scope': 'https://www.googleapis.com/auth/spreadsheets',
    'args': ['sheets', 'v4'],
    'kwargs': {
        'discoveryServiceUrl':
        'https://sheets.googleapis.com/$discovery/rest?version=v4'
    }
}

CALENDAR = {
    'name': 'calendar',
    'scope': 'https://www.googleapis.com/auth/calendar',
    'args': ['calendar', 'v3'],
    'kwargs': {}
}

class ServiceProvider(object):

    def __init__(self, *service_defs):
        self._credentials = self.fetch_credentials(*service_defs)
        self._services = {s['name']: self.fetch_service(s) for s in service_defs}

    @staticmethod
    def fetch_credentials(*service_defs):

        # Attempt to retrieve existing credentials
        current_dir = os.getcwd()
        credential_dir = os.path.join(current_dir, _SECRET_DIR)
        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir, _APP_SECRET)

        store = Storage(credential_path)
        credentials = store.get()

        # Create new credentials on failure
        if not credentials or credentials.invalid:
            client_path = os.path.join(credential_dir, _CLIENT_SECRET)
            scopes = [s['scope'] for s in service_defs]
            flow = client.flow_from_clientsecrets(client_path, scopes)
            flow.user_agent = _APP_NAME
            credentials = tools.run_flow(flow, store)

        return credentials

    def fetch_service(self, service_def):
        authorization = self._credentials.authorize(httplib2.Http())
        service_def['kwargs']['http'] = authorization
        return discovery.build(*service_def['args'], **service_def['kwargs'])


    def get_service(self, service_name):
        return self._services[service_name]