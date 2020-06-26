# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from setuptools import setup


with open("README.md", "r") as fh:
    long_description = fh.read()


setup(
    name='closingbrace_backupbrace',
    version='0.1.0',
    description='A script to create backups of a Linux system',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/closingbrace/backupbrace",
    author='Hans Vredeveld',
    author_email='github@closingbrace.nl',
    license='Mozilla Public License 2.0',
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Operating System :: POSIX :: Linux",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
    ],
    packages=['closingbrace'],
    python_requires='~=3.6',
    install_requires=['python-dateutil'],
    entry_points={
        'console_scripts': [
            'backupbrace=closingbrace.backup:run',
        ],
    },
    zip_safe=False,
)
