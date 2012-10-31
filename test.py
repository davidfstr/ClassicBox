#!/usr/bin/env python

"""
Run automated unit tests.
"""

# Commands through which tests are run
import alias_file
import alias_record
import catalog_create
import catalog_diff
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

# For _test_catalog_create_output()
from classicbox.time import convert_local_to_mac_timestamp
import json
from pprint import pprint
from tempfile import NamedTemporaryFile
import time

from classicbox.io import StringIO
from contextlib import contextmanager
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
    
    # catalog_create, catalog_diff
    test_catalog_create()
    test_catalog_diff()
    
    # TODO: box_create
    # TODO: box_bootstrap
    # TODO: box_up


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

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

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
            'data_fork': b''
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

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def test_catalog_create():
    test_throws_no_exceptions(
        'test_catalog_create_output', lambda: \
        _test_catalog_create_output())


def _test_catalog_create_output():
    if not os.path.exists('test_data/generated'):
        os.mkdir('test_data/generated')
    
    disk_image_filepath = 'test_data/generated/Catalog.dsk'
    
    try:
        now = time.time()
        now_string = time.strftime('%b %d %H:%M', time.localtime(now)).decode('ascii')
        now_mactimestamp = convert_local_to_mac_timestamp(now)
        
        created = 1
        modified = now_mactimestamp
        
        # Create disk image with some files on it
        hfs_format_new(disk_image_filepath, u'MyDisk', 800 * 1024)
        hfs_mkdir(u'MyDisk:CoolApp\u2122')
        hfs_copy_in_from_stream(write_macbinary_to_buffer({
            'filename': u'CoolApp\u2122',
            'file_type': u'APPL',
            'file_creator': u'TEST',
            'data_fork': b'',
            'created': created,
            'modified': modified,
        }), u'MyDisk:CoolApp\u2122:CoolApp\u2122')
        hfs_copy_in_from_stream(write_macbinary_to_buffer({
            'filename': u'Readme',
            'file_type': u'ttro',
            'file_creator': u'ttxt',
            'data_fork': b'RTFM!',
            'created': created,
            'modified': modified,
        }), u'MyDisk:CoolApp\u2122:Readme')
        hfs_copy_in_from_stream(write_macbinary_to_buffer({
            'filename': u'CoolApp Install Log',
            'file_type': u'TEXT',
            'file_creator': u'ttxt',
            'data_fork': b'I installed CoolApp!',
            'created': created,
            'modified': modified,
        }), u'MyDisk:CoolApp\u2122 Install Log')
        
        catalog_json = capture_stdout(lambda: \
            catalog_create.main([disk_image_filepath]))
        catalog = json.loads(catalog_json)
        
        expected_output = [
            [u'CoolApp\u2122', now_string, [
                [u'CoolApp\u2122', now_string],
                [u'Readme', now_string],
            ]],
            [u'CoolApp\u2122 Install Log', now_string],
        ]
        actual_output = catalog
        assert_equal(expected_output, actual_output,
            'Catalog output did not match expected output.')
    finally:
        if os.path.exists(disk_image_filepath):
            os.remove(disk_image_filepath)


def test_catalog_diff():
    test_names = [
        'test_catalog_diff_add_file',
        'test_catalog_diff_edit_file',
        'test_catalog_diff_delete_file',
        'test_catalog_diff_file_becomes_directory',
        'test_catalog_diff_directory_becomes_file',
        # TODO: Make tests that exercise the "ignore tree" functionality as well
    ]
    
    this_module = globals()
    for test_name in test_names:
        test_throws_no_exceptions(
            test_name, lambda: \
            this_module['_' + test_name]())


def _test_catalog_diff_add_file():
    catalog1 = [
        [u'File\u2122', u'Jan 10 10:00'],
    ]
    catalog2 = [
        [u'File\u2122', u'Jan 10 10:00'],
        [u'NewFile\u2122', u'Jan 10 10:00'],
    ]
    expected_output = [[], [
        u'NewFile\u2122'
    ], []]
    _ensure_catalog_diff_matches(catalog1, catalog2, expected_output)


def _test_catalog_diff_edit_file():
    catalog1 = [
        [u'File\u2122', u'Jan 10 10:00'],
    ]
    catalog2 = [
        [u'File\u2122', u'Jan 22 22:22'],
    ]
    expected_output = [[], [], [
        [u'File\u2122', [u'Jan 10 10:00', u'Jan 22 22:22']]
    ]]
    _ensure_catalog_diff_matches(catalog1, catalog2, expected_output)


def _test_catalog_diff_delete_file():
    catalog1 = [
        [u'File\u2122', u'Jan 10 10:00'],
    ]
    catalog2 = [
    ]
    expected_output = [[
        u'File\u2122'
    ], [], []]
    _ensure_catalog_diff_matches(catalog1, catalog2, expected_output)


def _test_catalog_diff_file_becomes_directory():
    catalog1 = [
        [u'Hybrid\u2122', u'Jan 10 10:00'],
    ]
    catalog2 = [
        [u'Hybrid\u2122', u'Jan 10 10:10', [
            [u'File', u'Jan 22 22:22'],
        ]],
    ]
    expected_output = [[u'Hybrid\u2122'], [u'Hybrid\u2122'], []]
    _ensure_catalog_diff_matches(catalog1, catalog2, expected_output)


def _test_catalog_diff_directory_becomes_file():
    catalog1 = [
        [u'Hybrid\u2122', u'Jan 10 10:10', [
            [u'File', u'Jan 22 22:22'],
        ]],
    ]
    catalog2 = [
        [u'Hybrid\u2122', u'Jan 10 10:00'],
    ]
    expected_output = [[u'Hybrid\u2122'], [u'Hybrid\u2122'], []]
    _ensure_catalog_diff_matches(catalog1, catalog2, expected_output)


def _ensure_catalog_diff_matches(catalog1, catalog2, expected_output):
    with NamedTemporaryFile(mode='wb', delete=True) as catalog1_file:
        json.dump(catalog1, catalog1_file)
        catalog1_file.flush()
        
        with NamedTemporaryFile(mode='wb', delete=True) as catalog2_file:
            json.dump(catalog2, catalog2_file)
            catalog2_file.flush()
            
            the_catalog_diff_json = capture_stdout(lambda: \
                catalog_diff.main([catalog1_file.name, catalog2_file.name]))[:-1]
            the_catalog_diff = json.loads(the_catalog_diff_json)
            
            actual_output = the_catalog_diff
            assert_equal(expected_output, actual_output,
                'Catalog diff output did not match expected output.')

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
    if test_stdout != '':
        print test_stdout,
        print


def _print_test_success(test_name):
    print bold_green('OK  %s') % test_name


def capture_stdout(block):
    test_stdout_buffer = StringIO()
    with _replace_stdout(test_stdout_buffer):
        block()
    return test_stdout_buffer.getvalue()


def assert_equal(expected_output, actual_output, message='Assertion failed.'):
    # (Use repr() to ensure that unicodeness of strings is preserved.)
    if repr(expected_output) != repr(actual_output):
        print 'Expected:'
        pprint(expected_output)
        print
        print 'Actual:'
        pprint(actual_output)
        
        raise AssertionError(message)

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
