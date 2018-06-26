#!/usr/bin/env python3

import requests

from .connection import AbstractPCloudConnection

PCLOUD_SERVER = "api.pcloud.com"
PCLOUD_PORT = 80
PCLOUD_SSL_PORT = 443

class PCloudJSONConnection(AbstractPCloudConnection):

    """Connection to pcloud.com based on their json protocol.

    NOTE: loads the whole file in memory on data upload.
    """

    def __init__(self,
                 use_ssl=True,
                 server=PCLOUD_SERVER, port=None,
                 timeout=30,
                 auth=None,
                 persistent_params=None):
        """Connection to pcloud.com based on their json protocol.

        persistent_params is a dict that augments params on each command,
        this is useful for storing auth data.

        NOTE: persistent_params overrides any values in params on send_command
        """
        self.use_ssl = use_ssl
        self.timeout = timeout
        if persistent_params is None:
            self.persistent_params = {}
        else:
            self.persistent_params = persistent_params
        if auth is not None:
            self.auth = auth
        self.baseurl = "{protocol}://{server}:{port}/".format(
                            protocol=use_ssl and 'https' or 'http',
                            server=server,
                            port=port or (use_ssl and 443 or 80)
                        )

    def send_command(self, method, **params):
        """Sends command and returns result. Blocks if result is needed.

        :param method: the pcloud method to call
        :param **params: parameters to be passed to the api, except:
            - '_data' is the file data
            - '_data_progress_callback' is the upload callback
        :returns dictionary returned by the api
        """
        data = params.pop('_data', None)
        data_progress_callback = params.pop('_data_progress_callback', None)

        params.update(self.persistent_params)

        #TODO: actually use the callback, probably chunk encoding
        execute_request = data is None and requests.get or requests.put

        #FIXME: currently loads the whole file into memory
        r = execute_request(self.baseurl + method,
                            params=params,
                            data=data,
                            allow_redirects=False,
                            timeout=self.timeout)
        r.raise_for_status()

        return r.json()


