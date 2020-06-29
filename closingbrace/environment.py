# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2015-2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

PROGRAM_VERSION = "0.2"

import argparse

class Environment:
    """The operating environment of the program.

    An Environment object contains information about the operating
    environment.

    Attributes:
        conf_file (str): The configuration file for the program.
    """

    def __init__(self):
        """Default constructor.

        This sets the information that is maintained in an Environment
        object.
        """
        self.conf_file = "/etc/backupbrace.conf"
        self._parse_command_line()

    def _parse_command_line(self):
        """Parse command line arguments.

        The command line arguments that are parsed are added to the
        parsing operating environment instance.
        """
        parser = argparse.ArgumentParser(
                description="Make a backup of the system.")
        parser.add_argument("-f", "--conf-format", action="store_true",
                help="show help about the configuration file format and exit")
        parser.add_argument("-v", "--version", action="version",
                version="%(prog)s v" + PROGRAM_VERSION)
        parser.add_argument("-c", "--config", dest="conffile",
                default=self.conf_file, help="the backup's configuration file")
        parser.parse_args(namespace=self)
