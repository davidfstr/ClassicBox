#!/usr/bin/env python

"""
Writes MacOS alias files.
"""

# TODO: Avoid need to import private member _ALIAS_RECORD_MEMBERS
from classicbox.alias.record import _ALIAS_RECORD_MEMBERS
from classicbox.alias.record import Extra
from classicbox.alias.record import print_alias_record
from classicbox.alias.record import write_alias_record
from classicbox.disk.hfs import hfs_mount
from classicbox.disk.hfs import hfs_stat
from classicbox.disk.hfs import hfspath_dirpath
from classicbox.disk.hfs import hfspath_normpath
from classicbox.io import fill_missing_structure_members_with_defaults
from classicbox.resource_fork import write_resource_fork
from StringIO import StringIO
import os.path
import sys

# ------------------------------------------------------------------------------

def main(args):
    # Parse arguments
    command = args.pop(0)
    force = (len(args) >= 1 and args[0] == '-f')
    if force:
        args = args[1:]
    output_alias_resource_fork_filepath = args.pop(0)
    
    # Don't let the user inadvertently clobber an existing file
    if not force and os.path.exists(output_alias_resource_fork_filepath):
        sys.exit('File exists: %s' % output_alias_resource_fork_filepath)
        return
    
    if command == 'write_fixed':
        write_fixed_alias_resource_fork_file(output_alias_resource_fork_filepath)
    elif command == 'write_targeted':
        write_targeted_alias_resource_fork_file(output_alias_resource_fork_filepath, args)
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
            'attributes': 0,
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


def write_targeted_alias_resource_fork_file(output_alias_resource_fork_filepath, args):
    """
    Writes an alias resource fork file that targets a particular
    item in an HFS disk image.
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
    
    # Display the resulting alias record
    fill_missing_structure_members_with_defaults(_ALIAS_RECORD_MEMBERS, alias_record)
    print_alias_record(alias_record)
    
    # Write alias file resource fork containing the alias record
    with open(output_alias_resource_fork_filepath, 'wb') as resource_fork_output:
        write_resource_fork(resource_fork_output, {
            'attributes': 0,
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


def create_alias_info_for_item_on_disk_image(disk_image_filepath, target_macitempath):
    """
    Creates an alias that targets the specified item on the specified disk image.
    
    Arguments:
    * disk_image_filepath -- Path to a disk image.
    * target_macitempath -- The absolute MacOS path to the desired target of 
                            the alias, which resides on the disk image.
    """
    # Normalize target path
    target_macitempath = hfspath_normpath(target_macitempath)
    
    volume_info = hfs_mount(disk_image_filepath)
    
    target_item_info = hfs_stat(target_macitempath)
    
    alias_resource_info = {
        'type': 'alis',
        'id': 0,
        'name': target_item_info.name + ' alias',
        'attributes': 0
    }
    
    target_is_volume = target_macitempath.endswith(':')
    if target_is_volume:
        # Target is volume
        alias_record = {
            'alias_kind': 1,                           # 1 = directory
            'volume_name': volume_info['name'],
            'volume_created': volume_info['created'],
            'parent_directory_id': 1,                  # special ID for parent of all volumes
            'file_name': target_item_info.name,
            'file_number': target_item_info.id,
            'file_created': volume_info['created'],    # special case
            'file_type': 0,    # random junk in native MacOS implementation
            'file_creator': 0, # random junk in native MacOS implementation
            'nlvl_from': 0xFFFF,   # assume alias file on different volume from target
            'nlvl_to': 0xFFFF,     # assume alias file on different volume from target
            'extras': [
                Extra(0xFFFF, 'end', None)
            ]
        }
        
        # A Finder-created alias file to a volume contains a custom icon
        # {'ICN#', 'ics#', 'SICN'} that matches the volume that it refers to.
        # 
        # Here, we are creating an alias file without a custom icon, that will
        # appear visually as a regular document alias (ick!) but will still work.
        # Finder will actually add the custom icon to the existing alias file
        # when the user attempts to open the file.
        # 
        # If it is desired to add the custom icon in the future, it is important
        # to include the USE_CUSTOM_ICON flag for the alias file (in addition
        # to ALIAS and INITED).
        alias_file_info = {
            'alias_file_type': 'hdsk',
            'alias_file_creator': 'MACS'
            #'alias_file_flags': (ALIAS | INITED)
        }
        
    else:
        # Target is file or folder
        
        # Lookup ancestors
        ancestor_infos = []
        cur_ancestor_dirpath = hfspath_dirpath(target_macitempath)
        while cur_ancestor_dirpath is not None:
            ancestor_infos.append(hfs_stat(cur_ancestor_dirpath))
            cur_ancestor_dirpath = hfspath_dirpath(cur_ancestor_dirpath)
        
        parent_dir_info = ancestor_infos[0]         # possibly a volume
        ancestor_dir_infos = ancestor_infos[:-1]    # exclude volume
        
        if target_item_info.is_file:
            # Target is file
            alias_record = {
                'alias_kind': 0,                       # 0 = file
                'volume_name': volume_info['name'],
                'volume_created': volume_info['created'],
                'parent_directory_id': parent_dir_info.id,
                'file_name': target_item_info.name,
                'file_number': target_item_info.id,
                # NOTE: Can't get file_created reliably from hfsutil CLI
                'file_created': 0,
                'file_type': target_item_info.type,
                'file_creator': target_item_info.creator,
                'nlvl_from': 1,    # assume alias file on same volume as target
                'nlvl_to': 1,      # assume alias file on same volume as target
                'extras': _create_standard_extras_list(
                    parent_dir_info, ancestor_dir_infos, target_macitempath)
            }
            
            if target_item_info.type == 'APPL':
                # Target is application file
                alias_file_info = {
                    'alias_file_type': 'adrp',
                    'alias_file_creator': target_item_info.creator
                    #'alias_file_flags': (ALIAS | INITED)
                }
                
            else:
                # Target is document file
                alias_file_info = {
                    'alias_file_type': target_item_info.type,
                    'alias_file_creator': 'MPS '
                    #'alias_file_flags': (ALIAS | INITED)
                }
            
        else:
            # Target is folder
            alias_record = {
                'alias_kind': 1,                       # 1 = directory
                'volume_name': volume_info['name'],
                'volume_created': volume_info['created'],
                'parent_directory_id': parent_dir_info.id,
                'file_name': target_item_info.name,
                'file_number': target_item_info.id,
                # NOTE: Can't get file_created reliably from hfsutil CLI
                'file_created': 0,
                'file_type': 0,    # random junk in native MacOS implementation
                'file_creator': 0, # random junk in native MacOS implementation
                'nlvl_from': 1,    # assume alias file on same volume as target
                'nlvl_to': 1,      # assume alias file on same volume as target
                'extras': _create_standard_extras_list(
                    parent_dir_info, ancestor_dir_infos, target_macitempath)
            }
            
            alias_file_info = {
                # NOTE: Type is 'fasy' if target is the System Folder. <sigh>
                'alias_file_type': 'fdrp',
                'alias_file_creator': 'MACS'
                #'alias_file_flags': (ALIAS | INITED)
            }
            
            # Fun trivia! An alias to the Trash has:
            # 
            # alias_record:
            # - 'alias_kind': 1        # 1 = directory
            # - 'parent_directory_id': <directory id of boot volume>
            # - 'file_name': 'Trash'
            # - 'file_number': 224     # a real directory!
            # - 'file_type': 0
            # - 'file_creator': 0
            # - 'nlvl_from': 2         # wut?
            # - 'nlvl_to': 1           # wut?
            # - 'extras': [
            #       Extra(type=0, name='parent_directory_name', value='Boot')
            #       Extra(type=2, name='absolute_path', value='Boot:Trash')
            #       Extra(type=65535, name='end', value=None)
            #   ]
            # 
            # alias_file_info:
            # - (alias_file_type, alias_file_creator) = ('trsh', 'MACS')
    
    return {
        'alias_record': alias_record,
        'alias_resource_info': alias_resource_info,
        'alias_file_info': alias_file_info,
    }


def _create_standard_extras_list(parent_dir_info, ancestor_dir_infos, target_macitempath):
    extras = []
    extras.append(Extra(0, 'parent_directory_name', parent_dir_info.name))
    if len(ancestor_dir_infos) > 0:
        extras.append(Extra(1, 'directory_ids', [d.id for d in ancestor_dir_infos]))
    extras.append(Extra(2, 'absolute_path', target_macitempath))
    extras.append(Extra(0xFFFF, 'end', None))
    return extras

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
