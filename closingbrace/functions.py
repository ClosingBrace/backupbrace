# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2015-2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import shutil
from closingbrace.backuperror import BackupError

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
