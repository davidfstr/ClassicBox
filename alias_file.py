#!/usr/bin/env python

"""
Manipulates MacOS alias files.
"""

# TODO: Extract common methods to classicbox.alias and classicbox.io.
from alias_record import Extra
from alias_record import write_alias_record
from alias_record import write_pascal_string
from alias_record import write_structure
from alias_record import write_unsigned

# TODO: Extract common methods to classicbox.resource_fork.
from resource_fork import _RESOURCE_FORK_HEADER_MEMBERS
from resource_fork import _RESOURCE_MAP_HEADER_MEMBERS
from resource_fork import _RESOURCE_REFERENCE_MEMBERS
from resource_fork import _RESOURCE_TYPE_MEMBERS

from StringIO import StringIO
import os.path
import sys

# ------------------------------------------------------------------------------

def main(args):
    # Parse arguments
    force = (len(args) >= 1 and args[0] == '-f')
    if force:
        args = args[1:]
    (output_alias_resource_fork_file, ) = args
    
    # Don't let the user inadvertently clobber an existing file
    if not force and os.path.exists(output_alias_resource_fork_file):
        sys.exit('File exists: %s' % output_alias_resource_fork_file)
        return
    
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

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
