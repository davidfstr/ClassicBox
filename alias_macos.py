#!/usr/bin/env python

"""
Manipulates MacOS alias files.
"""

import sys

# ------------------------------------------------------------------------------

def main(args):
    # Path to a file that (in its data fork) contains the contents of an 'alis'
    # resource, which is the primary resource contained in an alias file
    (alias_resource_file_filepath, ) = args
    
    print_information_for_alias_resource_file(alias_resource_file_filepath)

# ------------------------------------------------------------------------------

input = None

def print_information_for_alias_resource_file(alias_resource_file_filepath):
    global input
    input = open(alias_resource_file_filepath, 'rb')
    
    # 
    # Alias file format reference: http://xhelmboyx.tripod.com/formats/alias-layout.txt
    # 
    user_type_name_or_app_creator_code = read_fixed_string(4)   # 0 = none
    record_size = read_unsigned(2)
    record_version = read_unsigned(2)           # 2 = current version
    alias_kind = read_unsigned(2)               # 0 = file, 1 = directory
    volume_name = read_pascal_string(27)
    volume_created = read_unsigned(4)           # may be 0; seconds since 1904
    volume_signature = read_fixed_string(2)     # 'RW' = MFS, 'BD' = HFS (or foreign), 'H+' = HFS+
    drive_type = read_unsigned(2)   # 0 = Fixed HD, 1 = Network Disk,
                                    # 2 = 400kB FD, 3 = 800kB FD,
                                    # 4 = 1.4MB FD, 5 = Other Ejectable Media
    parent_directory_id = read_unsigned(4)      # may be 0
    file_name = read_pascal_string(63)
    file_number = read_unsigned(4)              # may be 0
    file_created = read_unsigned(4)             # may be 0; seconds since 1904
    file_type = read_fixed_string(4)            # may be 0
    file_creator = read_fixed_string(4)         # may be 0
    nlvl_from = read_unsigned(2)
    nlvl_to = read_unsigned(2)                  # -1 = alias on different volume,
                                                # 1 = alias and target in same directory
    volume_attributes = read_unsigned(4)        # may be 0
    volume_filesystem_id = read_fixed_string(2) # 0 for MFS or HFS
    reserved = read_fixed_string(10)
    extra = input.read()
    
    input.close()
    
    print 'Alias Information'
    print '================='
    print 'record_size: %s' % record_size
    print 'record_version: %s' % record_version
    print 'alias_kind: %s' % alias_kind
    print 'volume_name: %s' % volume_name
    print 'volume_created: %s' % volume_created
    print 'volume_signature: %s' % volume_signature
    print 'drive_type: %s' % drive_type
    print 'parent_directory_id: %s' % parent_directory_id
    print 'file_name: %s' % file_name
    print 'file_number: %s' % file_number
    print 'file_created: %s' % file_created
    print 'file_type: %s' % file_type
    print 'file_creator: %s' % file_creator
    print 'nlvl_from: %s' % nlvl_from
    print 'nlvl_to: %s' % nlvl_to
    print 'volume_attributes: %s' % volume_attributes
    print 'volume_filesystem_id: %s' % repr(volume_filesystem_id)
    print 'reserved: %s' % repr(reserved)
    print 'extra: %s' % repr(file_creator)


def read_fixed_string(num_bytes):
    return input.read(num_bytes)


def read_unsigned(num_bytes):
    value = 0
    for i in xrange(num_bytes):
        value = value << 8
        value += ord(input.read(1))
    return value


def read_pascal_string(max_string_length):
    str_length = ord(input.read(1))
    str = input.read(str_length)
    zero = input.read(max_string_length - str_length)
    return str

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
