# Backupbrace

a script to backup a Linux (desktop) system

## Description

_Backupbrace_ is a script to create backups of a Linux filesystem to a locally mounted backup
directory. Typically the directory where the backups are made is on a USB disk.

Each new backup is created as a subdirectory of the backup directory, where the timestamp of the
backup start is used to name the subdirectory. A backup starts as a copy of the last backup. In this
copy directories are created anew, but files are hardlinked with the file in last backup. After the
copy, the backup's directory structure is synchronized with the source directory that it is to be a
backup of. Files that changed between the last backup and the current backup run, are replaced by
their source. This breaks the hardlink between the last and current backup, so that the file in the
last backup is not changed. Files that did not change between the last backup and the current run,
are left alone. The hardlink will stay intact.

## License

_Backupbrace_ is distributed under the [Mozilla Public License Version 2.0](LICENSE.md).

## Requirements

The _backupbrace_ script itself is written in Python 3. At least version 3.6 must be installed. Also
the following Python modules must be available:

* python\_dateutil

_Backupbrace_ uses rsync for the actual synchronization. Therefore rsync must be installed. The
filesystem on which the backups are created must support inodes.

## Installation and Configuration

### Installation

The best way to install _backupbrace_ is to install it in a Python virtual environment using pip.
With a symbolic link in a directory in the path to the `backupbrace` executable, the tool is also
available without manually activating the virtual environment.

1. First, clone the git repository into a local directory. Let's call this `git-dir`.
2. Create a virtual environment where you want to install _backupbrace_  
`python3 -m venv <install-dir>`
3. Activate the virtual environment  
`source <install-dir>/bin/activate`
4. Install _backupbrace_ using pip  
`pip install <git-dir>`
5. Create a symbolic link in a directory on the path (here `/usr/local/sbin`)  
`ln -s <install-dir>/bin/backupbrace /usr/local/sbin/backupbrace`

### Configuration

The configuration for _backupbrace_ is stored in a JSON-file. The file is versioned. This version of
the program uses version 2.0 of the configuration file. It is also compatible with any other 2.x
version of the configuration file.

Version 2.0 supports the backup of local and remote files and directories to a local backup
directory.

A sample version 2.0 configuration file looks as follows:

```json
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
```

The configuration is contained in a single, unnamed JSON object. The object contains the following
name/value pairs:

* **version** The string "2.0".
* **backup-dir** A string that contains the base directory where the backups will go. This directory
                 must exist prior to the execution of the backup program.
* **backup-sets**: An array of backup sets.

The backup sets are objects that contain the following name/value pairs:

* **set-name** A string identifying the backup set. This set name will be used to create a
               subdirectory in `backup-dir`.
* **type** The type of backup, either "local dir" or "remote dir".
* **remote-shell**: (only when `type` is "remote dir") The remote shell to use for connecting with
                    the remote host. The string includes the options that the remote shell needs to
                    connect to the remote host.
* **remote-host** (only when `type` is "remote dir") The remote host to connect to. This can include
                  a remote user (with the syntax "\<user\>@\<host\>") that the remote rsync process
                  will use to execute its task.
* **source-dir** A string with the absolute path to the directory to backup.
* **skip-entries** (optional) An array of strings that are directory and file names which are to be
                   skipped during backup.

Each backup set will be backed up to the directory `backup-dir/`\<timestamp\>`/set-name`, where the
timestamp is fixed the moment the program started. Directories and files in `skip-entries` will be
excluded from the backup, indepent from where they appear below the source directory.

## Usage

_Backupbrace_ is a command line tool with the following invocation:

```bash
backupbrace [-h] [-f] [-c CONFIG] [-v]
```

The optional arguments are:

| option | description |
|--------|-------------|
| `-h, --help` | show this help message and exit |
| `-f, --conf-format` | show help about the configuration file format and exit |
| `-c CONFIG, --config CONFIG` | the backup's configuration file (default: `/etc/backupbrace.conf`)|
| `-v, --version` | show program's version number and exit |

## Changes / History

**v0.2.0 (21-may-2016)**
Next to making backups of local directories, the application can now make backups of remote
directories that are accessible via a remote shell like ssh.

**v0.1.0 (06-jun-2015)**
First complete application that make backups of local directories to another local directory.
