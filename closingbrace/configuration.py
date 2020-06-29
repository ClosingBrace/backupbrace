# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2015-2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import textwrap
from closingbrace.backuperror import BackupError

class Configuration:
    """Configuration for the backup program.

    The configuration is read from a json-configuration file. This
    configuration file is versioned. The program only supports
    configuration files in the version 2.0 format.

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
        if (int(self.version_major) == 2) and (int(self.version_minor) >= 0):
            # We have a supported version
            return
        raise BackupError("Configuration file format not supported. Found "
                "version {0}, only supporting versions 2.x".
                format(self._configuration["version"]))

    @classmethod
    def print_configuration_format(cls):
        """Print the configuration file format.
        """
        print(textwrap.dedent("""\
            The configuration for the backup program is stored in a JSON-file.
            The file is versioned. This version of the program uses version
            2.0 of the configuration file. It is also compatible with any other
            2.x version of the configuration file.

            Version 2.0 supports the backup of local and remote files and
            directories to a local backup directory.

            A sample version 2.0 configuration file looks as follows:

                {
                   "version": "2.0",
                   "backup-dir": "/path/to/backup/dir",
                   "backup-sets": [
                      {
                         "set-name": "set_1",
                         "type": "local dir"
                         "source-dir": "/path/to/source_1",
                         "skip-entries": [
                            "entry_1",
                            "entry_2",
                            "entry_3"
                         ]
                      },
                      {
                         "set-name": "set_2",
                         "type": "local dir"
                         "source-dir": "/path/to/source_2"
                      },
                      {
                         "set-name": "set_3",
                         "type": "remote dir"
                         "remote-shell": "ssh -l user",
                         "remote-host": "server_name",
                         "source-dir": "/path/to/source_3"
                      }
                   ]
                }

            The configuration is contained in a single, unnamed JSON object. The
            object contains the following name/value pairs:
            - `version`    : The string "2.0".
            - `backup-dir` : A string that contains the base directory where the
                             backups will go. This directory must exist prior to
                             the execution of the backup program.
            - `backup-sets`: An array of backup sets.

            The backup sets are objects that contain the following name/value
            pairs:
            - `set-name`    : A string identifying the backup set. This set name
                              will be used to create a subdirectory in
                              `backup-dir`.
            - `type`        : The type of backup, either 'local dir' or
                              'remote dir'.
            - `remote-shell`: (only when `type` is 'remote dir') The remote
                              shell to use for connecting with the remote host.
                              The string includes the options that the remote
                              shell needs to connect to the remote host.
            - `remote-host` : (only when `type` is 'remote dir') The remote host
                              to connect to. This can include a remote user
                              (with the syntax <user>@<host>) that the remote
                              rsync process will use to execute its task.
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
