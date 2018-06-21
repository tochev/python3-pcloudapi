=========
PCloudAPI
=========

PCloudAPI is a python3 library for accessing the pcloud.com API.
It supports both the binary and the json protocols.

Homepage: https://github.com/tochev/python3-pcloudapi

Examples
========

    >>> from pcloudapi import PCloudAPI
    >>> api = PCloudAPI()
    >>> api.login('pcloud_account@example.com', '1337pass')
    'Ec7QkEjFUnzZ7Z8W2YH1qLgxY7gGvTe09AH0i7V3kX'
    >>> api.make_request('listfolder', path='/')['metadata']['icon']
    'folder'
    >>> api.upload('/tmp/quotes.txt', '/test.txt')


For more see examples/

Status
======

This is a working prototype and is highly experimental. Things might change.
Use at your own risk.

The JSON connection is to be considered safer, although on upload it reads the
whole file into memory which can be a problem (this is due to a limitation of
the python requests library).

Installation
============

    sudo apt-get install python3 python3-requests python3-setuptools
    git clone https://github.com/tochev/python3-pcloudapi
    cd pcloudapi
    python3 setup.py install
