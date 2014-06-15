#!/usr/bin/env python3

# PCloudBinaryConnection example
#  - listfolder
#  - upload a file
#  - download it in a zip
#  - perform checksums

import hashlib
import os
import tempfile
import zipfile
from pprint import pprint as pp

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pcloudapi import PCloudBinaryConnection

def fill_file(f):
    data = b'abcdef\n' * 100000
    f.write(data)
    f.seek(0, os.SEEK_SET)
    return hashlib.sha1(data).hexdigest()

def main():
    try:
        AUTH_TOKEN = open(os.path.expanduser('~/.pcloud_auth')).read().strip()
    except:
        AUTH_TOKEN = 'Ec7QkEjFUnzZ7Z8W2YH1qLgxY7gGvTe09AH0i7V3kX'
    TEST_DIR = '/'
    with PCloudBinaryConnection(persistent_params={"auth": AUTH_TOKEN}) as api,\
        tempfile.NamedTemporaryFile('w+b') as tmpfile1,\
        tempfile.NamedTemporaryFile('w+b') as tmpfile2:

        print("Listing " + TEST_DIR)
        res = api.send_command('listfolder', path=TEST_DIR)
        pp(res)
        assert res['result'] == 0
        print()

        filename = "test_" + os.path.basename(tmpfile1.name)
        print("Uploading to : " + filename)
        checksum = fill_file(tmpfile1.file)
        res = api.send_command('uploadfile',
                            path=TEST_DIR,
                            filename=filename,
                            _data=tmpfile1.file)
        pp(res)
        assert res['result'] == 0
        assert res['checksums'][0]['sha1'].lower() == checksum
        fileid = res['fileids'][0]
        print()

        print("Downloading the same file")
        # can also be done with fileops
        # see https://docs.pcloud.com/methods/fileops/index.html
        res = api.send_command('getzip', fileids=[fileid])
        pp(res)
        assert res['result'] == 0
        assert 'data' in res
        api.write_data(tmpfile2, res['data'])
        tmpfile2.seek(0, os.SEEK_SET)
        with zipfile.ZipFile(tmpfile2, 'r') as zip_file:
            assert checksum == hashlib.sha1(zip_file.read(filename)).hexdigest()
        print()


if __name__ == '__main__':
    main()
