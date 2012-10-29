#!/usr/bin/env python

"""
Writes MacOS alias files.
"""

from classicbox.alias.file import create_alias_file
from classicbox.alias.record import Extra
from classicbox.alias.record import write_alias_record
from classicbox.resource_fork import write_resource_fork
from StringIO import StringIO
import os.path
import sys

# ------------------------------------------------------------------------------

VERBOSE_ALIAS_OUTPUT = False

def main(args):
    command = args.pop(0)
    
    if command == 'write_fixed_as_fork':
        write_fixed_alias_resource_fork_file(args)
    elif command == 'create':
        create_alias_file(*args)
    else:
        sys.exit('Unknown command: %s' % command)
        return

def write_fixed_alias_resource_fork_file(args):
    """
    Writes a fixed alias resource fork file to disk.
    """
    
    # Parse arguments
    force = (len(args) >= 1 and args[0] == '-f')
    if force:
        args = args[1:]
    output_alias_resource_fork_filepath = args.pop(0)
    
    # Don't let the user inadvertently clobber an existing file
    if not force and os.path.exists(output_alias_resource_fork_filepath):
        sys.exit('File exists: %s' % output_alias_resource_fork_filepath)
        return
    
    # "AppAlias.rsrc.dat"
    alis_resource_contents_output = StringIO()
    write_alias_record(alis_resource_contents_output, {
        'alias_kind': 0,
        'volume_name': 'Boot',
        'volume_created': 3431272487,
        'parent_directory_id': 542,
        'file_name': 'app',
        'file_number': 543,
        # NOTE: Can't get file_created reliably from hfsutil CLI
        'file_created': 3265652246,
        'file_type': 'APPL',
        'file_creator': 'AQt7',
        'nlvl_from': 1,
        'nlvl_to': 1,
        'extras': [
            Extra(0, 'parent_directory_name', 'B'),
            Extra(1, 'directory_ids', [542, 541, 484]),
            Extra(2, 'absolute_path', 'Boot:AutQuit7:A:B:app'),
            Extra(0xFFFF, 'end', None)
        ]
    })
    alis_resource_contents = alis_resource_contents_output.getvalue()
    
    with open(output_alias_resource_fork_filepath, 'wb') as resource_fork_output:
        write_resource_fork(resource_fork_output, {
            'resource_types': [
                {
                    'code': 'alis',
                    'resources': [
                        {
                            'id': 0,
                            'name': 'app alias',
                            'attributes': 0,
                            'data': alis_resource_contents
                        }
                    ]
                }
            ]
        })

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
