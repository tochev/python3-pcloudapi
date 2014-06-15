#!/usr/bin/env python3
import io
import socket

from .connection import AbstractPCloudConnection
from .utils import create_connection, PCloudBuffer

PCLOUD_BINAPI_SERVER = "binapi.pcloud.com"
PCLOUD_PORT = 80
PCLOUD_SSL_PORT = 443


class PCloudBinaryConnection(AbstractPCloudConnection):
    """Connection to pcloud.com based on their json protocol.

    NOTE: .connect() must be called to establish network communication.
    """

    def __init__(self,
                 use_ssl=True, server=PCLOUD_BINAPI_SERVER, port=None,
                 timeout=30,
                 auth=None,
                 persistent_params=None):
        """Initializes the API.

        :param persistent_params: a dict that augments params on each command,
            this is useful for storing auth data.

        NOTE: persistent_params overrides any values in params on send_command
        NOTE: .connect() must be called to establish network communication.
        """
        self.use_ssl = use_ssl
        self.server = server
        self.port = port or (self.use_ssl and PCLOUD_SSL_PORT or PCLOUD_PORT)
        self.timeout = timeout
        self.socket = None
        self.fp = None
        if persistent_params is None:
            self.persistent_params = {}
        else:
            self.persistent_params = persistent_params
        if auth is not None:
            self.auth = auth


    def send_command(self, method, **params):
        """Sends command and returns result. Blocks if result is needed.

        If '_data' is in params it is the file data
        :param method: the pcloud method to call
        :param **params: parameters to be passed to the api, except:
            - _data is the file data
            - _data_progress_callback is the upload callback
            - _noresult - if no result should be returned (you must call
                .get_result manually)
        :returns dictionary returned by the api or None if _noresult is set
        """
        data = params.pop('_data', None)
        data_progress_callback = params.pop('_data_progress_callback', None)
        noresult = params.pop('_noresult', None)
        self.send_command_nb(method,
                             params,
                             data=data,
                             data_progress_callback=data_progress_callback)
        if not noresult:
            return self.get_result()

    def connect(self):
        """Establish connection and return self."""
        if self.socket:
            raise ValueError("maybe connect called twice?")
        self.socket = create_connection(self.server,
                                        self.port,
                                        self.timeout,
                                        self.use_ssl)
        raw = socket.SocketIO(self.socket, 'rwb')
        self.socket._io_refs += 1
        self.fp = PCloudBuffer(raw, raw, 8192)
        return self

    def _prepare_send_request(self, method, params, data_len):
        req = bytearray()
        # actually preallocating would be more efficient but...

        method_name = method.encode('utf-8')
        method_len = len(method_name)
        assert method_len < 128

        if data_len is not None:
            method_len |= 0x80

        req.extend(method_len.to_bytes(1, 'little'))
        if data_len is not None:
            req.extend(data_len.to_bytes(8, 'little'))

        req.extend(method_name)
        req.extend(len(params).to_bytes(1, 'little'))

        for key,value in params.items():
            key = key.encode('utf-8')
            key_len = len(key)
            assert key_len < 64, "Parameter name too long"

            if isinstance(value, int) and value < 0:
                # negative numbers are converted to string
                value = str(value)

            if isinstance(value, list):
                # lists (usually ints) are joined with ,
                value = ','.join(map(str, value))

            if isinstance(value, str):
                value = value.encode('utf-8')

            if isinstance(value, bytes):
                req.extend(key_len.to_bytes(1, 'little'))
                req.extend(key)
                req.extend(len(value).to_bytes(4, 'little'))
                req.extend(value)
            elif isinstance(value, int):
                req.extend((key_len | 0x40).to_bytes(1, 'little'))
                req.extend(key)
                req.extend(value.to_bytes(8, 'little'))
            elif isinstance(value, bool):
                req.extend((key_len | 0x80).to_bytes(1, 'little'))
                req.extend(key)
                req.extend(value.to_bytes(1, 'little'))
            else:
                raise ValueError("Unknown value type {0}".format(type(value)))

        return req

    def _send_raw_data(self, data, data_len, progress_callback):
        """Sends data at the end of send_command."""
        if isinstance(data, io.IOBase):
            written_bytes, to_write = 0, data_len
            while data_len > 0:
                to_write = min(data_len, 8192)
                if to_write != self.fp.write(data.read(to_write)):
                    raise IOError("Mismatch between bytes written and supplied data length")
                data_len -= to_write
                if progress_callback:
                    progress_callback(to_write)
        else:
            written_bytes = self.fp.write(data)
            if written_bytes != data_len:
                raise IOError("Mismatch between bytes written and supplied data length")

    def _determine_data_len(self, data, data_len=None):
        if data is None:
            data_len = None
        elif data_len is None: # and data is not None
            data_len = getattr(data, '__len__', lambda : None)()
            if data_len is None:
                if isinstance(data, io.IOBase) and data.seekable():
                    pos = data.tell()
                    data_len = data.seek(0, io.SEEK_END) - pos
                    data.seek(pos, io.SEEK_SET)
            if data_len is None:
                raise ValueError("Unable to determine data length")
        return data_len

    def send_command_nb(self,
                        method, params,
                        data=None, data_len=None,
                        data_progress_callback=None):
        """Send command without blocking.

        NOTE: params is updated with self.persistent_params

        :param data_len: if not None should be consistent with data.
        :param data_progress_callback: called only for data which is io.IOBase
        """
        data_len = self._determine_data_len(data, data_len)

        params.update(self.persistent_params)

        req = self._prepare_send_request(method, params, data_len)
        assert len(req) < 65536, "Request too long {0}".format(len(req))

        self.fp.write(len(req).to_bytes(2, 'little'))
        self.fp.write(req)

        if data is not None:
            self._send_raw_data(data, data_len, data_progress_callback)

        self.fp.flush()

    def get_result(self):
        """Return the result from a call to the pcloud API."""
        self.fp.read(4) # FIXME: ignores length, seems it is not needed? ASK
        return self._read_object(strings=dict())

    def _read_object(self, strings):
        obj_type = self.fp.read(1)[0]
        # TODO: optimize checks based on actual usage

        if (obj_type <= 3) or (100 <= obj_type <= 149):
            # new string
            if 100 <= obj_type:
                str_len = obj_type - 100
            else:
                str_len = int.from_bytes(self.fp.read(obj_type + 1), 'little')
            string = self.fp.read(str_len).decode('utf-8')
            strings[len(strings)] = string
            return string
        if 4 <= obj_type <= 7:
            # existing string, long index
            return strings[int.from_bytes(self.fp.read(obj_type - 3), 'little')]
        if 8 <= obj_type <= 15:
            # int
            return int.from_bytes(self.fp.read(obj_type - 7), 'little')
        if obj_type == 16:
            # hash
            # FIXME: potential stack overflow
            # FIXME: with the current api, only listfolder(recursive=1)
            result = dict()
            while self.fp.peek(1)[0] != 255:
                key = self._read_object(strings)
                result[key] = self._read_object(strings)
            self.fp.read(1) # consume byte 255
            return result
        if obj_type == 17:
            # list
            # FIXME: potential stack overflow
            # FIXME: with the current api, only listfolder(recursive=1)
            result = []
            while self.fp.peek(1)[0] != 255:
                result.append(self._read_object(strings))
            self.fp.read(1) # consume byte 255
            return result
        if obj_type == 18:
            return False
        if obj_type == 19:
            return True
        if obj_type == 20:
            # data, return data_length
            # be sure to consume the data
            return int.from_bytes(self.fp.read(8), 'little')
        if 150 <= obj_type <= 199:
            # existing string, short index
            return strings[obj_type - 150]
        if 200 <= obj_type <= 219:
            # int, inline
            return obj_type - 200
        #if obj_type == 255: raise StopIteration

        # nothing matched
        raise ValueError("Unknown value returned: {0}".format(obj_type))

    def read_data(self, data_len):
        return self.fp.read(data_len)

    def get_data_stream(self):
        """Returns raw stream, from the socket.

        NOTE: Be careful with this file
        NOTE: Be sure to consume exactly data_len bytes.
        """
        return self.fp

    def write_data(self, writer, data_len, progress_callback=None):
        """Write data from response.

        NOTE: Be sure to consume all of it.
        """
        while data_len > 0:
            to_write = min(8192, data_len)
            assert to_write == writer.write(self.fp.read(to_write))
            data_len -= to_write
            if progress_callback:
                progress_callback(to_write)

    def close(self):
        self.socket.close()

