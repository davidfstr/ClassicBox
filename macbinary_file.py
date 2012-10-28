#!/usr/bin/env python

"""
Manipulates MacBinary files.
"""

from classicbox.io import offset_to_structure_member
from classicbox.io import print_structure
from classicbox.io import print_structure_format
from classicbox.io import read_structure
from classicbox.io import save_stream_position
from classicbox.io import sizeof_structure_member
from classicbox.io import StructMember
from classicbox.io import write_structure
from classicbox.io import write_unsigned
from StringIO import StringIO
import sys


# MacBinary format reference: http://code.google.com/p/theunarchiver/wiki/MacBinarySpecs
_MACBINARY_HEADER_MEMBERS = [
    StructMember('old_version', 'unsigned', 1, 0),
    StructMember('filename', 'pascal_string', 63, None),
    StructMember('file_type', 'fixed_string', 4, None),
    StructMember('file_creator', 'fixed_string', 4, None),
    StructMember('finder_flags', 'unsigned', 1, None),
    StructMember('zero_1', 'unsigned', 1, 0),
    StructMember('y_position', 'unsigned', 2, None),
    StructMember('x_position', 'unsigned', 2, None),
    StructMember('parent_directory_id', 'unsigned', 2, None),
    StructMember('protected', 'unsigned', 1, None),
    StructMember('zero_2', 'unsigned', 1, 0),
    StructMember('data_fork_length', 'unsigned', 4, None),
    StructMember('resource_fork_length', 'unsigned', 4, None),
    StructMember('created', 'unsigned', 4, None),
    StructMember('modified', 'unsigned', 4, None),
    StructMember('comment_length', 'unsigned', 2, None),
    StructMember('extra_finder_flags', 'unsigned', 1, None),
    StructMember('signature', 'fixed_string', 4, 'mBIN'),
    StructMember('filename_script', 'unsigned', 1, None),
    StructMember('extended_finder_flags', 'unsigned', 1, None),
    StructMember('reserved', 'fixed_string', 8, 0),
    StructMember('reserved_for_unpacked_size', 'unsigned', 4, 0),
    StructMember('reserved_for_second_header_length', 'unsigned', 2, 0),
    StructMember('version', 'unsigned', 1, 130),
    StructMember('min_version_to_read', 'unsigned', 1, 129),
    StructMember('header_crc', 'unsigned', 2, None),
    # NOTE: Somebody forgot to include this field in the MacBinary II and III
    #       documentation, although it is in the MacBinary I docs. Grr.
    StructMember('reserved_for_computer_type_and_os_id', 'unsigned', 2, None),
]

# ------------------------------------------------------------------------------

_VERBOSE_HEADER_FORMAT = False

def main(args):
    (command, macbinary_filepath, ) = args
    
    if _VERBOSE_HEADER_FORMAT:
        print_structure_format(_MACBINARY_HEADER_MEMBERS, 'MacBinary Header Format')
    
    with open(macbinary_filepath, 'rb') as input:
        macbinary = read_macbinary(input)
    
    if command == 'info':
        print_macbinary(macbinary)
    
    elif command == 'test_read_write':
        output_macbinary = StringIO()
        write_macbinary(output_macbinary, macbinary)
        
        with open(macbinary_filepath, 'rb') as file:
            expected_output = file.read()
        actual_output = output_macbinary.getvalue()
        
        matches = (actual_output == expected_output)
        print 'Matches? ' + ('yes' if matches else 'no')
        if not matches:
            print '    Expected: ' + repr(expected_output)
            print '    Actual:   ' + repr(actual_output)
            print
    
    else:
        sys.exit('Unrecognized command: %s' % command)
        return

# ------------------------------------------------------------------------------

def read_macbinary(input):
    macbinary_header = read_macbinary_header(input)
    data_fork = _read_macbinary_section(input, 'data_fork', macbinary_header)
    resource_fork = _read_macbinary_section(input, 'resource_fork', macbinary_header)
    comment = _read_macbinary_section(input, 'comment', macbinary_header)
    
    # Reclassify MacBinary header as MacBinary object
    macbinary = macbinary_header
    
    # Record remaining components in the MacBinary object
    macbinary.update({
        'data_fork': data_fork,
        'resource_fork': resource_fork,
        'comment': comment,
    })
    
    return macbinary


def read_macbinary_header(input):
    return read_structure(input, _MACBINARY_HEADER_MEMBERS)


def _read_macbinary_section(input, section_type, macbinary_header):
    section_length = macbinary_header[section_type + '_length']
    if section_length == 0:
        section = ''
    else:
        section = input.read(section_length)
        _seek_to_next_128_byte_boundary(input)
    return section


def _seek_to_next_128_byte_boundary(input):
    current_offset = input.tell()
    offset_to_next_boundary = 128 - (current_offset % 128)
    if offset_to_next_boundary < 128:
        input.seek(current_offset + offset_to_next_boundary)

# ------------------------------------------------------------------------------

def write_macbinary(output, macbinary):
    macbinary_header = macbinary
    data_fork = macbinary['data_fork']
    resource_fork = macbinary['resource_fork']
    comment = macbinary['comment']
    
    # Fill in header
    macbinary_header.update({
        'data_fork_length': len(data_fork),
        'resource_fork_length': len(resource_fork),
        'comment_length': len(comment),
    })
    
    # Write everything
    write_macbinary_header(output, macbinary)
    _write_macbinary_section(output, data_fork)
    _write_macbinary_section(output, resource_fork)
    _write_macbinary_section(output, comment)


def write_macbinary_header(output, macbinary_header):
    macbinary_header['header_crc'] = 0
    write_structure(output, _MACBINARY_HEADER_MEMBERS, macbinary_header)
    
    with save_stream_position(output):
        offset_to_crc_member = offset_to_structure_member(
            _MACBINARY_HEADER_MEMBERS, 'header_crc')
        
        # Compute CRC of header
        output.seek(0)
        header_section_to_crc = output.read(offset_to_crc_member)
        header_crc = _compute_macbinary_crc(header_section_to_crc)
        
        # Write CRC to header
        write_unsigned(output, 2, header_crc)
        
        # Save CRC to MacBinary object in case the caller is interested
        macbinary_header['header_crc'] = header_crc


def _write_macbinary_section(output, section_content):
    if len(section_content) > 0:
        output.write(section_content)
        _pad_until_next_128_byte_boundary(output)


def _pad_until_next_128_byte_boundary(output):
    current_offset = output.tell()
    offset_to_next_boundary = 128 - (current_offset % 128)
    if offset_to_next_boundary < 128:
        for i in xrange(offset_to_next_boundary):
            output.write(chr(0))

# ------------------------------------------------------------------------------

_CRC_MAGIC = (
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
    0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
    0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,

    0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
    0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
    0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,

    0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
    0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
    0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,

    0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
    0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
    0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
    0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,

    0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
    0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
    0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,

    0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
    0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
    0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,

    0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
    0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
    0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,

    0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
    0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
    0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
    0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0
)

def _compute_macbinary_crc(data, crc=0):
    """
    Computes a MacBinary II style CRC checksum of the specified data.
    """
    for c in data:
        crc ^= ord(c) << 8
        crc = ((crc << 8) ^ _CRC_MAGIC[crc >> 8]) & 0xFFFF
    return crc

# ------------------------------------------------------------------------------

def print_macbinary(macbinary):
    print_macbinary_header(macbinary)
    
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


def print_macbinary_header(macbinary_header):
    print_structure(macbinary_header, _MACBINARY_HEADER_MEMBERS, 'MacBinary Header')

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
