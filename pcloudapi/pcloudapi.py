#!/usr/bin/env python3

import hashlib
import re
import requests
import sys
from pprint import pprint as pp

from .exceptions import PCloudException
from .connection import AbstractPCloudConnection
from .pcloudbin import PCloudBinaryConnection


PCLOUD_SERVER_SUFFIX = '.pcloud.com'  # only allow downloads from pcloud servers


class PCloudAPIMetaclass(type):

    @classmethod
    def __prepare__(cls, name, bases):
        methods = """
                  getaudiolink getpubziplink deletefolder getvideolink
                  file_checksum cancelsharerequest getziplink currentserver
                  sendverificationemail file_lock file_pwrite getpublinkdownload
                  file_truncate getpubthumblink getthumb listpublinks listshares
                  getpubaudiolink savepubthumb deletefile lostpassword
                  revertrevision resetpassword acceptshare userinfo diff
                  feedback uploadprogress listrevisions copypubfile copytolink
                  verifyemail getdigest file_write renamefile getthumbslinks
                  file_close createuploadlink notifyuploadlink getfilelink
                  changepassword savezip getpubthumb getthumblink file_pread
                  renamefolder copyfile file_seek gettreepublink deletepublink
                  checksumfile verifyitunespurchase supportedlanguages
                  gethlslink uploadfile file_open savepubzip showpublink
                  listplshort getfolderpublink uploadtolink createfolder
                  savethumb file_pread_ifmod setlanguage getpubzip
                  deleteuploadlink showuploadlink getzip listitunesproducts
                  sharefolder register declineshare sharerequestinfo
                  listfolder file_read file_size downloadfile invite
                  getcertificate changeuploadlink changeshare changepublink
                  listuploadlinks normalizehash getpubthumbslinks
                  uploadlinkprogress removeshare getfilepublink
                  deletefolderrecursive
                  """.strip().split()
        return {method :
                    (lambda method :
                        (lambda self, **kwargs:
                            self.make_request(method, **kwargs))
                    )(method)
                for method in methods}

class PCloudAPI(metaclass=PCloudAPIMetaclass):
    """A stripped down of the PCloudAPI.

    All pcloud api methods are available as .method shortcut for
    make_request(method, ...).

    Exceptions that can be raised during correct operation:
        (PCloudException, requests.RequestException, IOError)
    """

    def __init__(self, connection=PCloudBinaryConnection, debug=False):
        """Initializes the API.

        connection can be either a concrete class of AbstractPCloudConnection
        or an AbstractPCloudConnection-derived object.
        If debug is true dumps the parameters
        """
        if issubclass(connection, AbstractPCloudConnection):
            connection = connection().connect()
        assert isinstance(connection, AbstractPCloudConnection), \
                ("PCloud instance expected, got %s" % connection.__class__)
        self.connection = connection
        self.debug = debug

    def make_request(self, method, check_result=True, **params):
        """Performs send_command through the connection.

        :param method: the method to call
        :param **params: the parameters for the connection
        :param _data: file data in the form of bytes or stream of bytes
        :param check_result: check that the ['result'] == 0 and raise if not
        :returns response in the form of a dictionary
        :raises PCloudException
        """
        if self.debug:
            pp((method, params), stream=sys.stderr)
        response = self.connection.send_command(method, **params)
        if self.debug:
            pp(response, stream=sys.stderr)
        if check_result:
            result = response.get('result', None)
            if result != 0:
                raise PCloudException(result_code=result)
        return response

    def login(self, username, password):
        """Perform login though the connection.

        :param username: username
        :param password: password
        :returns authentication token

        Also sets .auth and in turn .connection.auth to the returned token.
        """
        digest = self.make_request('getdigest')['digest']
        passworddigest = hashlib.sha1(
                            (password +
                             hashlib.sha1(username.lower().encode('utf-8')
                                 ).hexdigest().lower() +
                             digest).encode('utf-8')
                        ).hexdigest()
        auth = self.make_request('userinfo',
                                 getauth=1,
                                 username=username,
                                 digest=digest,
                                 passworddigest=passworddigest)['auth']
        self.auth = auth
        return auth

    def get_folderid(self, path):
        return self.make_request('listfolder',
                                 path=path,
                                 nofiles=1,
                                 )['metadata']['folderid']

    def create_directory(self, path):
        """Creates directory recursively.

        Does not raise any errors if the file exists.
        """
        if path == '/':
            return # HACK: pcloud fails otherwise
        if path == "":
            return # nothing to do
        # really ugly, sadly there is no mkdir -p
        try:
            self.make_request('createfolder', path=path)
        except PCloudException as e:
            if e.result_code == 2002:
                # parent does not exist
                # stack danger
                self.create_directory(re.sub('(^/?|/+)[^/]+/?$', '', path))
                self.make_request('createfolder', path=path)
            elif e.result_code == 2004:
                # file/folder exists, assume everything is OK
                pass
            else:
                raise

    def download(self, remote_path, local_path, progress_callback=None,
                 enforced_server_suffix=PCLOUD_SERVER_SUFFIX):
        """Downloads file from remote_path to local_path.

        :param progress_callback: called each time with the number of bytes
            written in the iteration
        :param enforced_server_suffix: only allow downloads from servers having
            the expected suffix (this together with ssl prevents a downloading
            of non-pcloud controlled resource)
        :returns pcloud api response
        """
        response = self.make_request('getfilelink',
                                     path=remote_path,
                                     forcedownload=1)
        server = response['hosts'][0]  # should be the closest server
        if enforced_server_suffix:
            if '/' in server or not server.lower().endswith(enforced_server_suffix):
                raise ValueError(
                    "Received download server {!r} which does not match expected suffix {!r}".format(
                        server, enforced_server_suffix
                    )
                )
        url = "{protocol}://{server}:{port}{path}".format(
                protocol=self.connection.use_ssl and 'https' or 'http',
                server=server,
                port=self.connection.use_ssl and 443 or 80,
                path=response['path']
            )
        r = requests.get(url, stream=True, allow_redirects=False, timeout=self.connection.timeout)
        r.raise_for_status()

        with open(local_path, 'wb') as fd:
            for chunk in r.iter_content(8192):
                written = fd.write(chunk)
                if progress_callback:
                    progress_callback(written)

        return response

    def upload(self, local_path, remote_path,
               create_parent=True, progress_callback=None):
        """Uploads file from local_path to remote_path.

        :param create_parent: whether to create the parent
        :param progress_callback: called each time with the number of bytes
            written in the iteration
        :returns pcloud api response
        """
        remote_dir, filename = remote_path.rsplit('/', 1)
        if create_parent:
            self.create_directory(remote_dir)
        with open(local_path, 'rb') as fd:
            response = self.make_request('uploadfile',
                                         _data=fd,
                                         path=remote_dir or '/',
                                         filename=filename,
                                         nopartial=1,
                                         _data_progress_callback=progress_callback)
            if not response['fileids']:
                raise PCloudException("Upload failed, no files reported back")
        return response

    def exists_file(self, remote_path):
        """Checks if file exists. Does not work for folders."""
        try:
            self.make_request('checksumfile',
                              path=remote_path)
            return True
        except PCloudException as e:
            if e.result_code in [2002, 2009]:
                return False
            else:
                raise

    def delete_file(self, remote_path):
        """Delete file at remote_path."""
        try:
            self.make_request('deletefile',
                              path=remote_path)
        except PCloudException as e:
            if e.result_code in [2002, 2009]:
                return False
            else:
                raise

    @property
    def auth(self):
        return self.connection.auth
    @auth.setter
    def auth(self, auth):
        self.connection.auth = auth

