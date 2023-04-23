import sys
from setuptools import setup
from os import path, environ

setup_file_dir = path.abspath(path.dirname(__file__))

try:
    with open(path.join(setup_file_dir, "README.md"), encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    print("README.md not found")
    sys.exit(1)

setup(
    name="porkbun-ddns",
    version=environ.get('VERSION'),
    description="A unofficial DDNS-Client for Porkbun domains",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="https://github.com/mietzen/porkbun-ddns",
    author="Nils Stein",
    author_email="github.nstein@mailbox.org",
    license="MIT",
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        "Operating System :: OS Independent",
    ],
    keywords="porkbun ddns",
    packages=["porkbun_ddns"],
    entry_points={
        'console_scripts': ['porkbun-ddns=porkbun_ddns.cli:main']
    },
)
