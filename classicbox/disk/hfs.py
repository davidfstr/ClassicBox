"""
Functions to manipulate and examine the contents of HFS Standard disk images.

Support for HFS Extended (HFS+) disk images may be added in the future.
Support for MFS disk images may be added in the future.
"""

from __future__ import absolute_import

from classicbox.time import convert_ctime_string_to_mac_timestamp
from classicbox.util import DEVNULL
from collections import namedtuple
import os
import re
import shutil
import subprocess
from tempfile import NamedTemporaryFile
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
            volume_info['created'] = convert_ctime_string_to_mac_timestamp(ctime_string)
        
        matcher = _HMOUNT_MODIFIED_RE.match(line)
        if matcher is not None:
            ctime_string = matcher.group(1)     # str-ascii
            volume_info['modified_ctime'] = ctime_string
            volume_info['modified'] = convert_ctime_string_to_mac_timestamp(ctime_string)
        
        matcher = _HMOUNT_BYTES_FREE_RE.match(line)
        if matcher is not None:
            bytes_free = int(matcher.group(1))  # int
            volume_info['bytes_free'] = bytes_free
    
    return volume_info


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


def hfs_copy_in(source_filepath, target_macfilepath):
    """
    Copies the specified MacBinary-encoded file from the local filesystem to the
    mounted HFS volume.
    
    Any file already at the target path will be overridden.
    
    Arguments:
    * source_filepath -- Path to a MacBinary-encoded file in the local filesystem.
    * target_macfilepath -- An absolute MacOS path. Location on the HFS volume
                            where the file will be copied to.
    """
    subprocess.check_call(
        ['hcopy', '-m', source_filepath, target_macfilepath],
        stdout=DEVNULL, stderr=DEVNULL)


def hfs_copy_in_from_stream(source_stream, target_macfilepath):
    """
    Same as `hfs_copy_in()` but copies from a source stream
    (i.e. a file-like object) instead of from a source file.
    """
    temp_file = NamedTemporaryFile(suffix='.bin', mode='wb', delete=False)
    temp_filepath = temp_file.name
    try:
        # Copy stream to local filesystem, since we need an actual file
        # as the source of the copy
        try:
            shutil.copyfileobj(source_stream, temp_file)
        finally:
            temp_file.close()
            
        # Copy alias file from local filesystem to disk image
        hfs_copy_in(temp_filepath, target_macfilepath)
    finally:
        os.remove(temp_filepath)


def hfs_exists(macitempath):
    """
    Returns whether the specified item exists on the mounted HFS volume.
    """
    process = subprocess.Popen(
        ['hdir', '-i', '-d', macitempath],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = process.communicate()
    if err.endswith('no such file or directory\n'):
        return False
    if process.returncode != 0 or err != '':
        raise IOError('Called process returned error. Code %s: %s' % (
            process.returncode, err))
    return True


def hfs_delete(macitempath):
    """
    Deletes the specified item on the mounted HFS volume.
    """
    subprocess.check_call(
        ['hdel', macitempath],
        stdout=DEVNULL, stderr=DEVNULL)

# ------------------------------------------------------------------------------
# HFS Path Manipulation

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
