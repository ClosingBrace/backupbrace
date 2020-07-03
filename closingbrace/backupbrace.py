# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2015-2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from closingbrace.backup import BackupManager
from closingbrace.backuperror import BackupError
from closingbrace.configuration import Configuration
from closingbrace.environment import Environment

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
