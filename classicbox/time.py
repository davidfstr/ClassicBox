"""
Converts between MacOS time values and native time values.

A Mac timestamp is the number of seconds since Jan 1, 1904.
"""

from __future__ import absolute_import

import time


_UNIX_EPOCH_TIMESTAMP = int(time.mktime(time.strptime('1970', '%Y')))
_MAC_EPOCH_TIMESTAMP = int(time.mktime(time.strptime('1904', '%Y')))
_TIMEDIFF = _UNIX_EPOCH_TIMESTAMP - _MAC_EPOCH_TIMESTAMP      # 2082844800


def _calctzdiff():
    """
    Calculate the timezone difference between local time and UTC.
    """
    now = int(time.time())
    isdst = time.localtime(now).tm_isdst
    
    now_utc = list(time.gmtime(now))
    now_utc[8] = isdst  # fill in tm_isdst field
    now_utc_with_dst = time.struct_time(now_utc)
    
    tzdiff = now - int(time.mktime(now_utc_with_dst))
    return tzdiff

_TZDIFF = _calctzdiff()


def convert_mac_to_local_timestamp(mtime):
    """
    Converts a Mac timestamp to a native timestamp.
    
    This function is compatible with d_ltime() from hfsutil 3.2.6.
    """
    return mtime - _TIMEDIFF - _TZDIFF;


def convert_local_to_mac_timestamp(ltime):
    """
    Converts a local timestamp to a Mac timestamp.
    
    This function is compatible with d_mtime() from hfsutil 3.2.6.
    """
    return int(ltime) + _TZDIFF + _TIMEDIFF


def convert_ctime_string_to_mac_timestamp(ctime_string):
    """
    Converts a string output by ctime() (such as 'Sun Sep 23 19:14:47 2012')
    to a Mac timestamp.
    
    This function is compatible with ctime output from hfsutil 3.2.6.
    """
    local_timestamp = int(time.mktime(time.strptime(ctime_string)))
    return convert_local_to_mac_timestamp(local_timestamp)