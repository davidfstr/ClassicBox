#!/usr/bin/env python

"""
Reads resource forks.
"""

from classicbox.io import _StructMember
from classicbox.io import print_structure
from classicbox.io import read_pascal_string
from classicbox.io import read_structure
import sys


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
    _StructMember('id', 'unsigned', 2, None),
    _StructMember('offset_from_resource_name_list_to_name', 'unsigned', 2, None),
        # -1 if the resource has no name
    _StructMember('attributes', 'unsigned', 1, None),
    _StructMember('offset_from_resource_data_area_to_data', 'unsigned', 3, None),
    _StructMember('reserved_for_handle', 'unsigned', 4, 0),
]

# ------------------------------------------------------------------------------

VERBOSE = True
READ_RESOURCE_NAMES = True

def main(args):
    (resource_file_filepath, ) = args
    
    with open(resource_file_filepath, 'rb') as input:
        resource_fork_header = read_structure(input, _RESOURCE_FORK_HEADER_MEMBERS)
        
        if VERBOSE:
            print_structure(
                resource_fork_header,
                _RESOURCE_FORK_HEADER_MEMBERS, 'Resource Fork Header')
        
        resource_map_absolute_offset = resource_fork_header['offset_to_resource_map']
        input.seek(resource_map_absolute_offset)
        resource_map = read_structure(input, _RESOURCE_MAP_HEADER_MEMBERS)
        
        if VERBOSE:
            print_structure(
                resource_map,
                _RESOURCE_MAP_HEADER_MEMBERS, 'Resource Map')
        
        # Read all resource types
        resource_type_count = resource_map['resource_type_count_minus_one'] + 1
        resource_types = [read_resource_type(input) for i in xrange(resource_type_count)]
        
        if VERBOSE:
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
            resource_references = [read_resource_reference(input) for i in 
                xrange(resource_reference_count)]
            
            if VERBOSE:
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
        
        # Record useful information in the resource map structure
        resource_map['absolute_offset'] = resource_map_absolute_offset
        resource_map['resource_types'] = resource_types
        
        if READ_RESOURCE_NAMES:
            if VERBOSE:
                print '######################'
                print '### Resource Names ###'
                print '######################'
                print
            
            for type in resource_map['resource_types']:
                for resource in type['resources']:
                    absolute_offset_to_resource_name = (
                        resource_map['absolute_offset'] +
                        resource_map['offset_to_resource_name_list'] +
                        resource['offset_from_resource_name_list_to_name'])
                    
                    input.seek(absolute_offset_to_resource_name)
                    resource_name = read_pascal_string(input, None)
                    
                    if VERBOSE:
                        print '\'%s\' %s: "%s"' % (type['code'], resource['id'], resource_name)
            
            if VERBOSE:
                print

# ------------------------------------------------------------------------------

def read_resource_type(input):
    return read_structure(input, _RESOURCE_TYPE_MEMBERS)


def read_resource_reference(input):
    return read_structure(input, _RESOURCE_REFERENCE_MEMBERS)

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
