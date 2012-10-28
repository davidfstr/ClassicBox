#!/usr/bin/env python

"""
Reads resource forks.
"""

from classicbox.resource_fork import read_resource_fork
from classicbox.resource_fork import write_resource_fork
from StringIO import StringIO
import sys

# ------------------------------------------------------------------------------

def main(args):
    (command, resource_file_filepath, ) = args
    
    if command == 'info':
        with open(resource_file_filepath, 'rb') as input:
            # Read and print the contents of the resource map
            print_resource_fork(input)
    
    elif command == 'test_read_write':
        with open(resource_file_filepath, 'rb') as input:
            original_resource_map = read_resource_fork(
                input,
                read_everything=True)
        
        output_fork = StringIO()
        write_resource_fork(output_fork, original_resource_map, _preserve_order=True)
        
        with open(resource_file_filepath, 'rb') as file:
            expected_output = file.read()
        actual_output = output_fork.getvalue()
        
        matches = (actual_output == expected_output)
        print 'Matches? ' + ('yes' if matches else 'no')
        if not matches:
            print '    Expected: ' + repr(expected_output)
            print '    Actual:   ' + repr(actual_output)
            print
            print ('#' * 32) + ' EXPECTED ' + ('#' * 32)
            print_resource_fork(StringIO(expected_output))
            
            print ('#' * 32) + ' ACTUAL ' + ('#' * 32)
            print_resource_fork(StringIO(actual_output))
            
    
    elif command == 'test_read_write_approx':
        with open(resource_file_filepath, 'rb') as input:
            test_read_write(input)
    
    else:
        sys.exit('Unrecognized command: %s' % command)
        return


def print_resource_fork(input_resource_fork_stream):
    # NOTE: Depends on undocumented argument
    resource_map = read_resource_fork(
        input_resource_fork_stream,
        read_all_resource_names=True,
        _verbose=True)


def test_read_write(input_resource_fork_stream):
    original_resource_map = read_resource_fork(
        input_resource_fork_stream,
        read_everything=True)
    
    # Must write to an intermediate "normalized" fork because
    # `write_resource_fork(read_resource_fork(...))` does not
    # preserve reserved fields of the resource fork, which are
    # actually set to non-zero values in real resource forks.
    # TODO: This limitation is dumb.
    normalized_fork = StringIO()
    write_resource_fork(normalized_fork, original_resource_map)
    
    normalized_fork.seek(0)
    normalized_resource_map = read_resource_fork(
        normalized_fork,
        read_everything=True)
    
    output_fork = StringIO()
    write_resource_fork(output_fork, normalized_resource_map)
    
    expected_output = normalized_fork.getvalue()
    actual_output = output_fork.getvalue()
    
    matches = (actual_output == expected_output)
    print 'Matches? ' + ('yes' if matches else 'no')
    if not matches:
        print '    Expected: ' + repr(expected_output)
        print '    Actual:   ' + repr(actual_output)
        print

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
