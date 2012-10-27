#!/usr/bin/env python

"""
Manipulates MacBinary files.
"""

# TODO: Extract common methods to classicbox.io.
from resource_fork import print_structure

from classicbox.io import _StructMember
from classicbox.io import read_structure
import sys


_VERBOSE_HEADER_FORMAT = False

# MacBinary format reference: http://code.google.com/p/theunarchiver/wiki/MacBinarySpecs
_MACBINARY_HEADER_MEMBERS = [
    _StructMember('old_version', 'unsigned', 1, 0),
    _StructMember('filename', 'pascal_string', 63, None),
    _StructMember('file_type', 'fixed_string', 4, None),
    _StructMember('file_creator', 'fixed_string', 4, None),
    _StructMember('finder_flags', 'unsigned', 1, None),
    _StructMember('zero_1', 'unsigned', 1, 0),
    _StructMember('y_position', 'unsigned', 2, None),
    _StructMember('x_position', 'unsigned', 2, None),
    _StructMember('parent_directory_id', 'unsigned', 2, None),
    _StructMember('protected', 'unsigned', 1, None),
    _StructMember('zero_2', 'unsigned', 1, 0),
    _StructMember('data_fork_length', 'unsigned', 4, None),
    _StructMember('resource_fork_length', 'unsigned', 4, None),
    _StructMember('created', 'unsigned', 4, None),
    _StructMember('modified', 'unsigned', 4, None),
    _StructMember('comment_length', 'unsigned', 2, None),
    _StructMember('extra_finder_flags', 'unsigned', 1, None),
    _StructMember('signature', 'fixed_string', 4, 'mBIN'),
    _StructMember('filename_script', 'unsigned', 1, None),
    _StructMember('extended_finder_flags', 'unsigned', 1, None),
    _StructMember('reserved', 'fixed_string', 8, 0),
    _StructMember('reserved_for_unpacked_size', 'unsigned', 4, 0),
    _StructMember('reserved_for_second_header_length', 'unsigned', 2, 0),
    _StructMember('version', 'unsigned', 1, 130),
    _StructMember('min_version_to_read', 'unsigned', 1, 129),
    _StructMember('header_crc', 'unsigned', 2, None),
]

# ------------------------------------------------------------------------------

def main(args):
    (macbinary_filepath, ) = args
    
    if _VERBOSE_HEADER_FORMAT:
        print_structure_format(_MACBINARY_HEADER_MEMBERS, 'MacBinary Header Format')
    
    with open(macbinary_filepath, 'rb') as input:
        macbinary = read_macbinary(input)
        
        print_macbinary_header(macbinary['header'])
        
        print 'Data Fork'
        print '========='
        print repr(macbinary['data_fork'])
        print
        print 'Resource Fork'
        print '============='
        print repr(macbinary['resource_fork'])
        print
        print 'Comment'
        print '======='
        print repr(macbinary['comment'])
        print

# ------------------------------------------------------------------------------

def read_macbinary(input):
    macbinary_header = read_macbinary_header(input)
    data_fork = _read_macbinary_section(input, 'data_fork', macbinary_header)
    resource_fork = _read_macbinary_section(input, 'resource_fork', macbinary_header)
    comment = _read_macbinary_section(input, 'comment', macbinary_header)
    
    return {
        'header': macbinary_header,
        'data_fork': data_fork,
        'resource_fork': resource_fork,
        'comment': comment,
    }


def _read_macbinary_section(input, section_type, macbinary_header):
    section_length = macbinary_header[section_type + '_length']
    if section_length == 0:
        section = ''
    else:
        _seek_to_next_128_byte_boundary(input)
        section = input.read(section_length)
    return section


def _seek_to_next_128_byte_boundary(input):
    current_offset = input.tell()
    offset_to_next_boundary = 128 - (current_offset % 128)
    if offset_to_next_boundary < 128:
        input.seek(current_offset + offset_to_next_boundary)


def read_macbinary_header(input):
    return read_structure(input, _MACBINARY_HEADER_MEMBERS)


def print_macbinary_header(macbinary_header):
    print_structure(macbinary_header, _MACBINARY_HEADER_MEMBERS, 'MacBinary Header')

# ------------------------------------------------------------------------------

def print_structure_format(members, name):
    print name
    print '=' * len(name)
    offset = 0
    for member in members:
        print '%s: %s' % (offset, member.name)
        
        # HACK: Size calculation does not work for all member types
        member_size = member.subtype
        if member.type == 'pascal_string':
            member_size += 1
        
        offset += member_size
    print

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
