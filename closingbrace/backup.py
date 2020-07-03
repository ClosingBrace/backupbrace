# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2015-2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
import os
from closingbrace.backuperror import BackupError
from closingbrace.backupset import BackupSet
from closingbrace.backupset import LocalDirBackupSet, RemoteDirBackupSet
from closingbrace.jsoncoders import TimestampEncoder, decode_state_json
from datetime import datetime

class Backup:
    """A single backup.

    A backup consists of one or more backup sets.
    """

    # The name of the file in which the backup's state is stored.
    _STATE_FILE = "backup.state"

    def __init__(self, directory, new=True):
        """Constructor that opens or creates a backup in `directory`.
        When a backup is created the backup directory must not yet
        exist, while when an existing backup is opened it must exist.

        Args:
            directory (str): The backup directory.
            new (boolean)  : True when this creates a new backup.

        Raises:
            BackupError: When the backup directory already exists and
                         new is True, or when the backup directory does
                         not exist and new is False.
        """
        self.timestamp = datetime.now().replace(microsecond=0)
        self._sets = []
        self._backup_dir = directory
        if new == True:
            try:
                os.mkdir(directory)
                self._save_state()
                logging.basicConfig(filename="{0}/backup.log".format(directory),
                        format="%(asctime)s %(levelname)s: %(message)s",
                        level=logging.INFO)
                logging.info("Backup started")
                logging.info("")
            except OSError:
                raise BackupError("Backup directory '{0}' already exists".
                        format(directory))
        else:
            try:
                self._load_state()
            except OSError:
                raise BackupError("Backup directory '{0}' does not exist".
                        format(directory))

    @classmethod
    def open(cls, directory):
        """Open the backup at `directory`. The state file in `directory`
        is read and used to set the timestamp and backup sets of the
        backup. A backup that is opened can only be used to read
        information from about when the backup was made and what sets
        were included in the backup and in what state these sets are.

        Args:
            directory (str): The backup directory.

        Returns:
            An opened backup.
        """
        return Backup(directory, new=False)

    def add_local_dir_set(self, name, src_dir, skip_entries):
        """Add a backup set for a local directory tree to the backup.

        Args:
            name (str)         : The set's name.
            src_dir (str)      : The directory to backup.
            skip_entries (list): A list of directory and file names that
                                 are to be skipped during backup.
        """
        self._sets.append(
                LocalDirBackupSet(name, src_dir,
                    os.path.join(self._backup_dir, name), skip_entries))
        self._save_state()
        logging.info("Backup set '{0}' added".format(name))

    def add_remote_dir_set(self, name, src_dir, host, shell, skip_entries):
        """Add a backup set for a remote directory tree to the backup.

        Args:
            name (str)         : The set's name.
            src_dir (str)      : The directory to backup.
            host (str)         : The host containing the directory to
                                 backup.
            shell (str)        : The command to log in to a shell on
                                 host.
            skip_entries (list): A list of directory and file names that
                                 are to be skipped during backup.
        """
        self._sets.append(
                RemoteDirBackupSet(name, src_dir,
                    os.path.join(self._backup_dir, name), host, shell,
                    skip_entries))
        self._save_state()
        logging.info("Backup set '{0}' added".format(name))

    def find_set_location(self, set_name, states):
        """Find the location of the backup set with the name `set_name`
        and a state that is in `states`.

        Args:
            set_name (str): The name of the backup set to search for.
            states (list) : A list of states (from BackupSet.States).

        Returns:
            The location (directory) of the set or None when there is no
            set with `set_name` in one of the states in `states`.
        """
        set_list = [ b for b in self._sets
                if b.name == set_name and b.state in states]
        if set_list:
            return os.path.join(self._backup_dir, set_name)
        return None

    def create(self, copy_source_finder):
        """Create the backup. For each backup set, copy it from the last
        successfull backup set and then synchronize it with the
        filesystem.

        Args:
            copy_source_finder (fnc): Function to find the backup set to
                                      copy from. The function takes two
                                      arguments: a set name and a list
                                      of states that the set must be in.
        """
        logging.info("")
        for backup_set in self._sets:
            logging.info("===================================================")
            copy_src = copy_source_finder(backup_set.name,
                    [BackupSet.States.CLONED, BackupSet.States.SYNCHRONIZING,
                        BackupSet.States.FINISHED])
            if copy_src is not None:
                backup_set.state = BackupSet.States.CLONING
                self._save_state()
                backup_set.clone(copy_src)
                backup_set.state = BackupSet.States.CLONED
                self._save_state()
            backup_set.state = BackupSet.States.SYNCHRONIZING
            self._save_state()
            backup_set.do_backup()
            backup_set.state = BackupSet.States.FINISHED
            self._save_state()

    def _save_state(self):
        """Save the backup's state.

        The backup's state consists of the time it was created and all
        backup sets with their state. The state is save in a file in the
        backup directory.
        """
        sets = {set_.name: set_.state.name for set_ in self._sets}
        state_file = os.path.join(self._backup_dir, Backup._STATE_FILE)
        with open(state_file, "w") as fp:
            json.dump({"timestamp": self.timestamp, "sets": sets}, fp, indent=4,
                    cls=TimestampEncoder)

    def _load_state(self):
        """Load the backup's state.
        """
        state_file = os.path.join(self._backup_dir, Backup._STATE_FILE)
        with open(state_file, "r") as fp:
            backup_state = json.load(fp, object_hook=decode_state_json)
            self._sets = [BackupSet(name, state=backup_state['sets'][name])
                    for name in backup_state['sets']]
            self.timestamp = backup_state['timestamp']
