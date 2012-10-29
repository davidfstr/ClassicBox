#!/usr/bin/env python

"""
Writes MacOS alias files.
"""

from classicbox.alias.file import create_alias_file
import sys

# ------------------------------------------------------------------------------

VERBOSE_ALIAS_OUTPUT = False

def main(args):
    command = args.pop(0)
    
    if command == 'create':
        create_alias_file(*args)
    else:
        sys.exit('Unknown command: %s' % command)
        return

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
