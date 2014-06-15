#!/usr/bin/env python3

import abc

class AbstractPCloudConnection(metaclass=abc.ABCMeta):

    """Abstract class for pcloud connection.

    A concrete class should implement send_command and potentially connect.

    :ivar use_ssl: to use or not ssl
    :ivar timeout: connection timeout
    :ivar auth: authentication token, stored in .persistent_params
    :ivat persistent_params: persistent parameters for storing auth and etc.
    """

    @abc.abstractmethod
    def send_command(self, method, **params):
        """Sends command and returns result.

        If '_data' is in params it is the file data
        If '_data_progress_callback' is in params it is the upload callback
        """
        raise NotImplemented

    def connect(self):
        """Establish connection and return self."""
        return self

    @property
    def auth(self):
        return self.persistent_params['auth']
    @auth.setter
    def auth(self, auth):
        if auth:
            self.persistent_params['auth'] = auth
        else:
            self.persistent_params.pop('auth', None)

    def close(self):
        """Perform any cleanup operation"""
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

