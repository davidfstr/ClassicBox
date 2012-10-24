#!/usr/bin/env python

"""
Manipulates MacOS alias files.
"""

from collections import namedtuple
from StringIO import StringIO
import sys


_StructMember = namedtuple(
    '_StructMember',
    ('name', 'type', 'subtype', 'default_value'))

# Alias file format reference: http://xhelmboyx.tripod.com/formats/alias-layout.txt
_ALIAS_RECORD_MEMBERS = [
    _StructMember('user_type_name',         'fixed_string', 4,  0),     # 0 = none
    _StructMember('record_size',            'unsigned', 2,      None),
    _StructMember('record_version',         'unsigned', 2,      2),     # 2 = current version
    _StructMember('alias_kind',             'unsigned', 2,      None),  # 0 = file, 1 = directory
    _StructMember('volume_name',            'pascal_string', 27, None),
    _StructMember('volume_created',         'unsigned', 4,      0),     # may be 0; seconds since 1904
    _StructMember('volume_signature',       'fixed_string', 2,  'BD'),  # 'RW' = MFS, 'BD' = HFS (or foreign), 'H+' = HFS+
    _StructMember('drive_type',             'unsigned', 2,      0),
        # 0 = Fixed HD, 1 = Network Disk,
        # 2 = 400kB FD, 3 = 800kB FD,
        # 4 = 1.4MB FD, 5 = Other Ejectable Media
    _StructMember('parent_directory_id',    'unsigned', 4,      0),     # may be 0
    _StructMember('file_name',              'pascal_string', 63, None),
    _StructMember('file_number',            'unsigned', 4,      0),     # may be 0
    _StructMember('file_created',           'unsigned', 4,      0),     # may be 0; seconds since 1904
    _StructMember('file_type',              'fixed_string', 4,  0),     # may be 0
    _StructMember('file_creator',           'fixed_string', 4,  0),     # may be 0
    _StructMember('nlvl_from',              'unsigned', 2,      None),
    _StructMember('nlvl_to',                'unsigned', 2,      None),
        # -1 = alias on different volume,
        # 1 = alias and target in same directory
    _StructMember('volume_attributes',      'unsigned', 4,      0),     # may be 0
    _StructMember('volume_filesystem_id',   'fixed_string', 2,  0),     # 0 for MFS or HFS
    _StructMember('reserved',               'fixed_string', 10, 0),
    _StructMember('extra',                  'until_eof', None,  None),
]

# ------------------------------------------------------------------------------

def main(args):
    # Path to a file that (in its data fork) contains the contents of an 'alis'
    # resource, which is the primary resource contained in an alias file
    (command, alias_resource_file_filepath) = args
    
    if command == 'info':
        with open(alias_resource_file_filepath, 'rb') as input:
            alias_record = read_alias_record(input)
        
        print_alias_record(alias_record)
        
    elif command == 'test':
        with open(alias_resource_file_filepath, 'rb') as input:
            alias_record = read_alias_record(input)
        
        output = StringIO()
        write_alias_record(output, **alias_record)
        
        actual_output = output.getvalue()
        with open(alias_resource_file_filepath, 'rb') as file:
            expected_output = file.read()
        
        matches = (actual_output == expected_output)
        print 'Matches? ' + ('yes' if matches else 'no')
        if not matches:
            print '    Expected: ' + repr(expected_output)
            print '    Actual:   ' + repr(actual_output)
            print
            print_alias_record(alias_record)
        
    else:
        sys.exit('Unrecognized command: %s' % command)
        return


def print_alias_record(alias_record):
    print 'Alias Information'
    print '================='
    for member in _ALIAS_RECORD_MEMBERS:
        print '%s: %s' % (member.name, repr(alias_record[member.name]))

# ------------------------------------------------------------------------------


def read_alias_record(input):
    v = {}
    this_module = globals()
    for member in _ALIAS_RECORD_MEMBERS:
        v[member.name] = this_module['read_' + member.type](input, member.subtype)
    return v


def read_fixed_string(input, num_bytes):
    return input.read(num_bytes)


def read_unsigned(input, num_bytes):
    value = 0
    for i in xrange(num_bytes):
        value = value << 8
        value += ord(input.read(1))
    return value


def read_pascal_string(input, max_string_length):
    str_length = ord(input.read(1))
    str = input.read(str_length)
    zero = input.read(max_string_length - str_length)
    return str


def read_until_eof(input, ignored):
    return input.read()

# ------------------------------------------------------------------------------

def write_alias_record(output, **fieldargs):
    this_module = globals()
    for member in _ALIAS_RECORD_MEMBERS:
        value = fieldargs.get(member.name, member.default_value)
        if value is None:
            raise ValueError('No value specified for member "%s", which has no default value.' % member.name)
        this_module['write_' + member.type](output, member.subtype, value)


def write_fixed_string(output, num_bytes, value):
    if value == 0:
        value = '\x00' * num_bytes
    if len(value) != num_bytes:
        raise ValueError('Value does not have the expected byte count.')
    output.write(value)


def write_unsigned(output, num_bytes, value):
    shift = (num_bytes - 1) * 8
    mask = 0xFF << shift
    
    for i in xrange(num_bytes):
        output.write(chr((value & mask) >> shift))
        shift -= 8
        mask = mask >> 8


def write_pascal_string(output, max_string_length, value):
    str_length = len(value)
    output.write(chr(str_length))
    output.write(value)
    for i in xrange(max_string_length - str_length):
        output.write(chr(0))


def write_until_eof(output, ignored, value):
    output.write(value)

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
