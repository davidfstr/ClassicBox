#!/usr/bin/env python

"""
Manipulates resource forks.
"""

# TODO: Extract common methods to classicbox.io.
from alias_macos import read_structure
from alias_macos import _StructMember

import sys


_RESOURCE_FORK_HEADER_MEMBERS = [
    _StructMember('offset_to_resource_data_area', 'unsigned', 4, None),
    _StructMember('offset_to_resource_map', 'unsigned', 4, None),
    _StructMember('resource_data_area_length', 'unsigned', 4, None),
    _StructMember('resource_map_length', 'unsigned', 4, None),
]

_RESOURCE_MAP_HEADER_MEMBERS = [
    _StructMember('reserved_for_resource_fork_header_copy', 'fixed_string', 16, None),
    _StructMember('reserved_for_next_resource_map_handle', 'unsigned', 4, None),
    _StructMember('reserved_for_file_reference_number', 'unsigned', 2, None),
    _StructMember('resource_fork_attributes', 'unsigned', 2, None),
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
    _StructMember('reserved_for_handle', 'unsigned', 4, None),
]

# ------------------------------------------------------------------------------

VERBOSE = True

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
        # FIXME: Simplify these structures as list comprehensions
        resource_types = []
        for i in xrange(resource_map['resource_type_count_minus_one'] + 1):
            resource_types.append(read_resource_type(input))
        
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
            resource_references = []
            for i in xrange(type['resource_count_minus_one'] + 1):
                resource_references.append(read_resource_reference(input))
            
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


def print_structure(structure, members, name):
    print name
    print '=' * len(name)
    for member in members:
        value = structure[member.name]
        print '%s: %s' % (member.name, repr(value))
    print

# ------------------------------------------------------------------------------

def read_resource_type(input):
    return read_structure(input, _RESOURCE_TYPE_MEMBERS)


def read_resource_reference(input):
    return read_structure(input, _RESOURCE_REFERENCE_MEMBERS)

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
