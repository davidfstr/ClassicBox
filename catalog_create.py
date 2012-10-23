#!/usr/bin/env python
"""
Scans the contents of an HFS-Standard volume and outputs a catalog document
that describes the names and last modified timestamps of all files on the volume.

This tool handles non-ASCII filenames correctly.

Requirements:
* hfsutils >= 3.2.6
    * Binaries must be in your shell's PATH.

Catalog Format:
* It's JSON. Strings are UTF-8 encoded.
* Grammar:
    * ROOT: DirectoryListing
    * DirectoryListing: [Item, ...]
    * Item:      File | Directory
    * File:      (name : unicode, date_modified : unicode)
    * Directory: (name : unicode, date_modified : unicode, DirectoryListing)
"""

import json
import os.path
import pprint
import re
import subprocess
import sys


def main(args):
    if len(args) > 0 and args[0] == '--pretty':
        pretty = True
        args = args[1:]
    else:
        pretty = False
    
    if len(args) != 1:
        sys.exit('syntax: catalog_create [--pretty] <path to .dsk image of HFS Standard volume>')
        return
    
    dsk_filepath = args[0]
    if not os.path.exists(dsk_filepath):
        sys.exit('file not found: %s' % dsk_filepath)
        return
    
    catalog = scan_disk_contents(dsk_filepath)
    
    if pretty:
        pprint.pprint(catalog)
    else:
        print json.dumps(catalog, ensure_ascii=True)


def scan_disk_contents(dsk_filepath):
    # NOTE: Will fail if the specified file is not an HFS Standard disk image
    subprocess.check_call(['hmount', dsk_filepath],
        stdout=subprocess.PIPE) # HACK: Ignore (small amount of) output
    
    volume_dirpath = subprocess.check_output(['hpwd'])[:-1]
    volume_name = volume_dirpath[:-1]   # chop trailing ':'
    
    # NOTE: Constructs entire disk catalog in memory, which could be large.
    return list_descendants(volume_dirpath)


def list_descendants(parent_dirpath):
    hdir_lines = subprocess.check_output(['hdir', parent_dirpath]).split('\n')[:-1]
    
    tree = []
    for line in hdir_lines:
        (name, date_modified, is_file) = parse_hdir_line(line)
        if is_file:
            tree.append((name.decode('macroman'), date_modified.decode('ascii')))
        else:
            descendants = list_descendants(parent_dirpath + name + ':')
            tree.append((name.decode('macroman'), date_modified.decode('ascii'), descendants))
    
    return tree


FILE_LINE_RE = re.compile(r'f  (....)/(....) +([0-9]+) +([0-9]+) ([^ ]...........) (.+)')
DIR_LINE_RE = re.compile(r'd +([0-9]+) items? +([^ ]...........) (.+)')

def parse_hdir_line(line):
    """
    Arguments:
    line -- A line from the `hdir` command.
    
    Returns:
    (name : str-MacRoman, date_modified : str, is_file : bool)
    """
    file_matcher = FILE_LINE_RE.match(line)
    if file_matcher is not None:
        (type, creator, data_size, rsrc_size, date_modified, name) = file_matcher.groups()
        return (name, date_modified, True)
    
    dir_matcher = DIR_LINE_RE.match(line)
    if dir_matcher is not None:
        (num_children, date_modified, name) = dir_matcher.groups()
        return (name, date_modified, False)
    
    raise ValueError('Unable to parse hdir output line: %s' % line)


if __name__ == '__main__':
    main(sys.argv[1:])