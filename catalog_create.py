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

from classicbox.disk.hfs import hfs_ls
from classicbox.disk.hfs import hfs_mount
import json
import os.path
import pprint
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
    
    catalog = create_catalog(dsk_filepath)
    
    if pretty:
        pprint.pprint(catalog)
    else:
        print json.dumps(catalog, ensure_ascii=True)


def create_catalog(dsk_filepath):
    # NOTE: Will fail if the specified file is not an HFS Standard disk image
    volume_info = hfs_mount(dsk_filepath)
    volume_name = volume_info['name']
    volume_dirpath = volume_name + ':'
    
    # NOTE: Constructs entire disk catalog in memory, which could be large.
    return _list_descendants(volume_dirpath)


def _list_descendants(parent_dirpath):
    tree = []
    for item in hfs_ls(parent_dirpath):
        if item.is_file:
            tree.append((item.name, item.date_modified))
        else:
            descendants = _list_descendants(parent_dirpath + item.name + ':')
            tree.append((item.name, item.date_modified, descendants))
    
    return tree


if __name__ == '__main__':
    main(sys.argv[1:])