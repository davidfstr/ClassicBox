"""
Manipulates MacOS resource forks.
"""

from classicbox.io import print_structure
from classicbox.io import read_pascal_string
from classicbox.io import read_structure
from classicbox.io import read_unsigned
from classicbox.io import sizeof_structure
from classicbox.io import StructMember
from classicbox.io import write_pascal_string
from classicbox.io import write_structure
from classicbox.io import write_unsigned

import sys


_RESOURCE_FORK_HEADER_MEMBERS = [
    StructMember('offset_to_resource_data_area', 'unsigned', 4, None),
    StructMember('offset_to_resource_map', 'unsigned', 4, None),
    StructMember('resource_data_area_length', 'unsigned', 4, None),
    StructMember('resource_map_length', 'unsigned', 4, None),
    
    # The format of this member is undocumented. If omitted, ResEdit will
    # complain that the resulting resource fork is damaged. Reserving the
    # appropriate amount of space and filling it with zeros seems to make
    # ResEdit happy.
    StructMember('reserved_for_system_use', 'fixed_string', 256 - 16, 0),
]

_RESOURCE_MAP_HEADER_MEMBERS = [
    StructMember('reserved_for_resource_fork_header_copy', 'fixed_string', 16, 0),
    StructMember('reserved_for_next_resource_map_handle', 'unsigned', 4, 0),
    StructMember('reserved_for_file_reference_number', 'unsigned', 2, 0),
    StructMember('attributes', 'unsigned', 2, None),
    StructMember('offset_to_resource_type_list', 'unsigned', 2, None),
    StructMember('offset_to_resource_name_list', 'unsigned', 2, None),
    StructMember('resource_type_count_minus_one', 'unsigned', 2, None),
]

_RESOURCE_TYPE_MEMBERS = [
    StructMember('code', 'fixed_string', 4, None),
    StructMember('resource_count_minus_one', 'unsigned', 2, None),
    StructMember('offset_from_resource_type_list_to_reference_list', 'unsigned', 2, None),
]

_RESOURCE_REFERENCE_MEMBERS = [
    StructMember('id', 'signed', 2, None),
    StructMember('offset_from_resource_name_list_to_name', 'unsigned', 2, None),
        # -1 if the resource has no name
    StructMember('attributes', 'unsigned', 1, None),
    StructMember('offset_from_resource_data_area_to_data', 'unsigned', 3, None),
    StructMember('reserved_for_handle', 'unsigned', 4, 0),
]

# Resource Attributes
RES_SYS_HEAP = 64       # set if read into system heap
RES_PURGEABLE = 32      # set if purgeable
RES_LOCKED = 16         # set if locked
RES_PROTECTED = 8       # set if protected
RES_PRELOAD = 4         # set if to be preloaded
RES_CHANGED = 2         # set if to be written to resource fork

# Resource Map Attributes
MAP_READ_ONLY = 128     # set to make file read-only
MAP_COMPACT = 64        # set to compact file on update
MAP_CHANGED = 32        # set to write map on update

# ------------------------------------------------------------------------------

def read_resource_fork(
        input,
        read_all_resource_names=True,
        read_all_resource_data=False,
        read_everything=False,
        _verbose=False):
    """
    Reads a resource fork from the specified input stream, returning a
    resource map object. Resource data is not read into memory by default.
    
    All resource names can be skipped by passing `False` for the
    `read_all_resource_names` parameter. Skipping the names uses less memory.
    
    All resource data can be read by passing `True` for the `read_all_resource_data`
    parameter. This is not recommended unless the resource fork is known
    to fit into memory completely. Instead, most callers should use
    read_resource_data() to read individual resources of interest.
    
    A resource map object is a dictionary of the format:
    * resource_types : list<ResourceType>
    * attributes : unsigned(2) -- Resource map attributes. See MAP_* constants.
    * absolute_offset : int -- Offset to the beginning of the resource map.
    
    A ResourceType object is a dictionary of the format:
    * code : str(4)-macroman -- Code for the resource type.
    * resources : list<Resource>
    
    A Resource object is a dictionary of the format:
    * id : signed(2) -- ID of this resource.
    * name : str-macroman -- Name of this resource.
                             Only available if `read_all_resource_names` is
                             True (the default).
    * attributes : unsigned(1) -- Attributes of this resource. See RES_* constants.
    * data : str-binary -- Data of this resource.
                           Only available if `read_all_resource_data` is True.
    
    Other undocumented keys may be present in the above dictionary types.
    Callers should not rely upon such keys.
    
    Arguments:
    * input -- Input stream to read the resource fork from.
    * read_all_resource_names : bool -- Whether to read all resource names.
                                        Defaults to True.
    * read_all_resource_data : bool - Whether to read all resource data.
                                      Defaults to False.
    * read_everything : bool -- Convenience argument that implies
                                `read_all_resource_names` and
                                `read_all_resource_data` if True.
                                Defaults to False.
    
    Returns a resource map object.
    """
    
    if read_everything:
        read_all_resource_names = True
        read_all_resource_data = True
    
    # Read resource fork header
    resource_fork_header = read_structure(input, _RESOURCE_FORK_HEADER_MEMBERS)
    
    if _verbose:
        print_structure(
            resource_fork_header,
            _RESOURCE_FORK_HEADER_MEMBERS, 'Resource Fork Header')
    
    # Read resource map header
    resource_map_absolute_offset = resource_fork_header['offset_to_resource_map']
    input.seek(resource_map_absolute_offset)
    resource_map_header = read_structure(input, _RESOURCE_MAP_HEADER_MEMBERS)
    
    if _verbose:
        print_structure(
            resource_map_header,
            _RESOURCE_MAP_HEADER_MEMBERS, 'Resource Map')
    
    # Read all resource types
    resource_type_count = resource_map_header['resource_type_count_minus_one'] + 1
    resource_types = [_read_resource_type(input) for i in xrange(resource_type_count)]
    
    if _verbose:
        print '######################'
        print '### Resource Types ###'
        print '######################'
        print
        for type in resource_types:
            print_structure(
                type,
                _RESOURCE_TYPE_MEMBERS, 'Resource Type')
    
    # Read all resource references
    for type in resource_types:
        # Read resource reference list for this resource type
        resource_reference_count = type['resource_count_minus_one'] + 1
        resource_references = [_read_resource_reference(input) for i in 
            xrange(resource_reference_count)]
        
        if _verbose:
            print '########################'
            print '### "%s" Resources ###' % type['code']
            print '########################'
            print
            for resource in resource_references:
                print_structure(
                    resource,
                    _RESOURCE_REFERENCE_MEMBERS, 'Resource')
        
        # Save the resource references in the associated resource type structure
        type['resources'] = resource_references
    
    # Create resource map object with contents of header
    resource_map = resource_map_header
    
    # Record useful information in the resource map structure
    resource_map['resource_fork_header'] = resource_fork_header
    resource_map['resource_types'] = resource_types
    
    # Read resource names if requested
    if read_all_resource_names:
        if _verbose:
            print '######################'
            print '### Resource Names ###'
            print '######################'
            print
        
        for type in resource_map['resource_types']:
            for resource in type['resources']:
                resource_name = read_resource_name(input, resource_map, resource)
                
                # Save the resource name in the resource reference structure
                resource['name'] = resource_name
                
                if _verbose:
                    print '\'%s\' %s: "%s"' % (type['code'], resource['id'], resource_name)
        
        if _verbose:
            print
    
    # Read resource data if requested
    if read_all_resource_data:
        for type in resource_map['resource_types']:
            for resource in type['resources']:
                resource_data = read_resource_data(input, resource_map, resource)
                
                # Save the resource name in the resource reference structure
                resource['data'] = resource_data
    
    return resource_map


def _read_resource_type(input):
    return read_structure(input, _RESOURCE_TYPE_MEMBERS)


def _read_resource_reference(input):
    return read_structure(input, _RESOURCE_REFERENCE_MEMBERS)


def read_resource_name(input, resource_map, resource):
    """
    Reads the name of the specified resource.
    """
    absolute_offset_to_resource_name = (
        resource_map['resource_fork_header']['offset_to_resource_map'] +
        resource_map['offset_to_resource_name_list'] +
        resource['offset_from_resource_name_list_to_name'])
    
    input.seek(absolute_offset_to_resource_name)
    resource_name = read_pascal_string(input, None)
    return resource_name


def read_resource_data(input, resource_map, resource):
    """
    Reads the data of the specified resource.
    """
    absolute_offset_to_resource_data = (
        resource_map['resource_fork_header']['offset_to_resource_data_area'] +
        resource['offset_from_resource_data_area_to_data'])
    
    input.seek(absolute_offset_to_resource_data)
    resource_data_length = read_unsigned(input, 4)
    resource_data = input.read(resource_data_length)
    return resource_data

# ------------------------------------------------------------------------------

def write_resource_fork(output, resource_map, _preserve_order=True):
    """
    Writes a resource fork to the specified output stream using the specified
    resource map. All resource names and data must be read into memory.
    
    The specified resource map must be in the format documented by
    `read_resource_fork()`. (It is not necessary for undocumented keys to be
    present.)
    """
    resource_types = resource_map['resource_types']
    
    # Verify that resource names and data are present
    for type in resource_types:
        for resource in type['resources']:
            if 'name' not in resource:
                raise ValueError('Missing name for "%s" resource %d.' % (
                    type.code, resource['id']))
            if 'data' not in resource:
                raise ValueError('Missing data for "%s" resource %d.' % (
                    type.code, resource['id']))
    
    # Compute ordering of resources in resource data area and name list
    if not _preserve_order:
        resources_in_resource_data_area = []
        resources_in_resource_name_list = []
        for type in resource_types:
            for resource in type['resources']:
                resources_in_resource_data_area.append(resource)
                resources_in_resource_name_list.append(resource)
    else:
        # Compute ordering of resources in resource data area
        resources_in_resource_data_area = []
        for type in resource_types:
            for resource in type['resources']:
                resources_in_resource_data_area.append((
                    # (Allow undocumented key to be missing. New resources sort last.)
                    resource.get('offset_from_resource_data_area_to_data', sys.maxint),
                    resource
                ))
        resources_in_resource_data_area.sort()  # NOTE: depends on stable sort
        resources_in_resource_data_area = (
            [resource for (_, resource) in resources_in_resource_data_area]
        )
        
        # Compute ordering of resources in resource name list
        resources_in_resource_name_list = []
        for type in resource_types:
            for resource in type['resources']:
                resources_in_resource_name_list.append((
                    # (Allow undocumented key to be missing. New resources sort last.)
                    resource.get('offset_from_resource_name_list_to_name', sys.maxint),
                    resource
                ))
        resources_in_resource_name_list.sort()  # NOTE: depends on stable sort
        resources_in_resource_name_list = (
            [resource for (_, resource) in resources_in_resource_name_list]
        )
    
    # Compute offsets within the resource data area
    next_data_offset = 0
    for resource in resources_in_resource_data_area:
        data_size = 4 + len(resource['data'])
        
        resource['offset_from_resource_data_area_to_data'] = next_data_offset
        next_data_offset += data_size
    resource_data_area_length = next_data_offset
    
    # Compute offsets within the resource name list
    next_name_offset = 0
    for resource in resources_in_resource_name_list:
        if len(resource['name']) == 0:
            resource['offset_from_resource_name_list_to_name'] = 0xFFFF
        else:
            name_size = 1 + len(resource['name'])
            
            resource['offset_from_resource_name_list_to_name'] = next_name_offset
            next_name_offset += name_size
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
    
    # Fill in resource fork header
    # (Allow undocumented key to be missing)
    resource_fork_header = resource_map.get('resource_fork_header', {})
    resource_fork_header_length = sizeof_structure(_RESOURCE_FORK_HEADER_MEMBERS)
    resource_fork_header.update({
        'offset_to_resource_data_area': resource_fork_header_length,
        'offset_to_resource_map': resource_fork_header_length + resource_data_area_length,
        'resource_data_area_length': resource_data_area_length,
        'resource_map_length': resource_map_length,
    })
    
    # Write everything
    _write_resource_fork_header(output, resource_fork_header)
    _write_resource_data_area_using_map(output, resource_map, resources_in_resource_data_area)
    _write_resource_map(output, resource_map, resources_in_resource_name_list)


def _write_resource_fork_header(output, resource_fork_header):
    write_structure(output, _RESOURCE_FORK_HEADER_MEMBERS, resource_fork_header)


def _write_resource_data_area_using_map(output, resource_map, resources_in_resource_data_area):
    for resource in resources_in_resource_data_area:
        resource_data = resource['data']
        resource_data_length = len(resource_data)
        
        write_unsigned(output, 4, resource_data_length)
        output.write(resource_data)


def _write_resource_map(output, resource_map, resources_in_resource_name_list):
    _write_resource_map_header(output, resource_map)
    
    # Write resource type list
    for type in resource_map['resource_types']:
        _write_resource_type(output, type)
    
    # Write reference list area
    for type in resource_map['resource_types']:
        for resource in type['resources']:
            _write_resource_reference(output, resource)
    
    # Write resource name list
    for resource in resources_in_resource_name_list:
        write_pascal_string(output, None, resource['name'])
        # (Consider writing a padding byte if not word-aligned.)


def _write_resource_map_header(output, resource_map_header):
    write_structure(output, _RESOURCE_MAP_HEADER_MEMBERS, resource_map_header)


def _write_resource_type(output, resource_type):
    write_structure(output, _RESOURCE_TYPE_MEMBERS, resource_type)


def _write_resource_reference(output, resource_reference):
    write_structure(output, _RESOURCE_REFERENCE_MEMBERS, resource_reference)
