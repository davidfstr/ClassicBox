"""
Writes MacOS alias files.
"""

from classicbox.alias.record import Extra
from classicbox.alias.record import write_alias_record
from classicbox.disk.hfs import hfs_copy_in_from_stream
from classicbox.disk.hfs import hfs_mount
from classicbox.disk.hfs import hfs_stat
from classicbox.disk.hfs import hfspath_dirpath
from classicbox.disk.hfs import hfspath_itemname
from classicbox.disk.hfs import hfspath_normpath
from classicbox.macbinary import FF_HAS_BEEN_INITED
from classicbox.macbinary import FF_IS_ALIAS
from classicbox.macbinary import write_macbinary
from classicbox.resource_fork import write_resource_fork
from StringIO import StringIO


def create_alias_file(
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
    
    # Compute alias resource info
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
