#!/usr/bin/env python

"""
Writes MacOS alias files.
"""

from classicbox.alias.file import create_alias_file
from classicbox.alias.file import create_alias_info_for_item_on_disk_image
from classicbox.alias.record import _ALIAS_RECORD_MEMBERS
from classicbox.alias.record import Extra
from classicbox.alias.record import print_alias_record
from classicbox.alias.record import write_alias_record
from classicbox.disk.hfs import hfs_copy_in_from_stream
from classicbox.disk.hfs import hfs_mount
from classicbox.io import fill_missing_structure_members_with_defaults
from classicbox.macbinary import write_macbinary
from classicbox.resource_fork import write_resource_fork
from StringIO import StringIO
import os.path
import sys

# ------------------------------------------------------------------------------

VERBOSE_ALIAS_OUTPUT = False

def main(args):
    # Parse arguments
    command = args.pop(0)
    force = (len(args) >= 1 and args[0] == '-f')
    if force:
        args = args[1:]
    
    if command != 'create':
        output_alias_resource_fork_filepath = args.pop(0)
        
        # Don't let the user inadvertently clobber an existing file
        if not force and os.path.exists(output_alias_resource_fork_filepath):
            sys.exit('File exists: %s' % output_alias_resource_fork_filepath)
            return
    
    if command == 'write_fixed_as_fork':
        write_fixed_alias_resource_fork_file(output_alias_resource_fork_filepath)
    elif command == 'write_targeted_as_fork':
        write_targeted_alias(output_alias_resource_fork_filepath, args,
            output_type='resource_fork')
    elif command == 'write_targeted_as_macbinary':
        write_targeted_alias(output_alias_resource_fork_filepath, args,
            output_type='macbinary')
    elif command == 'write_targeted_as_hfs_file':
        write_targeted_alias(output_alias_resource_fork_filepath, args,
            output_type='hfs_file')
    elif command == 'create':
        create_alias_file(*args)
    else:
        sys.exit('Unknown command: %s' % command)
        return

def write_fixed_alias_resource_fork_file(output_alias_resource_fork_filepath):
    """
    Writes a fixed alias resource fork file to disk.
    """
    
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


# NOTE: This method's core functionality (with output_type='hfs_type') is
#       available in `classicbox.alias.file.create_alias()`.
def write_targeted_alias(output_filepath, args, output_type):
    """
    Writes an alias as a resource fork file, as a MacBinary file, or
    as an HFS file that targets a particular item in an HFS disk image.
    """
    
    # Parse arguments
    (disk_image_filepath, target_macitempath) = args
    
    alias_info = create_alias_info_for_item_on_disk_image(
        disk_image_filepath, target_macitempath)
    
    alias_record = alias_info['alias_record']
    alias_resource_info = alias_info['alias_resource_info']
    alias_file_info = alias_info['alias_file_info']
    
    # Serialize alias record
    alis_resource_contents_output = StringIO()
    write_alias_record(alis_resource_contents_output, alias_record)
    alis_resource_contents = alis_resource_contents_output.getvalue()
    
    if VERBOSE_ALIAS_OUTPUT:
        # Display the resulting alias record
        fill_missing_structure_members_with_defaults(_ALIAS_RECORD_MEMBERS, alias_record)
        print_alias_record(alias_record)
    
    # Serialize alias file resource fork
    resource_fork_output = StringIO()
    write_resource_fork(resource_fork_output, {
        'resource_types': [
            {
                'code': alias_resource_info['type'],
                'resources': [
                    {
                        'id': alias_resource_info['id'],
                        'name': alias_resource_info['name'],
                        'attributes': alias_resource_info['attributes'],
                        'data': alis_resource_contents
                    }
                ]
            }
        ]
    })
    resource_fork_contents = resource_fork_output.getvalue()
    
    if output_type == 'resource_fork':
        with open(output_filepath, 'wb') as output:
            output.write(resource_fork_contents)
        return
    
    # Determine alias filename
    if output_type == 'hfs_file':
        # (Not a normal filepath. So we must do our own `basename` ourselves.)
        alias_file_filename = output_filepath.rsplit(':', 1)[-1]
    else:
        alias_file_filename = os.path.basename(output_filepath)
    if alias_file_filename.endswith('.bin'):
        alias_file_filename = alias_file_filename[:-len('.bin')]
    
    # Serialize MacBinary-encoded alias file
    macbinary_output = StringIO()
    write_macbinary(macbinary_output, {
        'filename': alias_file_filename,
        'file_type': alias_file_info['alias_file_type'],
        'file_creator': alias_file_info['alias_file_creator'],
        'finder_flags': alias_file_info['alias_file_finder_flags'],
        'resource_fork': resource_fork_contents,
    })
    macbinary_contents = macbinary_output.getvalue()
    
    if output_type == 'macbinary':
        with open(output_filepath, 'wb') as output:
            output.write(macbinary_contents)
        return
    
    if output_type == 'hfs_file':
        # Parse output path argument
        (output_disk_image_filepath, output_macfilepath) = \
            output_filepath.split(':', 1)
        
        # Check arguments
        if not os.path.exists(output_disk_image_filepath):
            raise ValueError('Disk image file not found: %s' % output_disk_image_filepath)
        
        hfs_mount(output_disk_image_filepath)
        hfs_copy_in_from_stream(StringIO(macbinary_contents), output_macfilepath)
        return
    
    raise ValueError('Unknown output type: %s' % output_type)

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
