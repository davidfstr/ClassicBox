#!/usr/bin/env python

"""
Creates a box directory for use with the box_up command.

The box is automatically bootstrapped with:
(1) An emulator such as Basilisk.
(2) A ROM package.
(3) A boot disk.

These components are automatically installed from the packages specified by the user.

Syntax:
  box_bootstrap.py <box directory path> <emulator package name> <ROM package name> <OS boot disk package name>
"""

import json
import os
import os.path
import shutil
import subprocess
import sys
import tempfile


SCRIPT_DIRPATH = os.path.dirname(__file__)

# The `unar` tool is used to extract archive files
UNAR_BINARY_FILEPATH = os.path.join(
    SCRIPT_DIRPATH, 'contrib', 'unar1.3', 'unar')

# NOTE: We are temporarily cheating by mapping the package cache directory
#       to the website contents, which would not normally be possible on
#       on end user's machine. This also means that no existant package needs
#       to be downloaded to the cache (because it will already be there).
PACKAGE_CACHE_DIRPATH = os.path.join(
    SCRIPT_DIRPATH, 'api.classicbox.io', 'packages')
    #SCRIPT_DIRPATH, 'package_cache')

DEVNULL = open(os.devnull, 'wb')


def main(args):
    # Parse arguments
    if len(args) != 4:
        # TODO: Support installing from an emulator group (i.e. "Basilisk_II")
        #       rather than an exact package name.
        # TODO: Support installing using a "box package" that
        #       automatically specifies what emulator, ROM, and OS to use.
        sys.exit('syntax: box_bootstrap.py <box directory path> <emulator package name> <ROM package name> <OS boot disk package name>')
        return
    (box_dirpath, emulator_package_name, rom_package_name, os_boot_disk_package_name) = args
    
    if os.path.exists(box_dirpath):
        sys.exit('Directory already exists: %s' % box_dirpath)
        return
    
    # TODO: Automatically download the specified packages if necessary.
    #       (Currently we just assume that they're already available.)
    
    create_empty_box(box_dirpath)
    try:
        install_binary_from_emulator_package(
            emulator_package_name,
            os.path.join(box_dirpath, 'bin'))
        
        install_rom_from_rom_package(
            rom_package_name,
            os.path.join(box_dirpath, 'rom'))
        
        install_disk_from_disk_package(
            os_boot_disk_package_name,
            os.path.join(box_dirpath, 'mount'))
        
        install_recommended_preferences(
            os.path.join(box_dirpath, 'etc'))
    except:
        # Cleanup incomplete box if there was an error
        shutil.rmtree(box_dirpath)
        
        raise


def create_empty_box(box_dirpath):
    os.mkdir(box_dirpath)
    os.mkdir(os.path.join(box_dirpath, 'bin'))
    os.mkdir(os.path.join(box_dirpath, 'etc'))
    os.mkdir(os.path.join(box_dirpath, 'mount'))
    os.mkdir(os.path.join(box_dirpath, 'mount-disabled'))
    os.mkdir(os.path.join(box_dirpath, 'rom'))
    os.mkdir(os.path.join(box_dirpath, 'share'))


def install_binary_from_emulator_package(package_name, output_dirpath):
    install_package_contents_to_directory(package_name, output_dirpath, 'emulator')


def install_rom_from_rom_package(package_name, output_dirpath):
    install_package_contents_to_directory(package_name, output_dirpath, 'rom')


def install_disk_from_disk_package(package_name, output_dirpath):
    install_package_contents_to_directory(package_name, output_dirpath, 'boot_disk')


def install_package_contents_to_directory(package_name, output_dirpath, expected_package_type):
    # Ensure the specified package exists
    package_dirpath = os.path.join(PACKAGE_CACHE_DIRPATH, package_name)
    if not os.path.exists(package_dirpath):
        raise Exception('No such package "%s".' % package_name)
    
    # Locate the archive file in the package
    with open(os.path.join(package_dirpath, 'metadata.json'), 'rb') as metadata_file:
        metadata = json.load(metadata_file)
    actual_package_type = metadata['type']
    if actual_package_type != expected_package_type:
        raise Exception('Expected package "%s" to be an "%s" package. It is a "%s" package.' % (
            package_name, expected_package_type, actual_package_type))
    files = metadata['files']
    # TODO: This limitation is not great for forward compatibility.
    if len(files) != 1:
        raise Exception('Expected emulator package "%s" to have exactly one file. It has %s.' % (
            package_name, len(files)))
    archive_filename = files.keys()[0]
    archive_metadata = files.values()[0]
    archive_filepath = os.path.join(package_dirpath, 'files', archive_filename)
    
    # Extract the archive file to a temporary extraction directory
    extraction_dirpath = tempfile.mkdtemp()
    try:
        if not os.path.exists(UNAR_BINARY_FILEPATH):
            raise Exception('Unable to locate "unar" tool. Expected to find it at "%s".' % UNAR_BINARY_FILEPATH)
        subprocess.check_call([
            UNAR_BINARY_FILEPATH,
            # recursively extract inner archives by default
            '-forks', 'fork',   # save resource forks natively (OS X only)
            '-no-quarantine',   # don't display warnings upon launch of extracted apps
            '-no-directory',    # don't create an extra enclosing directory
            '-output-directory', extraction_dirpath,
            archive_filepath
        ], stdout=DEVNULL, stderr=DEVNULL)
        
        # Locate the target item in the extraction directory
        target_itempath_components = archive_metadata['contents']
        target_itempath = os.path.join(extraction_dirpath, *target_itempath_components)
        
        # Move the emulator binary to the output directory
        shutil.move(target_itempath, output_dirpath)
    finally:
        # Delete the extraction directory
        shutil.rmtree(extraction_dirpath)


def install_recommended_preferences(prefs_dirpath):
    with open(os.path.join(prefs_dirpath, 'nojit.prefs'), 'wb') as nojit_file:
        nojit_file.write('# Disable JIT, as it causes compatibility problems with many programs\n')
        nojit_file.write('jit false\n')
        nojit_file.write('jitfpu false\n')


if __name__ == '__main__':
    main(sys.argv[1:])
