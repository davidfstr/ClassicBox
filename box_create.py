#!/usr/bin/env python

"""
Creates a blank box directory, for use with the box_up command.

The user must manually populate the box with:
(1) [bin] An emulator such as Basilisk.
(2) [rom] A ROM package.
(3) [mount] A boot disk.

Syntax:
    box_create.py <dirpath>
"""

from classicbox.box import box_create
import sys


def main(args):
    # Parse arguments
    if len(args) != 1:
        sys.exit('syntax: box_create.py <dirpath>')
        return
    dirpath = args[0]
    
    box_create(dirpath)


if __name__ == '__main__':
    main(sys.argv[1:])
