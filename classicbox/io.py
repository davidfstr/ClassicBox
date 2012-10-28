"""
Reads and writes binary data from structures and streams.
"""

from collections import namedtuple


StructMember = namedtuple(
    'StructMember',
    ('name', 'type', 'subtype', 'default_value'))

# ------------------------------------------------------------------------------

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
    str_length = ord(input.read(1))
    str = input.read(str_length)
    if max_string_length is not None:
        zero = input.read(max_string_length - str_length)
    return str


def read_until_eof(input, ignored):
    return input.read()

# ------------------------------------------------------------------------------

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


def write_signed(output, num_bytes, value):
    overflow_value = (1 << (8*num_bytes - 1))
    
    unsigned_value = value if value >= 0 else value + overflow_value*2
    write_unsigned(output, num_bytes, unsigned_value)


def write_pascal_string(output, max_string_length, value):
    str_length = len(value)
    output.write(chr(str_length))
    output.write(value)
    if max_string_length is not None:
        for i in xrange(max_string_length - str_length):
            output.write(chr(0))


def write_until_eof(output, ignored, value):
    output.write(value)

# ------------------------------------------------------------------------------

def print_structure(structure, members, name):
    print name
    print '=' * len(name)
    for member in members:
        value = structure[member.name]
        print '%s: %s' % (member.name, repr(value))
    print


def sizeof_structure(members):
    total_size = 0
    for member in members:
        total_size += sizeof_member(member)
    return total_size


def sizeof_member(member):
    if member.type in ('unsigned', 'signed', 'fixed_string'):
        return member.subtype
    else:
        raise ValueError('Don\'t know how to find the size of member with type: %s' % member.type)


def fill_missing_structure_members_with_defaults(structure_members, structure):
    for member in structure_members:
        if member.name not in structure:
            structure[member.name] = member.default_value


def at_eof(input):
    """
    Returns whether the specified input stream is at EOF.
    """
    original_offset = input.tell()
    at_eof = input.read(1) == ''
    input.seek(original_offset)
    return at_eof
