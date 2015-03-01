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
import textwrap
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
        parser.add_argument("-f", "--conf-format", action="store_true",
                help="show help about the configuration file format and exit")
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
            self._check_version()
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

    def _check_version(self):
        """Check if the configuration format version is supported.

        Raises:
            BackupError: When the configuration format version is not
                         supported.
        """
        if (int(self.version_major) == 1) and (int(self.version_minor) >= 0):
            # We have a supported version
            return
        raise BackupError("Configuration file format not supported. Found "
                "version {0}, only supporting versions 1.x".
                format(self._configuration["version"]))

    @classmethod
    def print_configuration_format(cls):
        """Print the configuration file format.
        """
        print(textwrap.dedent("""\
            The configuration for the backup program is stored in a JSON-file.
            The file is versioned. This version of the program uses version
            1.0 of the configuration file. It is also compatible with any other
            1.x version of the configuration file.

            Version 1.0 supports only the backup of local files and directories
            to a local backup directory.

            A sample version 1.0 configuration file looks as follows:

                {
                   "version": "1.0",
                   "backup-dir": "/path/to/backup/dir",
                   "backup-sets": [
                      {
                         "set-name": "set_1",
                         "source-dir": "/path/to/source_1",
                         "skip-entries": [
                            "entry_1",
                            "entry_2",
                            "entry_3"
                         ]
                      },
                      {
                         "set-name": "set_2",
                         "source-dir": "/path/to/source_2"
                      },
                   ]
                }

            The configuration is contained in a single, unnamed JSON object. The
            object contains the following name/value pairs:
            - `version`    : The string "1.0".
            - `backup-dir` : A string that contains the base directory where the
                             backups will go. This directory must exist prior to
                             the execution of the backup program.
            - `backup-sets`: An array of backup sets.

            The backup sets are objects that contain the following name/value
            pairs:
            - `set-name`    : A string identifying the backup set. This set name
                              will be used to create a subdirectory in
                              `backup-dir`.
            - `source-dir`  : A string with the absolute path to the directory
                              to backup.
            - `skip-entries`: (optional) An array of strings that are directory
                              and file names which are to be skipped during
                              backup.

            Each backup set will be backed up to the directory
            `backup-dir`/<timestamp>/`set-name`, where the timestamp is fixed
            the moment the program started. Directories and files in
            `skip-entries` will be excluded from the backup, indepent from where
            they appear below the source directory."""))


class BackupManager:
    """A manager that manages all the backups in a single base
    directory.

    A backup is located in a directory that is made up of a base
    directory and a timestamp as subdirectory. All the backups in a
    single base directory are managed by the same BackupManager.
    """

    def __init__(self, directory):
        """Constructor that takes the base directory as argument.

        All backups under the base directory will be managed by this
        instance of the BackupManager. It is an error when the
        `directory` refers to a non-existent directory.

        Args:
            directory (str): The base directory of the backups that will
                             managed.

        Raises:
            BackupError: When the base directory does not exist.
        """
        self._directory = directory
        if not os.path.isdir(directory):
            raise BackupError(
                    "Cannot manage backups in non-existent directory '{0}'".
                    format(directory))
        self._backups = []


if __name__ == "__main__":
    env = Environment()
    if (env.conf_format):
        Configuration.print_configuration_format()
        sys.exit(0)
    try:
        conf = Configuration(env.conffile)
        manager = BackupManager(conf.get_param("backup-dir"))
    except BackupError as e:
        print("Error: " + e.__str__())
        sys.exit(1)
