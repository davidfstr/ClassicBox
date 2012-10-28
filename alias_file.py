#!/usr/bin/env python

"""
Writes MacOS alias files.
"""

# TODO: Avoid need to import private member _ALIAS_RECORD_MEMBERS
from classicbox.alias.record import _ALIAS_RECORD_MEMBERS
from classicbox.alias.record import Extra
from classicbox.alias.record import print_alias_record
from classicbox.alias.record import write_alias_record
from classicbox.disk.hfs import hfs_copy_in_from_stream
from classicbox.disk.hfs import hfs_mount
from classicbox.disk.hfs import hfs_stat
from classicbox.disk.hfs import hfspath_dirpath
from classicbox.disk.hfs import hfspath_itemname
from classicbox.disk.hfs import hfspath_normpath
from classicbox.io import fill_missing_structure_members_with_defaults
from classicbox.macbinary import FF_HAS_BEEN_INITED
from classicbox.macbinary import FF_IS_ALIAS
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
        create_alias(*args)
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

def create_alias(
        output_disk_image_filepath, output_macfilepath,
        target_disk_image_filepath, target_macitempath):
    """
    Creates an alias at the specified output path that references the specified 
    target item.
    
    Both paths reside within disk images. The target must already exist.
    """
    
    alias_file_filename = hfspath_itemname(output_macfilepath)
    
    # Create alias info for the target item
    alias_info = create_alias_info_for_item_on_disk_image(
        target_disk_image_filepath, target_macitempath)
    alias_record = alias_info['alias_record']
    alias_resource_info = alias_info['alias_resource_info']
    alias_file_info = alias_info['alias_file_info']
    
    # Serialize alias record
    alis_resource_contents_output = StringIO()
    write_alias_record(alis_resource_contents_output, alias_record)
    alis_resource_contents = alis_resource_contents_output.getvalue()
    
    # Serialize alias file resource fork
    resource_fork = StringIO()
    write_resource_fork(resource_fork, {
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
    resource_fork_contents = resource_fork.getvalue()
    
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
    
    # Write the alias file to the source path
    hfs_mount(output_disk_image_filepath)
    hfs_copy_in_from_stream(StringIO(macbinary_contents), output_macfilepath)


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
    
    # Fill in common fields of the alias record.
    # Additional fields will be filled in later depending on the alias type.
    alias_record = {
        'volume_name': volume_info['name'],
        'volume_created': volume_info['created'],
        'file_name': target_item_info.name,
        'file_number': target_item_info.id,
        # NOTE: Can't get file_created from hfsutil CLI. It outputs a date,
        #       but not with sufficient precision to compute the Mac timestamp.
        'file_created': 0,
        'nlvl_from': 1,             # assume alias file on same volume as target
        'nlvl_to': 1,               # assume alias file on same volume as target
    }
    
    # Fill in common fields of the alias file info.
    # Additional fields will be filled in later depending on the alias type.
    alias_file_info = {
        # NOTE: Alias files will additionally have the FF_HAS_BEEN_INITED bit
        #       set when the Finder sees it for the first time and adds its
        #       icon to the desktop database (if applicable).
        'alias_file_finder_flags': FF_IS_ALIAS
    }
    
    target_is_volume = target_macitempath.endswith(':')
    if target_is_volume:
        # Target is volume
        
        # A Finder-created alias file to a volume additionally contains a custom icon
        # {'ICN#', 'ics#', 'SICN'} that matches the volume that it refers to.
        # 
        # Here, we are creating an alias file without a custom icon, that will
        # appear visually as a regular document alias (ick!) but will still work.
        # Finder will actually add the custom icon to the existing alias file
        # when the user attempts to open the file.
        # 
        # If it is desired to add the custom icon in the future, it is important
        # to include the FF_HAS_CUSTOM_ICON flag for the alias file (in addition
        # to FF_IS_ALIAS).
        
        alias_record.update({
            'alias_kind': 1,            # 1 = directory
            'parent_directory_id': 1,   # special ID for parent of all volumes
            'file_created': volume_info['created'],    # special case
            'file_type': 0,         # random junk in native MacOS implementation
            'file_creator': 0,      # random junk in native MacOS implementation
            'nlvl_from': 0xFFFF,    # assume alias file on different volume from target
            'nlvl_to': 0xFFFF,      # assume alias file on different volume from target
            'extras': [
                Extra(0xFFFF, 'end', None)
            ]
        })
        
        alias_file_info.update({
            'alias_file_type': 'hdsk',
            'alias_file_creator': 'MACS',
        })
        
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
        
        alias_record.update({
            'parent_directory_id': parent_dir_info.id,
            'extras': _create_standard_extras_list(
                parent_dir_info, ancestor_dir_infos, target_macitempath)
        })
        
        if target_item_info.is_file:
            # Target is file
            alias_record.update({
                'alias_kind': 0,    # 0 = file
                'file_type': target_item_info.type,
                'file_creator': target_item_info.creator,
            })
            
            if target_item_info.type == 'APPL':
                # Target is application file
                alias_file_info.update({
                    'alias_file_type': 'adrp',
                    'alias_file_creator': target_item_info.creator,
                })
                
            else:
                # Target is document file
                alias_file_info.update({
                    'alias_file_type': target_item_info.type,
                    'alias_file_creator': target_item_info.creator,
                })
            
        else:
            # Target is folder
            alias_record.update({
                'alias_kind': 1,    # 1 = directory
                'file_type': 0,     # random junk in native MacOS implementation
                'file_creator': 0,  # random junk in native MacOS implementation
            })
            
            alias_file_info.update({
                # NOTE: Various special folders have their own special type code.
                #       For example 'Boot:System Folder:' is 'fasy',
                #       and 'Disk:Trash:' is 'trsh'. <sigh>
                #       
                #       For a complete list, see Finder.h in the Carbon headers.
                #       
                #       Using the generic folder type code (as this
                #       implementation does) results in an alias that works,
                #       but that will initially have a generic folder icon
                #       until the alias is opened.
                'alias_file_type': 'fdrp',
                'alias_file_creator': 'MACS',
            })
    
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
