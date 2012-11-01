"""
Reads and writes binary data from structures and streams.
"""

from __future__ import absolute_import

from collections import namedtuple
from contextlib import contextmanager


StructMember = namedtuple(
    'StructMember',
    ('name', 'type', 'subtype', 'default_value'))

# ------------------------------------------------------------------------------
# Read

def read_structure(input, structure_members, external_readers=None):
    v = {}
    this_module = globals()
    for member in structure_members:
        member_reader_name = 'read_' + member.type
        member_reader = (
            this_module.get(member_reader_name, None) or
            external_readers[member_reader_name])
        
        v[member.name] = member_reader(input, member.subtype)
    
    return v


def read_fixed_string(input, num_bytes):
    return read_fixed_bytes(input, num_bytes).decode('macroman')


def read_fixed_bytes(input, num_bytes):
    return input.read(num_bytes)


def read_unsigned(input, num_bytes):
    value = 0
    for i in xrange(num_bytes):
        value = value << 8
        value = value | ord(input.read(1))
    return value


def read_signed(input, num_bytes):
    overflow_value = (1 << (8*num_bytes - 1))
    
    value = read_unsigned(input, num_bytes)
    signed_value = value if value < overflow_value else value - overflow_value*2
    return signed_value


def read_pascal_string(input, max_string_length):
    return read_pascal_bytes(input, max_string_length).decode('macroman')


def read_pascal_bytes(input, max_string_length):
    str_length = ord(input.read(1))
    str = input.read(str_length)
    if max_string_length is not None:
        zero = input.read(max_string_length - str_length)
    return str


def read_until_eof(input, ignored):
    return input.read()

# ------------------------------------------------------------------------------
# Write

def write_structure(output, structure_members, structure, external_writers=None):
    this_module = globals()
    for member in structure_members:
        member_writer_name = 'write_' + member.type
        member_writer = (
            this_module.get(member_writer_name, None) or
            external_writers[member_writer_name])
        
        value = structure.get(member.name, member.default_value)
        if value is None:
            raise ValueError('No value specified for member "%s", which lacks a default value.' % member.name)
        
        member_writer(output, member.subtype, value)


def write_fixed_string(output, num_bytes, value):
    write_fixed_bytes(output, num_bytes,
        0 if value == 0 else value.encode('macroman'))


def write_fixed_bytes(output, num_bytes, value):
    if value == 0:
        value = b'\x00' * num_bytes
    if len(value) != num_bytes:
        raise ValueError('Value does not have the expected byte count.')
    output.write(value)


def write_unsigned(output, num_bytes, value):
    shift = (num_bytes - 1) * 8
    mask = 0xFF << shift
    
    for i in xrange(num_bytes):
        output.write(bchr((value & mask) >> shift))
        shift -= 8
        mask = mask >> 8


def write_signed(output, num_bytes, value):
    overflow_value = (1 << (8*num_bytes - 1))
    
    unsigned_value = value if value >= 0 else value + overflow_value*2
    write_unsigned(output, num_bytes, unsigned_value)


def write_pascal_string(output, max_string_length, value):
    write_pascal_bytes(output, max_string_length, value.encode('macroman'))


def write_pascal_bytes(output, max_string_length, value):
    if max_string_length is not None:
        if len(value) > max_string_length:
            raise ValueError('Value exceeds the maximum byte count.')
    str_length = len(value)
    output.write(bchr(str_length))
    output.write(value)
    if max_string_length is not None:
        write_nulls(output, max_string_length - str_length)


def write_until_eof(output, ignored, value):
    output.write(value)

# ------------------------------------------------------------------------------
# Misc

def print_structure(structure, members, name):
    print name
    print '=' * len(name)
    for member in members:
        value = structure[member.name]
        print '%s: %s' % (member.name, repr(value))
    print


def print_structure_format(members, name):
    print name
    print '=' * len(name)
    offset = 0
    for member in members:
        print '%s: %s' % (offset, member.name)
        offset += sizeof_structure_member(member)
    print


def sizeof_structure(members):
    total_size = 0
    for member in members:
        total_size += sizeof_structure_member(member)
    return total_size


def sizeof_structure_member(member):
    if member.type in ('unsigned', 'signed', 'fixed_string', 'fixed_bytes'):
        return member.subtype
    elif member.type in ('pascal_string', 'pascal_bytes'):
        max_string_length = member.subtype
        if max_string_length is None:
            raise ValueError("Can't determine size of a dynamic pascal string.")
        return max_string_length + 1
    else:
        raise ValueError("Don't know how to find the size of member with type: %s" % member.type)


def offset_to_structure_member(members, member_name):
    offset = 0
    for member in members:
        if member.name == member_name:
            return offset
        offset += sizeof_structure_member(member)
    raise ValueError('No such member in structure.')


def fill_missing_structure_members_with_defaults(structure_members, structure):
    for member in structure_members:
        if member.name not in structure:
            structure[member.name] = member.default_value


def at_eof(input):
    """
    Returns whether the specified input stream is at EOF.
    """
    with save_stream_position(input):
        at_eof = input.read(1) == b''
    return at_eof


@contextmanager
def save_stream_position(stream):
    original_position = stream.tell()
    yield
    stream.seek(original_position)


def write_nulls(output, num_bytes):
    """
    Writes the specified number of NULL bytes to the specified output stream.
    
    This implementation is optimized to write a large number of bytes quickly.
    """
    zero_byte = NULL_BYTE   # save to local to improve performance
    
    # Write blocks of 1024 bytes first
    zero_kilobyte = zero_byte * 1024
    while num_bytes >= 1024:
        output.write(zero_kilobyte)
        num_bytes -= 1024
    
    # Write remaining bytes
    for i in xrange(num_bytes):
        output.write(zero_byte)

# ------------------------------------------------------------------------------
# Unicode & Python 3 Shims

# Declare BytesIO class, which will be important when migrating to Python 3
try:
    from io import BytesIO              # Python 3
except ImportError:
    from StringIO import StringIO as BytesIO

# Declare StringIO class, which will be important when migrating to Python 3
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO             # Python 3

if bytes == str:
    def bchr(byte_ordinal):
        return chr(byte_ordinal)
else:
    def bchr(byte_ordinal):
        return bytes([byte_ordinal])    # Python 3

NULL_BYTE = bchr(0)

if bytes == str:
    def iterord(bytes_value):
        for b in bytes_value:
            yield ord(b)
else:
    # Python 3
    def iterord(bytes_value):
        return bytes_value
