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

PROGRAM_VERSION = "0.2"

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import textwrap
import dateutil.parser
from datetime import datetime
from enum import Enum

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


class BackupSet:
    """A backup of a single directory tree.

    A backup set is created by cloning the previous backup set for the
    same directory and then synchronizing the cloned directory tree with
    the source directory. When cloning the previous backup, hard links
    are used for the files to avoid unnecessary disk use. To synchronize
    the backup directory with the source directory the rsync-program/
    -protocol is used.

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

    def __init__(self, name=None, src_dir=None, dst_dir=None, skip_entries=None,
            state=States.CONFIGURED):
        """Constructor that creates a backup set. When the backup set is
        created for a new backup, `name`, `src_dir` and `dst_dir` must
        be supplied. `skip_entries` should also be supplied if there are
        entries in the `src_dir` that are to be skipped. When the backup
        set is created for an existing backup, only `name` and `state`
        have to be supplied. In this case the backup set is used
        read-only.

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
        self.name = name
        self.state = state
        self._src_dir = src_dir
        self._dst_dir = dst_dir
        self._skip_entries = skip_entries

    def clone(self, src):
        """Clone the last successfull backup of this set.

        Args:
            src (str): The directory of the last successfull backup.
        """
        logging.info("Cloning backup set '{0}' from {1}".format(self.name, src))
        clone_tree(src, self._dst_dir)

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
        logging.info("Making backup of set '{0}'".format(self.name))
        logging.info("")
        with subprocess.Popen(rsync_cmd_list, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, universal_newlines=True) as rsync_cmd:
            while True:
                out_data = rsync_cmd.stdout.readline()
                if out_data == '':
                    break;
                logging.info(out_data.strip())
        logging.info("")
        logging.info("Finished backup of set '{0}'".format(self.name))


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

    def add_set(self, name, src_dir, skip_entries):
        """Add a backup set to the backup.

        Args:
            name (str)         : The set's name.
            src_dir (str)      : The directory to backup.
            skip_entries (list): A list of directory and file names that
                                 are to be skipped during backup.
        """
        self._sets.append(
                BackupSet(name, src_dir,
                    os.path.join(self._backup_dir, name), skip_entries))
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


if __name__ == "__main__":
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
                backup.add_set(name, src_dir, skip_entries)
        backup.create(manager.find_latest_set)
    except BackupError as e:
        logging.error("Backup incomplete due to error:")
        logging.error("  {0}".format(e))
        sys.exit(1)
