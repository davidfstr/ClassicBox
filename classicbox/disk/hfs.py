"""
Functions to manipulate and examine the contents of HFS Standard disk images.

Support for HFS Extended (HFS+) disk images may be added in the future.
Support for MFS disk images may be added in the future.
"""

from collections import namedtuple
import os
import re
import subprocess


_DEVNULL = open(os.devnull, 'wb')


"""
Represents a single item (i.e. a file or directory) from an HFS directory listing.

Fields:
* name : str-macroman
* is_file : bool
* type : char[4]-macroman
* creator : char[4]-macroman
* data_size : int
* rsrc_size : int
* date_modified : str-ascii
"""
HFSItem = namedtuple('HFSItem', 'name, is_file, type, creator, data_size, rsrc_size, date_modified')


def hfs_mount(disk_image_filepath):
    """
    Opens the specified disk image.
    All subsequent hfs_* functions will operate on this disk image.
    
    Raises an exception if:
    * the disk image format is not recognized,
    * an HFS Standard partition cannot be found, or 
    * any other error occurs.
    """
    subprocess.check_call(
        ['hmount', disk_image_filepath],
        stdout=_DEVNULL, stderr=_DEVNULL)


def hfs_pwd():
    """
    Returns the path to the current working directory of the mounted HFS volume.
    
    MacOS paths are bytestrings encoded in MacRoman, with colon (:) as the path
    component separator. For example: "Macintosh HD:System Folder:".
    """
    return subprocess.check_output(['hpwd'], stderr=_DEVNULL)[:-1]


def hfs_ls(dirpath=None):
    """
    Lists the specified directory on the mounted HFS volume,
    or the current working directory if no directory is specified.
    
    Returns a list of HFSItems.
    """
    hdir_command = ['hdir']
    if dirpath is not None:
        hdir_command += [dirpath]
    
    hdir_lines = subprocess.check_output(hdir_command, stderr=_DEVNULL).split('\n')[:-1]
    items = [_parse_hdir_line(line) for line in hdir_lines]
    return items


_FILE_LINE_RE = re.compile(r'f  (....)/(....) +([0-9]+) +([0-9]+) ([^ ]...........) (.+)')
_DIR_LINE_RE = re.compile(r'd +([0-9]+) items? +([^ ]...........) (.+)')

def _parse_hdir_line(line):
    """
    Arguments:
    * line -- A line from the `hdir` command.
    
    Returns an HFSItem.
    """
    file_matcher = _FILE_LINE_RE.match(line)
    if file_matcher is not None:
        (type, creator, data_size, rsrc_size, date_modified, name) = file_matcher.groups()
        return HFSItem(name, True, type, creator, data_size, rsrc_size, date_modified)
    
    dir_matcher = _DIR_LINE_RE.match(line)
    if dir_matcher is not None:
        (num_children, date_modified, name) = dir_matcher.groups()
        return HFSItem(name, False, '    ', '    ', 0, 0, date_modified)
    
    raise ValueError('Unable to parse hdir output line: %s' % line)