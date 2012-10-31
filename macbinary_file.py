#!/usr/bin/env python

"""
Manipulates MacBinary files.
"""

from __future__ import absolute_import

from classicbox.io import BytesIO
from classicbox.io import print_structure_format
from classicbox.macbinary import _MACBINARY_HEADER_MEMBERS
from classicbox.macbinary import print_macbinary
from classicbox.macbinary import read_macbinary
from classicbox.macbinary import write_macbinary
import sys

# ------------------------------------------------------------------------------

_VERBOSE_HEADER_FORMAT = False

def main(args):
    (command, macbinary_filepath, ) = args
    
    if _VERBOSE_HEADER_FORMAT:
        print_structure_format(_MACBINARY_HEADER_MEMBERS, 'MacBinary Header Format')
    
    if macbinary_filepath == '-':
        macbinary = None
    else:
        with open(macbinary_filepath, 'rb') as input:
            macbinary = read_macbinary(input)
    
    if command == 'info':
        print_macbinary(macbinary)
    
    elif command == 'test_read_write':
        output_macbinary = BytesIO()
        write_macbinary(output_macbinary, macbinary)
        
        with open(macbinary_filepath, 'rb') as file:
            expected_output = file.read()
        actual_output = output_macbinary.getvalue()
        
        matches = (actual_output == expected_output)
        if matches:
            print 'OK'
        else:
            print '    Expected: ' + repr(expected_output)
            print '    Actual:   ' + repr(actual_output)
            print
    
    elif command == 'test_write_custom':
        output_macbinary = BytesIO()
        write_macbinary(output_macbinary, {
            'filename': 'Greetings.txt',
            'file_type': 'TEXT',
            'file_creator': 'ttxt',
            'data_fork': 'Hello World!',
        })
    
    else:
        sys.exit('Unrecognized command: %s' % command)
        return

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
