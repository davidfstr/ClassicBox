#!/usr/bin/env python

"""
Manipulates MacOS alias records.
"""

from collections import namedtuple
from StringIO import StringIO
import sys


_StructMember = namedtuple(
    '_StructMember',
    ('name', 'type', 'subtype', 'default_value'))

# Alias file format reference: http://xhelmboyx.tripod.com/formats/alias-layout.txt
_ALIAS_RECORD_MEMBERS = [
    _StructMember('user_type_name', 'fixed_string', 4, 0),      # 0 = none
    _StructMember('record_size', 'unsigned', 2, None),
    _StructMember('record_version', 'unsigned', 2, 2),          # 2 = current version
    _StructMember('alias_kind', 'unsigned', 2, None),           # 0 = file, 1 = directory
    _StructMember('volume_name', 'pascal_string', 27, None),
    _StructMember('volume_created', 'unsigned', 4, 0),          # may be 0; seconds since 1904
    _StructMember('volume_signature', 'fixed_string', 2, 'BD'), # 'RW' = MFS, 'BD' = HFS (or foreign), 'H+' = HFS+
    _StructMember('drive_type', 'unsigned', 2, 0),
        # 0 = Fixed HD, 1 = Network Disk,
        # 2 = 400kB FD, 3 = 800kB FD,
        # 4 = 1.4MB FD, 5 = Other Ejectable Media
    _StructMember('parent_directory_id', 'unsigned', 4, 0),     # may be 0
    _StructMember('file_name', 'pascal_string', 63, None),
    _StructMember('file_number', 'unsigned', 4, 0),             # may be 0
    _StructMember('file_created', 'unsigned', 4, 0),            # may be 0; seconds since 1904
    _StructMember('file_type', 'fixed_string', 4, 0),           # may be 0
    _StructMember('file_creator', 'fixed_string', 4, 0),        # may be 0
    _StructMember('nlvl_from', 'unsigned', 2, None),
    _StructMember('nlvl_to', 'unsigned', 2, None),
        # -1 = alias on different volume,
        # 1 = alias and target in same directory
    _StructMember('volume_attributes', 'unsigned', 4, 0),       # may be 0
    _StructMember('volume_filesystem_id', 'fixed_string', 2, 0),# 0 for MFS or HFS
    _StructMember('reserved', 'fixed_string', 10, 0),
    _StructMember('extras', 'extras', None, []),
    _StructMember('trailing', 'until_eof', None, ''),
]

_ExtraType = namedtuple(
    '_ExtraType',
    ('code', 'name'))

_EXTRA_TYPES = [
    _ExtraType(0, 'parent_directory_name'),
    _ExtraType(1, 'directory_ids'),
    _ExtraType(2, 'absolute_path'),
    # 3 = AppleShare Zone Name
    # 4 = AppleShare Server Name
    # 5 = AppleShare User Name
    # 6 = Driver Name
    # 9 = Revised AppleShare info
    # 10 = AppleRemoteAccess dialup info
    _ExtraType(0xFFFF, 'end'),
]

Extra = namedtuple(
    'Extra',
    ('type', 'name', 'value'))

# ------------------------------------------------------------------------------

def main(args):
    # Path to a file that contains an alias record.
    # 
    # This is equivalent to the contents of an 'alis' resource,
    # which is the primary resource contained in an alias file
    (command, alias_record_file_filepath) = args
    
    with open(alias_record_file_filepath, 'rb') as input:
        alias_record = read_alias_record(input)
    
    if command == 'info':
        print_alias_record(alias_record)
        
    elif command == 'test_read_write':
        output = StringIO()
        write_alias_record(output, **alias_record)
        
        verify_matches(output, alias_record_file_filepath, alias_record)
        
    elif command == 'test_write_custom_matching':
        test_write_custom_matching(alias_record_file_filepath, alias_record)
        
    else:
        sys.exit('Unrecognized command: %s' % command)
        return


def test_write_custom_matching(alias_record_file_filepath, alias_record):
    # "AppAlias.rsrc.dat"
    output = StringIO()
    write_alias_record(output,
        record_size=202,
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
    
    """
    # "AutQuit7 Alias Data.rsrc.dat"
    output = StringIO()
    write_alias_record(output,
        record_size=200,
        alias_kind=0,
        volume_name='Boot',
        volume_created=3431272487,
        parent_directory_id=484,
        file_name='AutQuit7',
        file_number=485,
        # NOTE: Can't get file_created reliably from hfsutil CLI
        file_created=3265652246,
        file_type='APPL',
        file_creator='AQt7',
        nlvl_from=1,
        nlvl_to=1,
        extras=[
            Extra(0, 'parent_directory_name', 'AutQuit7'),
            Extra(1, 'directory_ids', [484]),
            Extra(2, 'absolute_path', 'Boot:AutQuit7:AutQuit7'),
            Extra(0xFFFF, 'end', None)
        ])
    """
    
    verify_matches(output, alias_record_file_filepath, alias_record)


def print_alias_record(alias_record):
    print 'Alias Information'
    print '================='
    for member in _ALIAS_RECORD_MEMBERS:
        value = alias_record[member.name]
        
        if member.name == 'extras':
            print 'extras:'
            for extra in value:
                print '    ' + repr(extra)
        else:
            print '%s: %s' % (member.name, repr(value))


def verify_matches(output, alias_record_file_filepath, alias_record):
    actual_output = output.getvalue()
    with open(alias_record_file_filepath, 'rb') as file:
        expected_output = file.read()
    
    matches = (actual_output == expected_output)
    print 'Matches? ' + ('yes' if matches else 'no')
    if not matches:
        print '    Expected: ' + repr(expected_output)
        print '    Actual:   ' + repr(actual_output)
        print
        print_alias_record(alias_record)

# ------------------------------------------------------------------------------


def read_alias_record(input):
    return read_structure(input, _ALIAS_RECORD_MEMBERS)


def read_structure(input, structure_members):
    v = {}
    this_module = globals()
    for member in structure_members:
        v[member.name] = this_module['read_' + member.type](input, member.subtype)
    return v


def read_fixed_string(input, num_bytes):
    return input.read(num_bytes)


def read_unsigned(input, num_bytes):
    value = 0
    for i in xrange(num_bytes):
        value = value << 8
        
        c = input.read(1)
        if c == '' and i == 0:
            # Special case that read_extras cares about
            raise EOFError
        value = value | ord(c)
    return value


def read_pascal_string(input, max_string_length):
    str_length = ord(input.read(1))
    str = input.read(str_length)
    if max_string_length is not None:
        zero = input.read(max_string_length - str_length)
    return str


def read_extras(input, ignored):
    extras = []
    this_module = globals()
    while True:
        try:
            extra_type = read_unsigned(input, 2)
        except EOFError:
            if extras == []:
                # EOF'ed immediately. No extras.
                return extras
            else:
                raise
        extra_length = read_unsigned(input, 2)
        extra_content = read_fixed_string(input, extra_length)
        if extra_length & 0x1 == 1:
            input.read(1)   # padding byte
        
        for type in _EXTRA_TYPES:
            if extra_type == type.code:
                extra_name = type.name
                extra_value = this_module['read_' + type.name + '_extra_content'](extra_content)
                break
        else:
            extra_name = 'unknown'
            extra_value = read_unknown_extra_content(extra_content)
        
        extras.append(Extra(extra_type, extra_name, extra_value))
        if extra_name == 'end':
            break
    
    return extras


def read_parent_directory_name_extra_content(extra_content):
    return extra_content


def read_directory_ids_extra_content(extra_content):
    extra_value = []
    extra_content_input = StringIO(extra_content)
    for i in xrange(len(extra_content) // 4):
        extra_value.append(read_unsigned(extra_content_input, 4))
    return extra_value


def read_absolute_path_extra_content(extra_content):
    return extra_content


def read_end_extra_content(extra_content):
    return None


def read_unknown_extra_content(extra_content):
    return extra_content


def read_until_eof(input, ignored):
    return input.read()

# ------------------------------------------------------------------------------

# TODO: Don't use kwargs. Just a plain dictionary will do.
def write_alias_record(output, **fieldargs):
    if 'record_size' in fieldargs:
        write_structure(output, _ALIAS_RECORD_MEMBERS, **fieldargs)
    else:
        # Write record, except for the 'record_size' field
        start_offset = output.tell()
        write_structure(output, _ALIAS_RECORD_MEMBERS, record_size=0, **fieldargs)
        end_offset = output.tell()
        
        # Write the 'record_size' field
        output.seek(start_offset + 4)
        record_size = end_offset - start_offset
        write_unsigned(output, 2, record_size)
        output.seek(end_offset)


# TODO: Don't use kwargs. Just a plain dictionary will do.
def write_structure(output, structure_members, **fieldargs):
    this_module = globals()
    for member in structure_members:
        value = fieldargs.get(member.name, member.default_value)
        if value is None:
            raise ValueError('No value specified for member "%s", which lacks a default value.' % member.name)
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
    if max_string_length is not None:
        for i in xrange(max_string_length - str_length):
            output.write(chr(0))


def write_extras(output, ignored, value):
    extras = value
    
    this_module = globals()
    for extra in extras:
        extra_content_output = StringIO()
        this_module['write_' + extra.name + '_extra_content'](extra_content_output, extra.value)
        extra_content = extra_content_output.getvalue()
        extra_length = len(extra_content)
        
        write_unsigned(output, 2, extra.type)
        write_unsigned(output, 2, extra_length)
        output.write(extra_content)
        if extra_length & 0x1 == 1:
            output.write(chr(0))    # padding byte


def write_parent_directory_name_extra_content(output, extra_value):
    output.write(extra_value)


def write_directory_ids_extra_content(output, extra_value):
    for path_id in extra_value:
        write_unsigned(output, 4, path_id)


def write_absolute_path_extra_content(output, extra_value):
    output.write(extra_value)


def write_end_extra_content(output, extra_value):
    pass


def write_unknown_extra_content(output, extra_value):
    output.write(extra_value)


def write_until_eof(output, ignored, value):
    output.write(value)

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
