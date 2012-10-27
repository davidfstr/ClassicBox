#!/usr/bin/env python

"""
Reads resource forks.
"""

from classicbox.resource_fork import read_resource_fork
import sys

# ------------------------------------------------------------------------------

READ_RESOURCE_NAMES = True

def main(args):
    (resource_file_filepath, ) = args
    
    with open(resource_file_filepath, 'rb') as input:
        # Read and print the contents of the resource map
        resource_map = read_resource_fork(
            input,
            read_resource_names=READ_RESOURCE_NAMES,
            _verbose=True)

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
