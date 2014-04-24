#!/usr/bin/env python

"""
Creates an alias file that points to another file.
"""

from classicbox.alias.file import create_alias_file
import sys

def main(args):
    # Parse arguments
    if len(args) != 4:
        sys.exit('syntax: alias_create.py output_disk_image_filepath, output_macfilepath, target_disk_image_filepath, target_macitempath')
        return
    output_disk_image_filepath = args[0]
    output_macfilepath = args[1].decode('macroman')
    target_disk_image_filepath = args[2]
    target_macitempath = args[3].decode('macroman')
    
    create_alias_file(
        output_disk_image_filepath, output_macfilepath,
        target_disk_image_filepath, target_macitempath)


if __name__ == '__main__':
    main(sys.argv[1:])
