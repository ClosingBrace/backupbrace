# Backupbrace
# A script to create backups of a Linux system.
#
# Copyright (c) 2015-2020 Hans Vredeveld
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import dateutil.parser
import json
from closingbrace.backupset import BackupSet
from datetime import datetime

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
