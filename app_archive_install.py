#!/usr/bin/env python

"""
Automatically installs an app from an archive file.

Syntax:
    app_archive_install.py <box directory> <archive file>
"""

# TODO: Extract common functionality to classicbox.box
import box_up

from classicbox.alias.file import create_alias_file
from classicbox.archive import archive_extract
from classicbox.disk import is_basilisk_supported_disk_image
from classicbox.disk import is_disk_image
from classicbox.disk.hfs import hfs_delete
from classicbox.disk.hfs import hfs_exists
from classicbox.disk.hfs import hfs_ls
from classicbox.disk.hfs import hfs_mount
from contextlib import contextmanager
import os
import os.path
import sys
from tempfile import NamedTemporaryFile


RECOGNIZED_INSTALLER_APP_CREATORS = [
    u'STi0',         # Stuffit InstallerMaker
    # TODO: What about InstallerVISE?
]


def main(args):
    # Parse arguments
    (box_dirpath, archive_filepath) = args
    
    # Extract the archive
    with archive_extract(archive_filepath) as archive:
        contents_dirpath = archive.extraction_dirpath
        
        # TODO: Probably will need to be smarter here for archives
        #       that expand with a single directory at the root
        
        # Locate disk images in archive, if any
        disk_image_filepaths = []
        for filename in os.listdir(contents_dirpath):
            if is_disk_image(filename):
                disk_image_filepaths.append(os.path.join(contents_dirpath, filename))
        
        # Identify the primary disk image
        if len(disk_image_filepaths) == 0:
            # TODO: ...
            raise NotImplementedError('Did not find any disk images in archive. Not sure what to do.')
            
        elif len(disk_image_filepaths) == 1:
            primary_disk_image_filepath = disk_image_filepaths[0]
            
        elif len(disk_image_filepaths) >= 2:
            # TODO: Probably want to ask the user to select one of the disk
            #       images as the primary disk image.
            raise NotImplementedError('Found multiple disk images in archive. Not sure what to do.')
        
        # Open the primary disk image
        hfs_mount(primary_disk_image_filepath)
        
        # List the root items
        root_items = hfs_ls()
        
        # Look for installer apps
        installer_app_items = []
        for item in root_items:
            if item.type == u'APPL' and item.creator in RECOGNIZED_INSTALLER_APP_CREATORS:
                installer_app_items.append(item)
        
        # Identify the primary installer app
        if len(installer_app_items) == 0:
            # TODO: Continue looking for the designated app...
            raise NotImplementedError('Did not find any installer applications. Not sure what to do.')
            
        elif len(installer_app_items) == 1:
            primary_installer_app_item = installer_app_items[0]
            
        elif len(installer_app_items) >= 2:
            # TODO: Extract to method
            print 'Found multiple installer applications.'
            while True:
                print
                print 'Please choose the primary installer for this program:'
                i = 1
                for item in installer_app_items:
                    # TODO: It looks like I need to be very careful about printing
                    #       any str-macroman types I receive from lower level functions.
                    #       Remembering to do this everywhere could get quite burdensome,
                    #       so I suggest actually converting all true strings to Unicode
                    #       upon input.
                    print '    %d: %s' % (i, item.name); i += 1
                print '    %d: <Cancel>' % i; i += 1
                try:
                    choice = int(raw_input('Choice? '))
                    if choice >= i:
                        raise ValueError
                    if choice == (i - 1):
                        # Cancel
                        return
                    else:
                        primary_installer_app_item = installer_app_items[choice - 1]
                        break
                except ValueError:
                    print 'Not a valid choice.'
                    continue
            print
        
        # Temporarily mount the disk images inside the VM
        with mount_disk_images_temporarily(box_dirpath, disk_image_filepaths):
            
            # Set the installer app as the boot app
            set_boot_app_of_box(
                box_dirpath,
                primary_disk_image_filepath, [primary_installer_app_item.name])
            
            # Boot the box and wait for the user to install the app
            run_box(box_dirpath)
            
            # Look for the installed app and set it as the boot app
            raise NotImplementedError
    
    pass


@contextmanager
def mount_disk_images_temporarily(box_dirpath, disk_image_filepaths):
    if len(disk_image_filepaths) != 1:
        raise NotImplementedError('Multiple simultenous images not yet implemented.')
    disk_image_filepath = disk_image_filepaths[0]
    
    mount_dirpath = os.path.join(box_dirpath, 'mount')
    disk_image_ext = os.path.splitext(disk_image_filepath)[1]
    link_filepath = _mktemp_dammit(dir=mount_dirpath, suffix=disk_image_ext)
    
    # NOTE: os.symlink() is not available on Windows.
    #       The underlying emulators support Windows .lnk files, so those should
    #       be created on Windows systems. Be sure to test box_up() when such
    #       links are present.
    os.symlink(disk_image_filepath, link_filepath)
    try:
        yield
    finally:
        os.remove(link_filepath)


def _mktemp_dammit(*args, **kwargs):
    """
    Same as tempfile.mktemp(), but isn't a deprecated function.
    
    Note that this function is vulnerable to symlink attacks.
    Recommended only when `dir` is specified explicitly.
    """
    with NamedTemporaryFile(*args, delete=False, **kwargs) as file:
        pass
    
    temp_filepath = file.name
    os.remove(temp_filepath)
    return temp_filepath


def set_boot_app_of_box(box_dirpath, disk_image_filepath, app_filepath_components):
    install_autoquit_in_box(box_dirpath)
    set_autoquit_app(box_dirpath, disk_image_filepath, app_filepath_components)

# ------------------------------------------------------------------------------
# install_autoquit_in_box

def install_autoquit_in_box(box_dirpath):
    # Check whether already installed
    if is_autoquit_in_box(box_dirpath):
        return
    
    # NOTE: I can delay implementing this by cheating and installing AutQuit7
    #       manually for the time being.
    raise NotImplementedError


def is_autoquit_in_box(box_dirpath):
    try:
        locate_autoquit_in_box(box_dirpath)
        return True
    except AutoQuitNotFoundError:
        return False


class AutoQuitNotFoundError(Exception):
    pass

def locate_autoquit_in_box(box_dirpath):
    boot_disk_image_filepath = locate_boot_volume_of_box(box_dirpath)
    
    # TODO: Eventually need to also check for the AutoQuit variant of this
    #       program for System 6 and below.
    autoquit_dirpath_components = ['System Folder', 'AutQuit7']
    
    if hfs2_exists(boot_disk_image_filepath, autoquit_dirpath_components):
        return (boot_disk_image_filepath, autoquit_dirpath_components)
    else:
        raise AutoQuitNotFoundError


class BootVolumeNotFoundError(Exception):
    pass

def locate_boot_volume_of_box(box_dirpath):
    for disk_image_filepath in volumes_of_box(box_dirpath):
        if hfs2_exists(disk_image_filepath, ['System Folder']):
            return disk_image_filepath
    raise BootVolumeNotFoundError


def volumes_of_box(box_dirpath):
    mount_dirpath = os.path.join(box_dirpath, 'mount')
    
    for root, dirs, files in os.walk(mount_dirpath):
        for file in files:
            # FIXME: Determine emulator type of box first to determine what
            #        types of disk images are supported. Here we assume that
            #        the box is a Basilisk box.
            if is_basilisk_supported_disk_image(file):
                yield os.path.join(root, file)

# ------------------------------------------------------------------------------
# set_autoquit_app

def set_autoquit_app(box_dirpath, disk_image_filepath, app_filepath_components):
    (boot_disk_image_filepath, autoquit_dirpath_components) = locate_autoquit_in_box(box_dirpath)
    
    autoquit_app_alias_filepath_components = autoquit_dirpath_components + ['app']
    if hfs2_exists(boot_disk_image_filepath, autoquit_app_alias_filepath_components):
        hfs2_delete(boot_disk_image_filepath, autoquit_app_alias_filepath_components)
    
    create_alias_file_2(
        boot_disk_image_filepath, autoquit_app_alias_filepath_components,
        disk_image_filepath, app_filepath_components)


def run_box(box_dirpath):
    try:
        box_up.main([box_dirpath])
    except SystemExit as e:
        if e.code == 0:
            pass
        else:
            raise
    print

# ------------------------------------------------------------------------------
# TODO: Make consistent and extract to classicbox.alias.file

def create_alias_file_2(
        output_disk_image_filepath, output_filepath_components,
        target_disk_image_filepath, target_filepath_components):
    
    output_macitempath = _mount_disk_image_and_resolve_path(
        output_disk_image_filepath, output_filepath_components)
    target_macitempath = _mount_disk_image_and_resolve_path(
        target_disk_image_filepath, target_filepath_components)
    create_alias_file(
        output_disk_image_filepath, output_macitempath,
        target_disk_image_filepath, target_macitempath)

# ------------------------------------------------------------------------------
# TODO: Make consistent and extract to classicbox.disk.hfs

def hfs2_exists(disk_image_filepath, itempath_components):
    macitempath = _mount_disk_image_and_resolve_path(disk_image_filepath, itempath_components)
    return hfs_exists(macitempath)


def hfs2_delete(disk_image_filepath, itempath_components):
    macitempath = _mount_disk_image_and_resolve_path(disk_image_filepath, itempath_components)
    hfs_delete(macitempath)


def hfs2_delete_if_exists(disk_image_filepath, itempath_components):
    if hfs2_exists(disk_image_filepath, itempath_components):
        hfs2_delete(disk_image_filepath, itempath_components)


def _mount_disk_image_and_resolve_path(disk_image_filepath, itempath_components):
    volume_info = hfs_mount(disk_image_filepath)
    volume_name = volume_info['name']
    
    macitempath = '%s:%s' % (volume_name, ':'.join(itempath_components))
    return macitempath

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])