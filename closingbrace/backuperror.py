# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2015-2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

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
