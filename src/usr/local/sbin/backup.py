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
"""

if __name__ == "__main__":
    pass
