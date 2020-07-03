# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2015-2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
from closingbrace.backup import Backup
from closingbrace.backuperror import BackupError
from datetime import datetime

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
        self._load_backups()

    def new_backup(self, directory=None):
        """Create a new backup.

        The backup is created as a subdirectory of the managers
        directory. This subdirectory is given by the `directory`
        argument. If `directory` is None, the current system time is
        used to create an ISO timestamp string, which is used for the
        directory name.

        Args:
            directory (str): The subdirectory in which the backup will
                             be created, or None.

        Returns:
            The newly created backup.
        """
        if directory is None:
            directory = datetime.now().replace(microsecond=0).isoformat()
        backup = Backup(os.path.join(self._directory, directory))
        self._backups.append(backup)
        return backup

    def find_latest_set(self, set_name, states):
        """Find the latest backup set with a state that is in `states`.

        Args:
            set_name (str): The name of the backup set to search for.
            states (list) : A list of states (from BackupSet.States).

        Returns:
            The location (directory) of the latest set or None when
            there is no set with `set_name` in one of the states in
            `states`.
        """
        latest_location = None
        latest_timestamp = datetime.min
        for backup in self._backups:
            location = backup.find_set_location(set_name, states)
            if location is not None:
                if backup.timestamp > latest_timestamp:
                    latest_timestamp = backup.timestamp
                    latest_location = location
        return latest_location

    def _load_backups(self):
        """Load the existing backups under the base directory.
        """
        backup_dirs = [d for d in os.listdir(self._directory)
                if os.path.isdir(os.path.join(self._directory, d))]
        for dir_ in backup_dirs:
            try:
                self._backups.append(Backup.open(os.path.join(self._directory,
                    dir_)))
            except BackupError:
                # skip directory when it is not a backup
                pass
