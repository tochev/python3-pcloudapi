#!/usr/bin/env python3
import os
from setuptools import setup

def read(fname):
    # Utility function to read the README file.
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "pcloud",
    version = "0.0.2",
    author = "Tocho Tochev",
    author_email = "tocho@tochev.net",
    description = ("python3 api to access pcloud.com"),
    license = "MIT",
    keywords = "pcloud pcloudapi",
    url = "https://github.com/tochev/python3-pcloudapi",
    packages=['pcloudapi'],
    long_description=read('README.txt'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
    install_requires=read('requirements.txt').strip().splitlines(),
)
