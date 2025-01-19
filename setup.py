from setuptools import setup
from os import environ

setup(
    version=environ.get('VERSION'),
)
