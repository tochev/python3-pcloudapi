
#!/usr/bin/python3

# PCloudBinaryConnection example
#  - listfolder
#  - upload a file
#  - download it in a zip
#  - perform checksums

import hashlib
import os
import tempfile
from pprint import pprint as pp

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pcloudapi import PCloudAPI, PCloudJSONConnection

def fill_file(f):
    data = b'abcdef\n' * 100000
    f.write(data)
    f.flush()
    f.seek(0, os.SEEK_SET)
    return hashlib.sha1(data).hexdigest()

def main():
    try:
        username, password = open(
                    os.path.expanduser('~/.pcloud_auth_user_pass')
                ).read().strip().split()[:2]
    except:
        username, password = 'user', 'pass'
    #AUTH_TOKEN = open(os.path.expanduser('~/.pcloud_auth')).read().strip()
    #AUTH_TOKEN = 'Ec7QkEjFUnzZ7Z8W2YH1qLgxY7gGvTe09AH0i7V3kX'
    AUTH_TOKEN = None
    TEST_DIR = '/'

    api = PCloudAPI(connection=PCloudJSONConnection)
    if AUTH_TOKEN:
        api.auth = AUTH_TOKEN
    else:
        api.login(username, password)

    with tempfile.NamedTemporaryFile('w+b') as tmpfile1,\
         tempfile.NamedTemporaryFile('w+b') as tmpfile2:

        #api.debug = True
        print("Listing " + TEST_DIR)
        res = api.listfolder(path=TEST_DIR)
        pp(res)
        print()

        filename = TEST_DIR + "test_" + os.path.basename(tmpfile1.name)
        print("Uploading to : " + filename)
        checksum = fill_file(tmpfile1.file)
        res = api.upload(tmpfile1.name, filename)
        pp(res)
        assert res['checksums'][0]['sha1'].lower() == checksum
        print()

        print("Downloading the same file")
        res = api.download(filename, tmpfile2.name)
        pp(res)
        assert checksum == \
                hashlib.sha1(open(tmpfile2.name, 'rb').read()).hexdigest()

    print("All done")

if __name__ == '__main__':
    main()
