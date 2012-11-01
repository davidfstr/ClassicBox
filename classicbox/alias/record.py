"""
Manipulates MacOS alias records.
"""

from classicbox.io import at_eof
from classicbox.io import BytesIO
from classicbox.io import NULL_BYTE
from classicbox.io import read_fixed_bytes
from classicbox.io import read_structure
from classicbox.io import read_unsigned
from classicbox.io import StructMember
from classicbox.io import write_structure
from classicbox.io import write_unsigned

from collections import namedtuple


# Alias file format reference: http://xhelmboyx.tripod.com/formats/alias-layout.txt
_ALIAS_RECORD_MEMBERS = [
    StructMember('user_type_name', 'fixed_string', 4, 0),      # 0 = none
    StructMember('record_size', 'unsigned', 2, None),
    StructMember('record_version', 'unsigned', 2, 2),          # 2 = current version
    StructMember('alias_kind', 'unsigned', 2, None),           # 0 = file, 1 = directory
    StructMember('volume_name', 'pascal_string', 27, None),
    StructMember('volume_created', 'unsigned', 4, 0),          # may be 0; seconds since 1904
    StructMember('volume_signature', 'fixed_string', 2, 'BD'), # 'RW' = MFS, 'BD' = HFS (or foreign), 'H+' = HFS+
    StructMember('drive_type', 'unsigned', 2, 0),
        # 0 = Fixed HD, 1 = Network Disk,
        # 2 = 400kB FD, 3 = 800kB FD,
        # 4 = 1.4MB FD, 5 = Other Ejectable Media
    StructMember('parent_directory_id', 'unsigned', 4, 0),     # may be 0
    StructMember('file_name', 'pascal_string', 63, None),
    StructMember('file_number', 'unsigned', 4, 0),             # may be 0
    StructMember('file_created', 'unsigned', 4, 0),            # may be 0; seconds since 1904
    StructMember('file_type', 'fixed_string', 4, 0),           # may be 0
    StructMember('file_creator', 'fixed_string', 4, 0),        # may be 0
    StructMember('nlvl_from', 'unsigned', 2, None),
    StructMember('nlvl_to', 'unsigned', 2, None),
        # -1 = alias on different volume,
        # 1 = alias and target in same directory
    StructMember('volume_attributes', 'unsigned', 4, 0),       # may be 0
    StructMember('volume_filesystem_id', 'fixed_string', 2, 0),# 0 for MFS or HFS
    StructMember('reserved', 'fixed_bytes', 10, 0),
    StructMember('extras', 'extras', None, []),
    StructMember('trailing', 'until_eof', None, b''),
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

def read_alias_record(input):
    return read_structure(input, _ALIAS_RECORD_MEMBERS, external_readers={
        'read_extras': _read_extras
    })


def _read_extras(input, ignored):
    if at_eof(input):
        # EOF'ed immediately. No extras.
        return []
    
    extras = []
    this_module = globals()
    while True:
        extra_type = read_unsigned(input, 2)
        extra_length = read_unsigned(input, 2)
        extra_content = read_fixed_bytes(input, extra_length)
        if extra_length & 0x1 == 1:
            input.read(1)   # padding byte
        
        for type in _EXTRA_TYPES:
            if extra_type == type.code:
                extra_name = type.name
                extra_value = this_module['_read_' + type.name + '_extra_content'](extra_content)
                break
        else:
            extra_name = 'unknown'
            extra_value = read_unknown_extra_content(extra_content)
        
        extras.append(Extra(extra_type, extra_name, extra_value))
        if extra_name == 'end':
            break
    
    return extras


def _read_parent_directory_name_extra_content(extra_content):
    return extra_content.decode('macroman')


def _read_directory_ids_extra_content(extra_content):
    extra_value = []
    extra_content_input = BytesIO(extra_content)
    for i in xrange(len(extra_content) // 4):
        extra_value.append(read_unsigned(extra_content_input, 4))
    return extra_value


def _read_absolute_path_extra_content(extra_content):
    return extra_content.decode('macroman')


def _read_end_extra_content(extra_content):
    return None


def _read_unknown_extra_content(extra_content):
    return extra_content

# ------------------------------------------------------------------------------

def write_alias_record(output, alias_record):
    if 'record_size' in alias_record:
        _write_alias_record_structure(output, alias_record)
    else:
        alias_record['record_size'] = 0
        
        # Write record, except for the 'record_size' field
        start_offset = output.tell()
        _write_alias_record_structure(output, alias_record)
        end_offset = output.tell()
        
        # Write the 'record_size' field
        output.seek(start_offset + 4)
        record_size = end_offset - start_offset
        write_unsigned(output, 2, record_size)
        output.seek(end_offset)


def _write_alias_record_structure(output, alias_record):
    write_structure(output, _ALIAS_RECORD_MEMBERS, alias_record, external_writers={
        'write_extras': _write_extras
    })


def _write_extras(output, ignored, value):
    extras = value
    
    this_module = globals()
    for extra in extras:
        extra_content_output = BytesIO()
        this_module['_write_' + extra.name + '_extra_content'](extra_content_output, extra.value)
        extra_content = extra_content_output.getvalue()
        extra_length = len(extra_content)
        
        write_unsigned(output, 2, extra.type)
        write_unsigned(output, 2, extra_length)
        output.write(extra_content)
        if extra_length & 0x1 == 1:
            output.write(NULL_BYTE)    # padding byte


def _write_parent_directory_name_extra_content(output, extra_value):
    output.write(extra_value.encode('macroman'))


def _write_directory_ids_extra_content(output, extra_value):
    for path_id in extra_value:
        write_unsigned(output, 4, path_id)


def _write_absolute_path_extra_content(output, extra_value):
    output.write(extra_value.encode('macroman'))


def _write_end_extra_content(output, extra_value):
    pass


def _write_unknown_extra_content(output, extra_value):
    output.write(extra_value)

# ------------------------------------------------------------------------------

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
