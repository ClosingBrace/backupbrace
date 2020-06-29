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
import shutil
import subprocess
import sys
import dateutil.parser
from closingbrace.backuperror import BackupError
from closingbrace.configuration import Configuration
from closingbrace.environment import Environment
from datetime import datetime
from enum import Enum

class TimestampEncoder(json.JSONEncoder):
    """Custom JSON encoder that encodes datetime objects as their
    ISO-8601 string.
    """

    def default(self, obj):
        """Encoding function.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


def decode_state_json(dct):
    """Object hook for decoding the saved state from JSON. In the JSON
    file, the timestamp is a string. This is converted to a datetime
    object. Also in the JSON file, the backup sets' states are strings.
    These are converted to instances of the BackupSet.States
    enumeration.

    Args:
        dct: The dictionary as decoded by the default decoder.

    Returns:
        A dictionary with the timestamp as a datetime object and the
        sets using the state enumeration.
    """
    if 'timestamp' in dct:
        dct['timestamp'] = dateutil.parser.parse(dct['timestamp'])
    if 'sets' in dct:
        sets = dct['sets']
        dct['sets'] = {key : BackupSet.States.from_string(sets[key])
                for key in sets}
    return dct


def clone_tree(src, dst):
    """Recursively clone a directory tree.

    (Adapted from shutil.copytree. It differs from copytree in that it
    also copies owner and group information and that it makes hard links
    for files.)

    The destination directory must not already exist. If exception(s)
    occur, a BackupError is raised with a list of reasons.

    Symbolic links in the source tree result in symbolic links in the
    destination tree.

    Args:
        src (str) : The source directory to clone.
        dst (str) : The destination to clone to. It must not yet exist.

    Raises:
        BackupError: When there were errors during cloning.
    """
    def copy_all_stat(src, dst, follow_symlinks=True):
        """Copy all stat info (mode bits, atime, mtime, flags, uid, gid)
        from src to dst.

        If the optional flag `follow_symlinks` is not set, symlinks
        aren't followed if and only if both `src` and `dst` are
        symlinks.

        Args:
            src (str)             : The source to retrieve stats from.
            dst (str)             : The destination to set stats on.
            follow_symlinks (bool): If symlinks should be dereferenced.
        """
        stat = os.stat(src, follow_symlinks=follow_symlinks)
        os.chown(dst, stat.st_uid, stat.st_gid, follow_symlinks=follow_symlinks)
        shutil.copystat(src, dst, follow_symlinks=follow_symlinks)

    names = os.listdir(src)

    os.makedirs(dst)
    errors = []
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
                copy_all_stat(srcname, dstname, follow_symlinks=False)
            elif os.path.isdir(srcname):
                clone_tree(srcname, dstname)
            else:
                os.link(srcname, dstname)
        # catch the BackupError from the recursive clone_tree so that we
        # can continue with other files
        except BackupError as err:
            errors.extend(err.args[0])
        except OSError as why:
            errors.append((srcname, dstname, str(why)))
    try:
        copy_all_stat(src, dst)
    except OSError as why:
        errors.append((src, dst, str(why)))
    if errors:
        raise BackupError(errors)


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


def run():
    env = Environment()
    if (env.conf_format):
        Configuration.print_configuration_format()
        sys.exit(0)
    try:
        conf = Configuration(env.conffile)
        manager = BackupManager(conf.get_param("backup-dir"))
        backup = manager.new_backup()
        for backup_set in conf.get_param("backup-sets"):
            if (backup_set["type"] == "local dir"):
                name = backup_set["set-name"]
                src_dir = backup_set["source-dir"]
                if "skip-entries" in backup_set:
                    skip_entries = backup_set["skip-entries"]
                else:
                    skip_entries = None
                backup.add_local_dir_set(name, src_dir, skip_entries)
            elif (backup_set["type"] == "remote dir"):
                name = backup_set["set-name"]
                src_dir = backup_set["source-dir"]
                remote_host = backup_set["remote-host"]
                remote_shell = backup_set["remote-shell"]
                if "skip-entries" in backup_set:
                    skip_entries = backup_set["skip-entries"]
                else:
                    skip_entries = None
                backup.add_remote_dir_set(name, src_dir, remote_host,
                        remote_shell, skip_entries)
        backup.create(manager.find_latest_set)
    except BackupError as e:
        logging.error("Backup incomplete due to error:")
        logging.error("  {0}".format(e))
        sys.exit(1)
