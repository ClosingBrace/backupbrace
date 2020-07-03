# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2015-2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import subprocess
from closingbrace.backuperror import BackupError
from closingbrace.functions import clone_tree
from enum import Enum

class BackupSet:
    """Base for a backup of a single backup item.

    A backup set is created by cloning the previous backup set for the
    same item and then updating the cloned backup set. When cloning the
    previous backup set, hard links are used for the files to avoid
    unnecessary disk use.

    Attributes:
        name (str)    : The set's name.
        state (States): The set's state.
    """

    class States(Enum):
        """Enumeration for the states of a backup set.

        The states are:
            CONFIGURED
            CLONING
            CLONED
            SYNCHRONIZING
            FINISHED
        """

        def __ge__(self, other):
            """The >=-operator."""
            if self.__class__ is other.__class__:
                return self.value >= other.value
            return NotImplemented

        def __gt__(self, other):
            """The >-operator."""
            if self.__class__ is other.__class__:
                return self.value > other.value
            return NotImplemented

        def __le__(self, other):
            """The <=-operator."""
            if self.__class__ is other.__class__:
                return self.value <= other.value
            return NotImplemented

        def __lt__(self, other):
            """The <-operator."""
            if self.__class__ is other.__class__:
                return self.value < other.value
            return NotImplemented

        @classmethod
        def from_string(cls, name):
            """Return the enum member given a string with its name.

            Args:
                name (str): The enum member's name.

            Returns:
                The state as an enum menber.

            Raises:
                ValueError: When the name does not correspond to a
                            member.
            """
            if name == BackupSet.States.CONFIGURED.name:
                return BackupSet.States.CONFIGURED
            elif name == BackupSet.States.CLONING.name:
                return BackupSet.States.CLONING
            elif name == BackupSet.States.CLONED.name:
                return BackupSet.States.CLONED
            elif name == BackupSet.States.SYNCHRONIZING.name:
                return BackupSet.States.SYNCHRONIZING
            elif name == BackupSet.States.FINISHED.name:
                return BackupSet.States.FINISHED
            else:
                raise ValueError("Illegal name ({0}) for enumeration 'States'".
                        format(name))

        CONFIGURED = 0
        CLONING = 1
        CLONED = 2
        SYNCHRONIZING = 3
        FINISHED = 4

    def __init__(self, name, dst_dir=None, state=States.CONFIGURED):
        """Constructor that creates a backup set. When the backup set is
        created for a new backup, `name` and `dst_dir` must be supplied.
        When the backup set is created for an existing backup, `name`
        and `state` have to be supplied. In this case the backup set is
        used read-only.

        Args:
            name (str)         : The set's name.
            dst_dir (str)      : The directory where the backup set will
                                 be created.
            state              : The initial state that the backup set
                                 is in.
        """
        self.name = name
        self.state = state
        self._dst_dir = dst_dir

    def clone(self, src):
        """Clone the last successfull backup of this set.

        Args:
            src (str): The directory of the last successfull backup.
        """
        logging.info("Cloning backup set '{0}' from {1}".format(self.name, src))
        clone_tree(src, self._dst_dir)

    def execute_command(self, command_list):
        """Execute the supplied command to create the backup.

        Args:
            command_list (list): The command to execute, including its
                                 parameters.
        """
        logging.info("Making backup of set '{0}'".format(self.name))
        logging.info("")
        with subprocess.Popen(command_list, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, universal_newlines=True) as command:
            while True:
                out_data = command.stdout.readline()
                if out_data == '':
                    break;
                logging.info(out_data.strip())
            return_code = command.wait(timeout=10)
        logging.info("")
        if return_code == 0:
            logging.info("Finished backup of set '{0}'".format(self.name))
            logging.info("")
        else:
            logging.error("Error making backup of set '{0}' (error code: {1})".
                    format(self.name, return_code))
            logging.info("")
            raise BackupError("{0} subprocess failed with return code {1}".
                    format(command_list[0], return_code))


class LocalDirBackupSet(BackupSet):
    """A backup set of a single local directory tree.

    The backup set is created by cloning the previous backup set for the
    same local directory and then synchronizing the cloned directory
    tree with the local source directory. When cloning the previous
    backup, hard links are used for the files to avoid unnecessary disk
    use. To synchronize the backup directory with the source directory
    the rsync-program/-protocol is used.
    """

    def __init__(self, name, src_dir, dst_dir, skip_entries=None,
            state=BackupSet.States.CONFIGURED):
        """Constructor that creates a new backup set.

        Args:
            name (str)         : The set's name.
            src_dir (str)      : The directory to backup.
            dst_dir (str)      : The directory where the backup set will
                                 be created.
            skip_entries (list): A list of directory and file names that
                                 are to be skipped during backup.
            state              : The initial state that the backup set
                                 is in.
        """
        super().__init__(name, dst_dir, state)
        self._src_dir = src_dir
        self._skip_entries = skip_entries

    def do_backup(self):
        """Make the backup by synchronizing the backup directory with
        the filesystem.
        """
        rsync_cmd_list = ["rsync", "-aAXh", "--delete", "--delete-excluded",
                "--numeric-ids", "--outbuf=Line", "--stats",
                "--itemize-changes"]
        if self._skip_entries is not None:
            rsync_cmd_list.extend(["--exclude=" + f for f in
                self._skip_entries])
        rsync_cmd_list.append(self._src_dir + "/")
        rsync_cmd_list.append(self._dst_dir)
        self.execute_command(rsync_cmd_list)


class RemoteDirBackupSet(BackupSet):
    """A backup of a single remote directory tree.

    The backup set is created by cloning the previous backup set for the
    same remote directory and then synchronizing the cloned directory
    tree with the remote source directory. When cloning the previous
    backup, hard links are used for the files to avoid unnecessary disk
    use. To synchronize the backup directory with the source directory
    the rsync-program/-protocol is used.
    """

    def __init__(self, name, src_dir, dst_dir, remote_host, remote_shell,
            skip_entries=None, state=BackupSet.States.CONFIGURED):
        """Constructor that creates a new backup set.

        Args:
            name (str)         : The set's name.
            src_dir (str)      : The directory to backup.
            dst_dir (str)      : The directory where the backup set will
                                 be created.
            remote_host (str)  : The host containing the files to
                                 backup.
            remote_shell (str) : The command used to log in to a shell
                                 on the remote host (e.g. "ssh -l user).
            skip_entries (list): A list of directory and file names that
                                 are to be skipped during backup.
            state              : The initial state that the backup set
                                 is in.
        """
        super().__init__(name, dst_dir, state)
        self._src_dir = src_dir
        self._remote_host = remote_host
        self._remote_shell = remote_shell
        self._skip_entries = skip_entries

    def do_backup(self):
        """Make the backup by synchronizing the backup directory with
        the filesystem.
        """
        rsync_cmd_list = ["rsync", "-aXhzs", "--delete", "--delete-excluded",
                "--numeric-ids", "--outbuf=Line", "--stats",
                "--itemize-changes"]
        rsync_cmd_list.append("-e" + self._remote_shell)
        if self._skip_entries is not None:
            rsync_cmd_list.extend(["--exclude=" + f for f in
                self._skip_entries])
        rsync_cmd_list.append(self._remote_host + ":" + self._src_dir + "/")
        rsync_cmd_list.append(self._dst_dir)
        self.execute_command(rsync_cmd_list)
