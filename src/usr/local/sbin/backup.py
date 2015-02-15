#!/usr/bin/python3
"""Backup program.

This program makes backups of a Linux system to a backup directory. The
backup directory must be locally accessible to the backup program, and
the backup directory must be located on a filesystem that supports
inodes. Typically the backup directory is on a mounted USB harddisk.

Each new backup is created as a subdirectory of the backup directory,
where the timestamp of the backup start is used to name the
subdirectory. A backup starts as a copy of the last backup. In this copy
directories are created anew, but files are hardlinked with the file in
last backup. After the copy, the backup's directory structure is
synchronized with the source directory that it is to be a backup of.
Files that changed between the last backup and the current backup run,
are replaced by their source. This breaks the hardlink between the last
and current backup, so that the file in the last backup is not changed.
Files that did not change between the last backup and the current run,
are left alone. The hardlink will stay intact.

The program support optional command line arguments. The arguments
supported are:
-h, --help            show this help message and exit
-v, --version         show program's version number and exit
-c CONFFILE, --config CONFFILE
                      the backup's configuration file
"""

PROGRAM_VERSION = "0.1"

import argparse
import json
import os
import sys
from datetime import datetime

class BackupError(Exception):
    """Base exception for the backup program.

    This exception is raised when an error occurs in the backup program.
    It may be derived for more specific errors.
    """

    def __init__(self, reason):
        """Constructor that takes the reason for the error as argument.

        Args:
            reason (str): The reason for raising the error.
        """
        self._reason = reason

    def __str__(self):
        """String representation of the error."""
        return self._reason


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
        parser.add_argument("-v", "--version", action="version",
                version="%(prog)s v" + PROGRAM_VERSION)
        parser.add_argument("-c", "--config", dest="conffile",
                default=self.conf_file, help="the backup's configuration file")
        parser.parse_args(namespace=self)


class Configuration:
    """Configuration for the backup program.

    The configuration is read from a json-configuration file. This
    configuration file is versioned. The program currently only supports
    configuration files in the version 1.0 format.

    The configuration file formats are:

    version 1.0:
        The configuration is one unnamed object. This object has the
        following members:
        - version: The configuration's version-string: `1.0`.
        - backup-dir: The base directory where the backups will go. This
          directory must exist prior to the execution of the backup
          program.
        - backup-sets: An array of backup sets.

        The backup sets are objects with the following members:
        - set-name: A string identifying the backup set.
        - source-dir: The directory to backup.
        - skip-entries: (optional) An array of directory and file names
          that are to be skipped during backup.

        Each backup set will be backed up to the directory
        `<backup-dir>/<timestamp>/<set-name>`, where the timestamp is
        fixed the moment the program started. Directories and files in
        skip-entries will be excluded from the backup, indepent from
        where they appear below the source-dir.

    Attributes:
        version_major (str): The major part of the configuration's
                             version.
        version_minor (str): The minor part of the configuration's
                             version.
        """

    def __init__(self, conf_file):
        """Constructor that takes the path to the configuration file as
        argument.

        The configuration is loaded from the json configuration file at
        `conf_file`.

        Args:
            conf_file (str): Path to the configuration file.

        Raises:
            BackupError: When the configuration file does not exist or
                         could otherwise not be opened, or when the
                         configuration file could not be parsed.
        """
        try:
            with open(conf_file, "r") as fp:
                self._configuration = json.load(fp)
            self._extract_version()
        except IOError as err:
            raise BackupError(
                    "Could not open configuration file '{0}' ({1})".format(
                        err.filename, err.strerror))
        except ValueError as err:
            raise BackupError("Could not parse configuration ({0})".
                    format(err))

    def get_param(self, key):
        """Get the parameter `key` from the configuration.

        Args:
            key (str): The key to retrieve.

        Returns:
            The value corresponding to `key`.

        Raises:
            KeyError: When `key` does not exist in the configuration.
        """
        return self._configuration[key]

    def _extract_version(self):
        """Extract the version from the configuration into the
        attributes version_major and version_minor.

        Raises:
            BackupError: When the configuration does not have a version
                         parameter, or when the version parameter could
                         not be split into two separate strings.
        """
        try:
            version = self._configuration["version"]
            self.version_major, self.version_minor = version.split(".")
        except KeyError as err:
            raise BackupError("Missing configuration parameter '{0}'".format(
                err.args[0]))
        except ValueError as err:
            raise BackupError(
                    "Error parsing configuration's version string ({0})".
                    format(err))


if __name__ == "__main__":
    env = Environment()
    try:
        conf = Configuration(env.conffile)
    except BackupError as e:
        print("Error: " + e.__str__())
        sys.exit(1)
