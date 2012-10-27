"""
Manipulates MacOS resource forks.
"""

from classicbox.io import _StructMember
from classicbox.io import print_structure
from classicbox.io import read_pascal_string
from classicbox.io import read_structure
from classicbox.io import sizeof_structure
from classicbox.io import write_pascal_string
from classicbox.io import write_structure
from classicbox.io import write_unsigned


_RESOURCE_FORK_HEADER_MEMBERS = [
    _StructMember('offset_to_resource_data_area', 'unsigned', 4, None),
    _StructMember('offset_to_resource_map', 'unsigned', 4, None),
    _StructMember('resource_data_area_length', 'unsigned', 4, None),
    _StructMember('resource_map_length', 'unsigned', 4, None),
    
    # The format of this member is undocumented. If omitted, ResEdit will
    # complain that the resulting resource fork is damaged. Reserving the
    # appropriate amount of space and filling it with zeros seems to make
    # ResEdit happy.
    _StructMember('reserved_for_system_use', 'fixed_string', 256 - 16, 0),
]

_RESOURCE_MAP_HEADER_MEMBERS = [
    _StructMember('reserved_for_resource_fork_header_copy', 'fixed_string', 16, 0),
    _StructMember('reserved_for_next_resource_map_handle', 'unsigned', 4, 0),
    _StructMember('reserved_for_file_reference_number', 'unsigned', 2, 0),
    _StructMember('attributes', 'unsigned', 2, None),
    _StructMember('offset_to_resource_type_list', 'unsigned', 2, None),
    _StructMember('offset_to_resource_name_list', 'unsigned', 2, None),
    _StructMember('resource_type_count_minus_one', 'unsigned', 2, None),
]

_RESOURCE_TYPE_MEMBERS = [
    _StructMember('code', 'fixed_string', 4, None),
    _StructMember('resource_count_minus_one', 'unsigned', 2, None),
    _StructMember('offset_from_resource_type_list_to_reference_list', 'unsigned', 2, None),
]

_RESOURCE_REFERENCE_MEMBERS = [
    # TODO: This should be signed.
    #       Update definition here and the documentation for read_resource_fork().
    _StructMember('id', 'unsigned', 2, None),
    _StructMember('offset_from_resource_name_list_to_name', 'unsigned', 2, None),
        # -1 if the resource has no name
    _StructMember('attributes', 'unsigned', 1, None),
    _StructMember('offset_from_resource_data_area_to_data', 'unsigned', 3, None),
    _StructMember('reserved_for_handle', 'unsigned', 4, 0),
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

def read_resource_fork(input, read_resource_names=True, _verbose=False):
    """
    Reads a resource fork from the specified input stream, returning a
    resource map object. Resource data is not read into memory.
    
    Resource names can be skipped by passing `False` for the
    `read_resource_names` parameter.
    
    A resource map object is a dictionary of the format:
    * resource_types : list<ResourceType>
    * attributes : unsigned(2) -- Resource map attributes. See MAP_* constants.
    * absolute_offset : int -- Offset to the beginning of the resource map.
    
    A ResourceType object is a dictionary of the format:
    * code : str(4)-macroman -- Code for the resource type.
    * resources : list<Resource>
    
    A Resource object is a dictionary of the format:
    * id : unsigned(2) -- ID of this resource.
    * name : str-macroman -- Name of this resource. Only available if
                             `read_resource_names` is `True` (the default).
    * attributes : unsigned(1) -- Attributes of this resource. See RES_* constants.
    """
    
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
    resource_map['absolute_offset'] = resource_map_absolute_offset
    resource_map['resource_types'] = resource_types
    
    # Read resource names if requested
    if read_resource_names:
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
        resource_map['absolute_offset'] +
        resource_map['offset_to_resource_name_list'] +
        resource['offset_from_resource_name_list_to_name'])
    
    input.seek(absolute_offset_to_resource_name)
    resource_name = read_pascal_string(input, None)
    return resource_name


# TODO: Provide function read_resource_data()

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
    _write_resource_fork_header(output, {
        'offset_to_resource_data_area': resource_fork_header_length,
        'offset_to_resource_map': resource_fork_header_length + resource_data_area_length,
        'resource_data_area_length': resource_data_area_length,
        'resource_map_length': resource_map_length,
    })
    _write_resource_data_area_using_map(output, resource_map)
    _write_resource_map(output, resource_map)


def _write_resource_fork_header(output, resource_fork_header):
    write_structure(output, _RESOURCE_FORK_HEADER_MEMBERS, **resource_fork_header)


def _write_resource_data_area_using_map(output, resource_map):
    for type in resource_map['resource_types']:
        for resource in type['resources']:
            resource_data = resource['data']
            resource_data_length = len(resource_data)
            
            write_unsigned(output, 4, resource_data_length)
            output.write(resource_data)
            if resource_data_length & 0x1 == 1:
                output.write(chr(0))


def _write_resource_map(output, resource_map):
    _write_resource_map_header(output, resource_map)
    
    # Write resource type list
    for type in resource_map['resource_types']:
        _write_resource_type(output, type)
    
    # Write reference list area
    for type in resource_map['resource_types']:
        for resource in type['resources']:
            _write_resource_reference(output, resource)
    
    # Write resource name list
    for type in resource_map['resource_types']:
        for resource in type['resources']:
            write_pascal_string(output, None, resource['name'])
            # (Consider writing a padding byte if not word-aligned.)


def _write_resource_map_header(output, resource_map_header):
    write_structure(output, _RESOURCE_MAP_HEADER_MEMBERS, **resource_map_header)


def _write_resource_type(output, resource_type):
    write_structure(output, _RESOURCE_TYPE_MEMBERS, **resource_type)


def _write_resource_reference(output, resource_reference):
    write_structure(output, _RESOURCE_REFERENCE_MEMBERS, **resource_reference)
