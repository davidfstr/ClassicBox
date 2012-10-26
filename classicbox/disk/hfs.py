"""
Functions to manipulate and examine the contents of HFS Standard disk images.

Support for HFS Extended (HFS+) disk images may be added in the future.
Support for MFS disk images may be added in the future.
"""

from classicbox.util import DEVNULL
from collections import namedtuple
import os
import re
import subprocess
import time


"""
Represents a single item (i.e. a file or directory) from an HFS directory listing.

Fields:
* id : int -- The file number or directory ID that uniquely identifies the file
              on the disk.
* name : str-macroman
* is_file : bool
* type : char[4]-macroman
* creator : char[4]-macroman
* data_size : int
* rsrc_size : int
* date_modified : str-ascii -- Human-readable modification date of the file.
                               Unfortunately hfsutils does not provide a
                               machine-readable version.
"""
HFSItem = namedtuple(
    'HFSItem',
    ('id', 'name', 'is_file', 'type', 'creator', 'data_size', 'rsrc_size', 'date_modified'))


_HMOUNT_VOLUME_NAME_RE = re.compile(r'^Volume name is "(.*)"$')
_HMOUNT_CREATED_RE =     re.compile(r'^Volume was created on (.*)$')
_HMOUNT_MODIFIED_RE =    re.compile(r'^Volume was last modified on (.*)$')
_HMOUNT_BYTES_FREE_RE =  re.compile(r'^Volume has ([0-9]+) bytes free$')

def hfs_mount(disk_image_filepath):
    """
    Opens the specified disk image.
    All subsequent hfs_* functions will operate on this disk image.
    
    Raises an exception if:
    * the disk image format is not recognized,
    * an HFS Standard partition cannot be found, or 
    * any other error occurs.
    """
    hmount_lines = subprocess.check_output(
        ['hmount', disk_image_filepath],
        stderr=DEVNULL).split('\n')[:-1]
    
    volume_info = {}
    for line in hmount_lines:
        line = line.strip('\r\n')
        
        matcher = _HMOUNT_VOLUME_NAME_RE.match(line)
        if matcher is not None:
            name = matcher.group(1)             # str-macroman
            volume_info['name'] = name
        
        matcher = _HMOUNT_CREATED_RE.match(line)
        if matcher is not None:
            ctime_string = matcher.group(1)     # str-ascii
            volume_info['created_ctime'] = ctime_string
            volume_info['created'] = _convert_ctime_to_mac_timestamp(ctime_string)
        
        matcher = _HMOUNT_MODIFIED_RE.match(line)
        if matcher is not None:
            ctime_string = matcher.group(1)     # str-ascii
            volume_info['modified_ctime'] = ctime_string
            volume_info['modified'] = _convert_ctime_to_mac_timestamp(ctime_string)
        
        matcher = _HMOUNT_BYTES_FREE_RE.match(line)
        if matcher is not None:
            bytes_free = int(matcher.group(1))  # int
            volume_info['bytes_free'] = bytes_free
    
    return volume_info


# Year 1904, minus 1 hour (3600) -- maybe a Daylight Savings Time error?
# 
# FIXME: It seems likely that my time conversion computations are inadvertently
#        being affected by the current computer's locale settings.
#        
#        Make sure I am reversing the conversion logic done by hfsutil's
#        d_ltime() and d_mtime() appropriately.
_EMPIRICAL_MAC_EPOCH_TIMESTAMP = -2082819600

if __debug__:
    # (from hdir command emitting a volume creation date)
    _input_ctime_string = 'Sun Sep 23 19:14:47 2012'
    _expected_unix_timestamp = 1348452887
    # (from MacOS alias referencing the same volume's creation date)
    _expected_output_mac_timestamp = 3431272487
    
    _actual_unix_timestamp = int(time.mktime(time.strptime(_input_ctime_string)))
    if _actual_unix_timestamp != _expected_unix_timestamp:
        raise AssertionError(
            'mktime() is giving back different results than before. ' +
            'Is your mktime() implementation taking your current timezone ' +
            'or DST status into account when computing results?')
    
    _computed_empirical_mac_epoch_timestamp = (
        _actual_unix_timestamp -
        _expected_output_mac_timestamp
    )
    if _EMPIRICAL_MAC_EPOCH_TIMESTAMP != _computed_empirical_mac_epoch_timestamp:
        raise AssertionError(
            'The computed Mac time epoch changed! ' +
            'Is your mktime() implementation taking your current timezone ' +
            'or DST status into account when computing results?')

def _convert_ctime_to_mac_timestamp(ctime_string):
    """
    Converts a ctime string (such as 'Sun Sep 23 19:14:47 2012') to a
    Mac timestamp, which is the number of seconds since Jan 1, 1904.
    
    Local time is assumed, as opposed to UTC time.
    """
    unix_timestamp = int(time.mktime(time.strptime(ctime_string)))
    mac_timestamp = unix_timestamp - _EMPIRICAL_MAC_EPOCH_TIMESTAMP
    return mac_timestamp


def hfs_pwd():
    """
    Returns the absolute MacOS path to the current working directory of the mounted HFS volume.
    
    MacOS paths are bytestrings encoded in MacRoman, with colon (:) as the path
    component separator. For example: "Macintosh HD:System Folder:".
    """
    return subprocess.check_output(['hpwd'], stderr=DEVNULL)[:-1]


def hfs_ls(dirpath=None, _stat_path=False):
    """
    Lists the specified directory on the mounted HFS volume,
    or the current working directory if no directory is specified.
    
    Behavior is undefined if there is no such directory.
    
    Arguments:
    * dirpath -- An absolute MacOS path. For example "Boot:" or "Boot:System Folder".
    
    Returns a list of HFSItems.
    """
    hdir_command = ['hdir', '-i']
    if _stat_path:
        hdir_command += ['-d']
    if dirpath is not None:
        hdir_command += [dirpath]
    
    hdir_lines = subprocess.check_output(hdir_command, stderr=DEVNULL).split('\n')[:-1]
    items = [_parse_hdir_line(line) for line in hdir_lines]
    return items


def hfs_stat(itempath):
    """
    Gets information about the specified item on the mounted HFS volume.
    
    Behavior is undefined if there is no such item.
    
    Arguments:
    * itempath -- An absolute MacOS path. For example "Boot:" or "Boot:System Folder".
    
    Returns an HFSItem.
    """
    
    item_with_path_as_name = hfs_ls(itempath, _stat_path=True)[0]
    itemname = hfspath_itemname(itempath)
    return item_with_path_as_name._replace(name=itemname)


_FILE_LINE_RE = re.compile(r'^ *([0-9]+) f  (....)/(....) +([0-9]+) +([0-9]+) ([^ ]...........) (.+)$')
_DIR_LINE_RE =  re.compile(r'^ *([0-9]+) d +([0-9]+) items? +([^ ]...........) (.+)$')

def _parse_hdir_line(line):
    """
    Arguments:
    * line -- A line from the `hdir -i` command.
    
    Returns an HFSItem.
    """
    file_matcher = _FILE_LINE_RE.match(line)
    if file_matcher is not None:
        (id, type, creator, data_size, rsrc_size, date_modified, name) = file_matcher.groups()
        return HFSItem(int(id), name, True, type, creator, int(data_size), int(rsrc_size), date_modified)
    
    dir_matcher = _DIR_LINE_RE.match(line)
    if dir_matcher is not None:
        (id, num_children, date_modified, name) = dir_matcher.groups()
        return HFSItem(int(id), name, False, '    ', '    ', 0, 0, date_modified)
    
    raise ValueError('Unable to parse hdir output line: %s' % line)


def hfspath_dirpath(itempath):
    """
    Returns the absolute MacOS path to the volume or directory containing the
    specified item. If the item refers to a volume, None is returned.
    
    Note that the semantics are similar to but not the same as `os.path.dirname`.
    
    Examples:
    * hfspath_dirpath('Boot:') -> None
    * hfspath_dirpath('Boot:System Folder') -> 'Boot:'
    * hfspath_dirpath('Boot:System Folder:Preferences') -> 'Boot:System Folder'
    
    Arguments:
    * itempath -- An absolute MacOS path. For example "Boot:" or "Boot:System Folder".
    """
    
    itempath = hfspath_normpath(itempath)
    if itempath.endswith(':'):
        # Item is a volume and has no parent directory
        return None
    
    parent_path = itempath.rsplit(':', 1)[0]
    if ':' not in parent_path:
        # Parent is a volume
        return parent_path + ':'
    else:
        # Parent is a directory
        return parent_path


def hfspath_itemname(itempath):
    """
    Returns the name of the specified item.
    
    Note that the semantics are similar to but not the same as `os.path.basename`.
    
    Examples:
    * hfspath_itemname('Boot:') -> 'Boot'
    * hfspath_itemname('Boot:System Folder') -> 'System Folder'
    * hfspath_itemname('Boot:System Folder:') -> 'System Folder'
    * hfspath_itemname('Boot:SimpleText') -> 'SimpleText'
    
    Arguments:
    * itempath -- An absolute MacOS path. For example "Boot:" or "Boot:System Folder".
    """
    
    if itempath.endswith(':'):
        itempath = itempath[:-1]
    return itempath.rsplit(':', 1)[-1]


def hfspath_normpath(itempath):
    """
    Returns the normalized form of the specified absolute MacOS path.
    
    This is the path without any trailing colon (:), unless the path refers to
    a volume.
    
    Examples:
    * hfspath_normpath('Boot:') -> 'Boot:'
    * hfspath_normpath('Boot:System Folder') -> 'Boot:System Folder'
    * hfspath_normpath('Boot:System Folder:') -> 'Boot:System Folder'
    * hfspath_normpath('Boot:SimpleText') -> 'Boot:SimpleText'
    
    Arguments:
    * itempath -- An absolute MacOS path. For example "Boot:" or "Boot:System Folder".
    """
    
    if itempath.endswith(':'):
        if itempath.index(':') == len(itempath) - 1:
            # Refers to a volume
            return itempath
        else:
            # Refers to a directory
            return itempath[:-1]
    else:
        # Refers to a file or directory
        return itempath
