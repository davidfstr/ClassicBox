#!/usr/bin/env python

"""
Manipulates MacOS alias records.
"""

from classicbox.alias.record import Extra
from classicbox.alias.record import print_alias_record
from classicbox.alias.record import read_alias_record
from classicbox.alias.record import write_alias_record
from StringIO import StringIO
import sys


def main(args):
    # Path to a file that contains an alias record.
    # 
    # This is equivalent to the contents of an 'alis' resource,
    # which is the primary resource contained in an alias file
    (command, alias_record_file_filepath) = args
    
    if alias_record_file_filepath == '-':
        alias_record = None
    else:
        with open(alias_record_file_filepath, 'rb') as input:
            alias_record = read_alias_record(input)
    
    if command == 'info':
        print_alias_record(alias_record)
        
    elif command == 'test_read_write':
        output = StringIO()
        write_alias_record(output, alias_record)
        
        verify_matches(output, alias_record_file_filepath, alias_record)
    
    elif command == 'test_read_write_no_extras':
        alias_record['extras'] = []
        
        output = StringIO()
        write_alias_record(output, alias_record)
        
        output.seek(0)
        alias_record_no_extras = read_alias_record(output)
        
        if alias_record_no_extras['extras'] == []:
            print 'OK'
        else:
            print 'Expected empty extras.'
        
    elif command == 'test_write_custom_matching':
        test_write_custom_matching(alias_record_file_filepath, alias_record)
        
    else:
        sys.exit('Unrecognized command: %s' % command)
        return


def test_write_custom_matching(alias_record_file_filepath, alias_record):
    # "AppAlias.rsrc.dat"
    output = StringIO()
    write_alias_record(output, {
        'alias_kind': 0,
        'volume_name': 'Boot',
        'volume_created': 3431272487,
        'parent_directory_id': 542,
        'file_name': 'app',
        'file_number': 543,
        # NOTE: Can't get file_created reliably from hfsutil CLI
        'file_created': 3265652246,
        'file_type': 'APPL',
        'file_creator': 'AQt7',
        'nlvl_from': 1,
        'nlvl_to': 1,
        'extras': [
            Extra(0, 'parent_directory_name', 'B'),
            Extra(1, 'directory_ids', [542, 541, 484]),
            Extra(2, 'absolute_path', 'Boot:AutQuit7:A:B:app'),
            Extra(0xFFFF, 'end', None)
        ]
    })
    
    if alias_record_file_filepath != '-':
        verify_matches(output, alias_record_file_filepath, alias_record)


def verify_matches(output, alias_record_file_filepath, alias_record):
    actual_output = output.getvalue()
    with open(alias_record_file_filepath, 'rb') as file:
        expected_output = file.read()
    
    matches = (actual_output == expected_output)
    if matches:
        print 'OK'
    else:
        print '    Expected: ' + repr(expected_output)
        print '    Actual:   ' + repr(actual_output)
        print
        print_alias_record(alias_record)

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
