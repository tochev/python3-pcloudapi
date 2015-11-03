import io
import socket
import ssl


class PCloudBuffer(io.BufferedRWPair):
    """Buffered RW that raises IOError on insufficient bytes for read."""

    def read(self, size=-1):
        result = super().read(size)
        if size != -1 and len(result) != size:
            raise IOError("Requested {0} bytes, got {1}".format(size, len(result)))
        return result


### Misc functionality that should be in python but is not ###

try:
    from ssl import (
            match_hostname,
            create_default_context as ssl_create_default_context
        )

except ImportError:
    import sys
    from requests.packages.urllib3.packages.ssl_match_hostname import match_hostname

    # create_default_context is added in python 3.4
    def ssl_create_default_context(purpose='SERVER_AUTH', *, cafile=None,
                               capath=None, cadata=None):
        """NOTE: Copied from python 3.4

        WARNING: this doesn't do hostname checking, you need backports.ssl_match_hostname

        Create a SSLContext object with default settings.

        NOTE: The protocol and settings may change anytime without prior
            deprecation. The values represent a fair balance between maximum
            compatibility and security.
        """
        if purpose not in ['SERVER_AUTH', 'CLIENT_AUTH']:
            raise ValueError("Unknown purpose " + purpose)

        context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

        # SSLv2 considered harmful.
        context.options |= ssl.OP_NO_SSLv2

        # SSLv3 has problematic security and is only required for really old
        # clients such as IE6 on Windows XP
        context.options |= ssl.OP_NO_SSLv3

        # disable compression to prevent CRIME attacks (OpenSSL 1.0+)
        context.options |= getattr(ssl._ssl, "OP_NO_COMPRESSION", 0)

        if purpose == 'SERVER_AUTH':
            # verify certs and host name in client mode
            context.verify_mode = ssl.CERT_REQUIRED
            # should also check for hostnames but
            #context.check_hostname = True
        elif purpose == 'CLIENT_AUTH':
            # Prefer the server's ciphers by default so that we get stronger
            # encryption
            context.options |= getattr(ssl._ssl, "OP_CIPHER_SERVER_PREFERENCE", 0)

            # Use single use keys in order to improve forward secrecy
            context.options |= getattr(ssl._ssl, "OP_SINGLE_DH_USE", 0)
            context.options |= getattr(ssl._ssl, "OP_SINGLE_ECDH_USE", 0)

            # disallow ciphers with known vulnerabilities
            context.set_ciphers(ssl._RESTRICTED_SERVER_CIPHERS)

        if cafile or capath or cadata:
            context.load_verify_locations(cafile, capath, cadata)
        elif context.verify_mode != ssl.CERT_NONE:
            # no explicit cafile, capath or cadata but the verify mode is
            # CERT_OPTIONAL or CERT_REQUIRED. Let's try to load default system
            # root CA certificates for the given purpose. This may fail silently.
            
            #context.load_default_certs(purpose)
            if sys.platform == "win32":
                for storename in context._windows_cert_stores:
                    context._load_windows_store_certs(storename)
            else:
                context.set_default_verify_paths()
        return context


def create_connection(server=None, port=None, timeout=None, use_ssl=False):
    """Create a socket or a secure ssl socket.

    Hopefully some day such functionality will be included in python3.

    :returns socket
    :rtype socket.SocketType
    """
    # based on socket.create_connection()
    if use_ssl:
        context = ssl_create_default_context()
    err = None
    for af, socktype, proto, canonname, sa in \
            socket.getaddrinfo(server, port, 0, socket.SOCK_STREAM):
        sock = None
        try:
            sock = socket.socket(af, socktype, proto)
            if timeout is not None:
                sock.settimeout(timeout)
            if use_ssl:
                sock = context.wrap_socket(sock, server_hostname=server)
            sock.connect(sa)
            if use_ssl:
                match_hostname(sock.getpeercert(), server)
            return sock

        except socket.error as _:
            err = _
            if sock is not None:
                sock.close()

    if err is not None:
        raise err
    else:
        raise socket.error("getaddrinfo returns an empty list")


