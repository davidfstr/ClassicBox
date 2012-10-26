#!/usr/bin/env python

"""
Manipulates MacOS alias files.
"""

# TODO: Extract common methods to classicbox.alias and classicbox.io.
from alias_record import _ALIAS_RECORD_MEMBERS
from alias_record import Extra
from alias_record import print_alias_record
from alias_record import write_alias_record
from alias_record import write_pascal_string
from alias_record import write_structure
from alias_record import write_unsigned

# TODO: Extract common methods to classicbox.resource_fork.
from resource_fork import _RESOURCE_FORK_HEADER_MEMBERS
from resource_fork import _RESOURCE_MAP_HEADER_MEMBERS
from resource_fork import _RESOURCE_REFERENCE_MEMBERS
from resource_fork import _RESOURCE_TYPE_MEMBERS

from classicbox.disk.hfs import hfs_mount
from classicbox.disk.hfs import hfs_stat
from classicbox.disk.hfs import hfspath_dirpath
from classicbox.disk.hfs import hfspath_normpath
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
    output_alias_resource_fork_file = args.pop(0)
    
    # Don't let the user inadvertently clobber an existing file
    if not force and os.path.exists(output_alias_resource_fork_file):
        sys.exit('File exists: %s' % output_alias_resource_fork_file)
        return
    
    if command == 'write_fixed':
        write_fixed_alias_resource_fork_file(output_alias_resource_fork_file)
    elif command == 'write_targeted':
        write_targeted_alias_resource_fork_file(output_alias_resource_fork_file, args)
    else:
        sys.exit('Unknown command: %s' % command)
        return

def write_fixed_alias_resource_fork_file(output_alias_resource_fork_file):
    """
    Writes a fixed alias resource fork file to disk.
    """
    
    # "AppAlias.rsrc.dat"
    alis_resource_contents_output = StringIO()
    write_alias_record(alis_resource_contents_output,
        alias_kind=0,
        volume_name='Boot',
        volume_created=3431272487,
        parent_directory_id=542,
        file_name='app',
        file_number=543,
        # NOTE: Can't get file_created reliably from hfsutil CLI
        file_created=3265652246,
        file_type='APPL',
        file_creator='AQt7',
        nlvl_from=1,
        nlvl_to=1,
        extras=[
            Extra(0, 'parent_directory_name', 'B'),
            Extra(1, 'directory_ids', [542, 541, 484]),
            Extra(2, 'absolute_path', 'Boot:AutQuit7:A:B:app'),
            Extra(0xFFFF, 'end', None)
        ])
    alis_resource_contents = alis_resource_contents_output.getvalue()
    
    with open(output_alias_resource_fork_file, 'wb') as resource_fork_output:
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


def write_targeted_alias_resource_fork_file(output_alias_resource_fork_file, args):
    """
    Writes an alias resource fork file that targets a particular
    item in an HFS disk image.
    """
    
    # Parse arguments
    (disk_image_filepath, target_macitempath) = args
    
    volume_info = hfs_mount(disk_image_filepath)
    
    target_macitempath = hfspath_normpath(target_macitempath)
    target_is_volume = target_macitempath.endswith(':')
    
    target_item_info = hfs_stat(target_macitempath)
    
    alias_resource_info = dict(
        type='alis',
        id=0,
        name=target_item_info.name + ' alias',
        attributes=0
    )
    
    if target_is_volume:
        # Target is volume
        alias_record = dict(
            alias_kind=1,                           # 1 = directory
            volume_name=volume_info['name'],
            volume_created=volume_info['created'],
            parent_directory_id=1,                  # magic?
            file_name=target_item_info.name,
            file_number=target_item_info.id,
            file_created=volume_info['created'],    # special case
            file_type=0,    # random junk in native MacOS implementation
            file_creator=0, # random junk in native MacOS implementation
            nlvl_from=0xFFFF,   # assume alias file on different volume from target
            nlvl_to=0xFFFF,     # assume alias file on different volume from target
            extras=[
                Extra(0xFFFF, 'end', None)
            ]
        )
        
        alias_file_info = dict(
            alias_file_type='hdsk',
            alias_file_creator='MACS'
            # NOTE: The alias resource fork contains, in addition to 'alis',
            #       resources of type {'ICN#', 'ics#', 'SICN'}.
            #       Hence the USE_CUSTOM_ICON flag here.
            #       I suspect that omitting the icon won't prevent the alias
            #       from working, although Finder may draw it oddly.
            #alias_file_flags=(ALIAS | INITED | USE_CUSTOM_ICON)
        )
        
    else:
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
            alias_record = dict(
                alias_kind=0,                       # 0 = file
                volume_name=volume_info['name'],
                volume_created=volume_info['created'],
                parent_directory_id=parent_dir_info.id,
                file_name=target_item_info.name,
                file_number=target_item_info.id,
                # NOTE: Can't get file_created reliably from hfsutil CLI
                file_created=0,
                file_type=target_item_info.type,
                file_creator=target_item_info.creator,
                nlvl_from=1,    # assume alias file on same volume as target
                nlvl_to=1,      # assume alias file on same volume as target
                extras=_create_standard_extras_list(
                    parent_dir_info, ancestor_dir_infos, target_macitempath)
            )
            
            if target_item_info.type == 'APPL':
                # Target is application file
                alias_file_info = dict(
                    alias_file_type='adrp',
                    alias_file_creator=target_item_info.creator
                    #alias_file_flags=(ALIAS | INITED)
                )
                
            else:
                # Target is document file
                alias_file_info = dict(
                    alias_file_type=target_item_info.type,
                    alias_file_creator='MPS '
                    #alias_file_flags=(ALIAS | INITED)
                )
            
        else:
            # Target is folder
            alias_record = dict(
                alias_kind=1,                       # 1 = directory
                volume_name=volume_info['name'],
                volume_created=volume_info['created'],
                parent_directory_id=parent_dir_info.id,
                file_name=target_item_info.name,
                file_number=target_item_info.id,
                # NOTE: Can't get file_created reliably from hfsutil CLI
                file_created=0,
                file_type=0,    # random junk in native MacOS implementation
                file_creator=0, # random junk in native MacOS implementation
                nlvl_from=1,    # assume alias file on same volume as target
                nlvl_to=1,      # assume alias file on same volume as target
                extras=_create_standard_extras_list(
                    parent_dir_info, ancestor_dir_infos, target_macitempath)
            )
            
            alias_file_info = dict(
                # NOTE: Type is 'fasy' if target is the System Folder. <sigh>
                alias_file_type='fdrp',
                alias_file_creator='MACS'
                #alias_file_flags=(ALIAS | INITED)
            )
            
            # Fun trivia! An alias to the Trash has:
            # 
            # - alias_kind=1        # 1 = directory
            # - parent_directory_id=<directory id of boot volume>
            # - file_name='Trash'
            # - file_number=224     # a real directory!
            # - file_type=0
            # - file_creator=0
            # - nlvl_from=2         # wut?
            # - nlvl_to=1           # wut?
            # - extras:
            #       Extra(type=0, name='parent_directory_name', value='Boot')
            #       Extra(type=2, name='absolute_path', value='Boot:Trash')
            #       Extra(type=65535, name='end', value=None)
            # 
            # - (alias_file_type, alias_file_creator) = ('trsh', 'MACS')
    
    # Outputs from above logic:
    # (1) alias_record
    # (2) alias_resource_info
    # (3) alias_file_info
    
    # Display the resulting alias record
    fill_missing_structure_members_with_defaults(_ALIAS_RECORD_MEMBERS, alias_record)
    print_alias_record(alias_record)
    
    # TODO: Write to file: output_alias_resource_fork_file


def _create_standard_extras_list(parent_dir_info, ancestor_dir_infos, target_macitempath):
    extras = []
    extras.append(Extra(0, 'parent_directory_name', parent_dir_info.name))
    if len(ancestor_dir_infos) > 0:
        extras.append(Extra(1, 'directory_ids', [d.id for d in ancestor_dir_infos]))
    extras.append(Extra(2, 'absolute_path', target_macitempath))
    extras.append(Extra(0xFFFF, 'end', None))
    return extras

# ------------------------------------------------------------------------------

def write_resource_fork(output, resource_map):
    resource_types = resource_map['resource_types']
    
    # Compute offsets within the resource data area and resource name list,
    # that resource references refer to
    next_name_offset = 0
    next_data_offset = 0
    for type in resource_types:
        for resource in type['resources']:
            if len(resource['name']) == 0:
                resource['offset_from_resource_name_list_to_name'] = 0xFFFF
            else:
                name_size = 1 + len(resource['name'])
                
                resource['offset_from_resource_name_list_to_name'] = next_name_offset
                next_name_offset += name_size
            
            data_size = 4 + len(resource['data'])
            if data_size & 0x1 == 1:
                data_size += 1
            
            resource['offset_from_resource_data_area_to_data'] = next_data_offset
            next_data_offset += data_size
            
    resource_data_area_length = next_data_offset
    resource_name_list_length = next_name_offset
    
    resource_map_header_length = (
        sizeof_structure(_RESOURCE_MAP_HEADER_MEMBERS) +
        # (Apparently the 'resource_type_count_minus_one' field at the end of
        #  the resource map header is considered part of the resource type list)
        -2
    )
    resource_type_list_length = (
        # (Apparently the 'resource_type_count_minus_one' field at the end of
        #  the resource map header is considered part of the resource type list)
        2 +
        len(resource_types) * sizeof_structure(_RESOURCE_TYPE_MEMBERS))
    
    # Compute offsets within the reference list area,
    # that resource types refer to
    next_reference_list_area_offset = 0
    for type in resource_types:
        resource_count = len(type['resources'])
        reference_list_length = resource_count * sizeof_structure(_RESOURCE_REFERENCE_MEMBERS)
        
        if resource_count == 0:
            raise ValueError(
                ('Resource type "%s" has no resources and should be removed ' +
                 'from the resource map before serialization') % type['code'])
        type['resource_count_minus_one'] = resource_count - 1
        
        type['offset_from_resource_type_list_to_reference_list'] = (
            resource_type_list_length +
            next_reference_list_area_offset
        )
        next_reference_list_area_offset += reference_list_length
    
    reference_list_area_length = next_reference_list_area_offset
    
    # Compute offsets within the resource map,
    # that the resource map header refers to
    resource_map_length = (
        resource_map_header_length +
        resource_type_list_length +
        reference_list_area_length +
        resource_name_list_length
    )
    
    resource_map['offset_to_resource_type_list'] = resource_map_header_length
    resource_map['offset_to_resource_name_list'] = (
        resource_map_header_length + 
        resource_type_list_length + 
        reference_list_area_length
    )
    
    if len(resource_types) == 0:
        raise ValueError(
            'No resource types. ' +
            'Cannot serialize resource fork without at least one type.')
    resource_map['resource_type_count_minus_one'] = len(resource_types) - 1
    
    resource_fork_header_length = sizeof_structure(_RESOURCE_FORK_HEADER_MEMBERS)
    
    # Write everything
    write_resource_fork_header(output, {
        'offset_to_resource_data_area': resource_fork_header_length,
        'offset_to_resource_map': resource_fork_header_length + resource_data_area_length,
        'resource_data_area_length': resource_data_area_length,
        'resource_map_length': resource_map_length,
    })
    write_resource_data_area_using_map(output, resource_map)
    write_resource_map(output, resource_map)


def write_resource_fork_header(output, resource_fork_header):
    write_structure(output, _RESOURCE_FORK_HEADER_MEMBERS, **resource_fork_header)


def write_resource_data_area_using_map(output, resource_map):
    for type in resource_map['resource_types']:
        for resource in type['resources']:
            resource_data = resource['data']
            resource_data_length = len(resource_data)
            
            write_unsigned(output, 4, resource_data_length)
            output.write(resource_data)
            if resource_data_length & 0x1 == 1:
                output.write(chr(0))


def write_resource_map(output, resource_map):
    write_resource_map_header(output, resource_map)
    
    # Write resource type list
    for type in resource_map['resource_types']:
        write_resource_type(output, type)
    
    # Write reference list area
    for type in resource_map['resource_types']:
        for resource in type['resources']:
            write_resource_reference(output, resource)
    
    # Write resource name list
    for type in resource_map['resource_types']:
        for resource in type['resources']:
            write_pascal_string(output, None, resource['name'])
            # (Consider writing a padding byte if not word-aligned.)


def write_resource_map_header(output, resource_map_header):
    write_structure(output, _RESOURCE_MAP_HEADER_MEMBERS, **resource_map_header)


def write_resource_type(output, resource_type):
    write_structure(output, _RESOURCE_TYPE_MEMBERS, **resource_type)


def write_resource_reference(output, resource_reference):
    write_structure(output, _RESOURCE_REFERENCE_MEMBERS, **resource_reference)

# ------------------------------------------------------------------------------

def sizeof_structure(members):
    total_size = 0
    for member in members:
        if member.type not in ('unsigned', 'fixed_string'):
            raise ValueError('Don\'t know how to find the size of member of type: %s' % member.type)
        sizeof_member = member.subtype
        
        total_size += sizeof_member
    
    return total_size

def fill_missing_structure_members_with_defaults(structure_members, structure):
    for member in structure_members:
        if member.name not in structure:
            structure[member.name] = member.default_value

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
