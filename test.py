#!/usr/bin/env python

"""
Run automated unit tests.
"""

# Commands through which tests are run
import alias_file
import alias_record
import macbinary_file
import resource_fork

# For _test_create_alias_file()
from classicbox.disk.hfs import hfs_copy_in_from_stream
from classicbox.disk.hfs import hfs_exists
from classicbox.disk.hfs import hfs_format_new
from classicbox.disk.hfs import hfs_mkdir
from classicbox.disk.hfs import hfs_mount
from classicbox.macbinary import write_macbinary_to_buffer
import os
import os.path

from contextlib import contextmanager
from StringIO import StringIO
import sys
import traceback


def main(args):
    # Test each module
    # 
    # Modules should be tested in order of dependencies first.
    # So if module A depends on B, B should be tested before A.
    # This ensures that the first test failure corresponds most
    # closely with what actually needs to be fixed.
    
    # classicbox.alias.file (and dependencies)
    test_classicbox_io()
    test_classicbox_alias_record()
    test_classicbox_resource_fork()
    test_classicbox_macbinary()
    test_classicbox_alias_file()


def test_classicbox_io():
    # No specific tests for this module.
    # Currently io is tested indirectly by all of its (numerous) dependants.
    pass


def test_classicbox_alias_record():
    # 'AppAlias.rsrc.dat' is an alias record with the properties:
    #   * The alias's target is not at the root level of the volume.
    #     Therefore it has a parent directory.
    #   * The alias matches the output expected by the
    #     'test_write_custom_matching' test.
    alias_record_filepath = 'test_data/AppAlias.rsrc.dat'
    
    test_throws_no_exceptions(
        'test_alias_record_read_print', lambda: \
        alias_record.main(
            ['info', alias_record_filepath]))
    test_ends_output_with_ok(
        'test_alias_record_read_write', lambda: \
        alias_record.main(
            ['test_read_write', alias_record_filepath]))
    test_ends_output_with_ok(
        'test_alias_record_read_write_no_extras', lambda: \
        alias_record.main(
            ['test_read_write_no_extras', alias_record_filepath]))
    test_throws_no_exceptions(
        'test_alias_record_write_custom', lambda: \
        alias_record.main(
            ['test_write_custom_matching', '-']))
    test_throws_no_exceptions(
        'test_alias_record_write_custom_matching', lambda: \
        alias_record.main(
            ['test_write_custom_matching', alias_record_filepath]))


def test_classicbox_resource_fork():
    # (1) 'AppAlias.rsrcfork.dat' is a simple resource fork with:
    #   * A single resource of type 'alis'.
    # 
    # (2) 'MultipleResource.rsrcfork.dat' is a more complex resource fork with:
    #   * Multiple resources, all of type 'alis'
    #   * Resources with names that vary in even and odd length.
    #     (This matters when tested whether padding bytes are inserted.)
    #   * Resource are arranged in the resource data area in a different
    #     order than their IDs.
    SAMPLES = [
        ('simple', 'test_data/AppAlias.rsrcfork.dat'),
        ('complex', 'test_data/MultipleResource.rsrcfork.dat'),
    ]
    
    for (sample_name, resource_fork_filepath) in SAMPLES:
        test_throws_no_exceptions(
            'test_resource_fork_read_print_' + sample_name, lambda: \
            resource_fork.main(
                ['info', resource_fork_filepath]))
        test_ends_output_with_ok(
            'test_resource_fork_read_write_approx_' + sample_name, lambda: \
            resource_fork.main(
                ['test_read_write_approx', resource_fork_filepath]))
        test_ends_output_with_ok(
            'test_resource_fork_read_write_exact_' + sample_name, lambda: \
            resource_fork.main(
                ['test_read_write_exact', resource_fork_filepath]))
    
    test_throws_no_exceptions(
        'test_resource_fork_write_custom', lambda: \
        resource_fork.main(
            ['test_write_custom', '-']))


def test_classicbox_macbinary():
    macbinary_filepath = 'test_data/AppAlias.bin'
    
    test_throws_no_exceptions(
        'test_macbinary_read_print', lambda: \
        macbinary_file.main(
            ['info', macbinary_filepath]))
    test_ends_output_with_ok(
        'test_macbinary_read_write', lambda: \
        macbinary_file.main(
            ['test_read_write', macbinary_filepath]))
    test_throws_no_exceptions(
        'test_macbinary_write_custom', lambda: \
        macbinary_file.main(
            ['test_write_custom', '-']))


def test_classicbox_alias_file():
    test_throws_no_exceptions(
        'test_alias_file_create_on_disk_image', lambda: \
        _test_create_alias_file())


def _test_create_alias_file():
    if not os.path.exists('test_data/generated'):
        os.mkdir('test_data/generated')
    
    source_disk_image_filepath = 'test_data/generated/SourceDisk.dsk'
    target_disk_image_filepath = 'test_data/generated/TargetDisk.dsk'
    
    try:
        # Create empty source disk image
        hfs_format_new(source_disk_image_filepath, 'Source', 800 * 1024)
        
        # Create target disk image containing fake app at 'Target:App:app'
        hfs_format_new(target_disk_image_filepath, 'Target', 800 * 1024)
        hfs_mkdir('Target:App')
        hfs_copy_in_from_stream(write_macbinary_to_buffer({
            'filename': 'app',
            'file_type': 'APPL',
            'file_creator': 'TEST',
            'data_fork': ''
        }), 'Target:App:app')
        
        # Ensure an alias can be created without any exceptions
        alias_file.main(['create', 
            source_disk_image_filepath, 'Source:app alias',
            target_disk_image_filepath, 'Target:App:app'])
        
        # Ensure the target alias actually exists
        hfs_mount(source_disk_image_filepath)
        if not hfs_exists('Source:app alias'):
            raise AssertionError('Alias not created in the expected location.')
    finally:
        if os.path.exists(target_disk_image_filepath):
            os.remove(target_disk_image_filepath)
        if os.path.exists(source_disk_image_filepath):
            os.remove(source_disk_image_filepath)


# ------------------------------------------------------------------------------
# Test Infrastructure

def test_throws_no_exceptions(test_name, block):
    if _try_run_test_block(test_name, block) is not None:
        _print_test_success(test_name)


def test_ends_output_with_ok(test_name, block):
    test_stdout = _try_run_test_block(test_name, block)
    if test_stdout is not None:
        if test_stdout.endswith('OK\n'):
            _print_test_success(test_name)
        else:
            _print_test_error(test_name, test_stdout)


def _try_run_test_block(test_name, block):
    """
    Tries to run the specified block.
    
    If successful, returns the stdout from running the block.
    If failure, prints the failure and returns None.
    """
    test_stdout_buffer = StringIO()
    try:
        with _replace_stdout(test_stdout_buffer):
            block()
        return test_stdout_buffer.getvalue()
    except:
        (type, value, tb) = sys.exc_info()
        _print_test_error(test_name, test_stdout_buffer.getvalue(), tb)
        return None


@contextmanager
def _replace_stdout(new_stdout):
    original_stdout = sys.stdout
    sys.stdout = new_stdout
    try:
        yield
    finally:
        sys.stdout = original_stdout


def _print_test_error(test_name, test_stdout, tb=None):
    print bold_red('ERR %s') % test_name
    print
    if tb is not None:
        traceback.print_exc()
        print
    # TODO: Also consider printing `test_stdout`


def _print_test_success(test_name):
    print bold_green('OK  %s') % test_name

# ------------------------------------------------------------------------------
# Terminal Colors

# ANSI color codes
# Obtained from: http://www.bri1.com/files/06-2008/pretty.py
TERM_FG_BLUE =          '\033[0;34m'
TERM_FG_BOLD_BLUE =     '\033[1;34m'
TERM_FG_RED =           '\033[0;31m'
TERM_FG_BOLD_RED =      '\033[1;31m'
TERM_FG_GREEN =         '\033[0;32m'
TERM_FG_BOLD_GREEN =    '\033[1;32m'
TERM_FG_CYAN =          '\033[0;36m'
TERM_FG_BOLD_CYAN =     '\033[1;36m'
TERM_FG_YELLOW =        '\033[0;33m'
TERM_FG_BOLD_YELLOW =   '\033[1;33m'
TERM_RESET =            '\033[0m'


def bold_red(str_value):
    return TERM_FG_BOLD_RED + str_value + TERM_RESET


def bold_green(str_value):
    return TERM_FG_BOLD_GREEN + str_value + TERM_RESET

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])
