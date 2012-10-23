#!/usr/bin/env python

"""
Launches Basilisk, SheepShaver, or Mini vMac from a "box" directory that
contains all the necessary components of the virtual machine.

This script is responsible for generating an emulator preferences file
that points to the items in the box (if applicable) and launching
the emulator with that preferences file.

This is a tracer.
"""

from classicbox.disk import is_basilisk_supported_disk_image
from classicbox.disk import is_mini_vmac_supported_disk_image
import md5
import os
import os.path
import subprocess
import sys


def main(args):
    # Parse flags
    verify_rom = True
    if len(args) >= 1 and args[0] == '-f':
        verify_rom = False
        args = args[1:]
    
    # Parse arguments
    if len(args) != 1:
        sys.exit('syntax: box_up <path to box directory>')
        return
    box_dirpath = os.path.abspath(args[0])
    if not os.path.exists(box_dirpath):
        sys.exit('file not found: ' + box_dirpath)
        return
    
    # Compute paths to important directories and files
    bin_dirpath = os.path.join(box_dirpath, 'bin')
    etc_dirpath = os.path.join(box_dirpath, 'etc')
    rom_dirpath = os.path.join(box_dirpath, 'rom')
    share_dirpath = os.path.join(box_dirpath, 'share')
    mount_dirpath = os.path.join(box_dirpath, 'mount')
    
    minivmac_filepath = os.path.join(bin_dirpath,
        'Mini vMac.app', 'Contents', 'MacOS', 'minivmac')
    basilisk_filepath = os.path.join(bin_dirpath,
        'BasiliskII.app', 'Contents', 'MacOS', 'BasiliskII')
    sheepshaver_filepath = os.path.join(bin_dirpath,
        'SheepShaver.app', 'Contents', 'MacOS', 'SheepShaver')
    
    if os.path.exists(minivmac_filepath):
        emulator_filepath = minivmac_filepath
        prefs_filepath = None
    elif os.path.exists(basilisk_filepath):
        emulator_filepath = basilisk_filepath
        prefs_filepath = os.path.join(etc_dirpath, '.basilisk_ii_prefs')
    elif os.path.exists(sheepshaver_filepath):
        emulator_filepath = sheepshaver_filepath
        prefs_filepath = os.path.join(etc_dirpath, '.sheepshaver_prefs')
    else:
        sys.exit('Cannot locate a supported emulator in the bin directory.')
        return
    
    # Locate ROM file
    rom_filepath = None
    for root, dirs, files in os.walk(rom_dirpath):
        for file in files:
            # Find the first .rom file and use it
            if file.lower().endswith('.rom'):
                if rom_filepath is not None:
                    sys.exit('Multiple ROM files found.')
                    return
                rom_filepath = os.path.join(root, file)
    if rom_filepath is None:
        sys.exit('Cannot locate ROM file.')
        return
    
    # Load ROM file for further checks
    with open(rom_filepath, 'rb') as rom_file:
        rom = rom_file.read()
        rom_size = len(rom)
    
    # A user may want to override the following ROM checks, since
    # an invalid ROM often works inside emulators. Furthermore some
    # commonly distributed copies of ROMs are bogus (especially vMac.ROM).
    if verify_rom:
        # Verify ROM checksum (if OldWorld ROM)
        is_newworld_rom = rom.startswith('<CHRP-BOOT>')
        is_oldworld_rom = not is_newworld_rom
        if is_oldworld_rom:
            expected_checksum = get_oldworld_rom_embedded_checksum(rom)
            actual_checksum = compute_oldworld_rom_actual_checksum(rom)
            if actual_checksum != expected_checksum:
                sys.exit('Invalid ROM checksum. Expected %08x but found %08x.' % (
                    expected_checksum,
                    actual_checksum
                ))
                return
        
        # Verify ROM size
        if is_oldworld_rom:
            if rom_size not in [64*1024, 128*1024, 256*1024, 512*1024, 1*1024*1024, 2*1024*1024, 4*1024*1024]:
                sys.exit('Invalid ROM file size. Expected 64k, 128k, 256k, 512k, 1m, 2m, or 4m.')
                return
        
        # There are chopped versions of the Mac Classic ROM on the internet
        # that only have the first 256k. Detect this.
        if get_oldworld_rom_embedded_checksum(rom) == 0xA49F9914 and rom_size != 512 * 1024:   
            if rom_size == 256 * 1024:
                sys.exit('This Mac Classic ROM is missing its last 256k. Booting it with Command-Option-X-O will not work.')
                return
            else:
                sys.exit('Invalid ROM size. Expected %d bytes but found %d bytes.' % (
                    512 * 1024,
                    rom_size
                ))
                return
    
    using_minivmac = (emulator_filepath == minivmac_filepath)
    using_basilisk = (emulator_filepath == basilisk_filepath)
    if using_minivmac:
        rom = None  # permit early garbage collection
        
        # Locate disk images
        disk_filepaths = []
        for root, dirs, files in os.walk(mount_dirpath):
            for file in files:
                if is_mini_vmac_supported_disk_image(file):
                    disk_filepaths.append(os.path.join(root, file))
        
        # Create a symlink to the ROM file with the name required by Mini vMac,
        # and locate it in the same directory as the Mini vMac binary.
        # NOTE: When porting to Windows, Mini vMac explicitly supports a
        #       Windows-style .lnk file. See the docs for details.
        rom_link_filepath = os.path.join(bin_dirpath, 'vMac.ROM')
        if os.path.exists(rom_link_filepath):
            # Cleanup old link
            # TODO: Fail if isn't a link (i.e. if there is already
            #       a full ROM file here).
            os.remove(rom_link_filepath)
        os.symlink(rom_filepath, rom_link_filepath)
        
        returncode = 1
        try:
            # Start Mini vMac
            # NOTE: Unlike for Basilisk or SheepShaver, it is not necessary
            #       to fake the home directory, since Mini vMac does not
            #       have any configuration files at all.
            minivmac_process = subprocess.Popen([emulator_filepath])
            
            # Mount all of the disks (by simulating a drag of each disk to the
            # Mini vMac application icon).
            # 
            # <strike>Do this twice because the system will eject disks until a valid
            #         boot disk is inserted.</strike>
            # Mini vMac complains about multiple mounts & file in use.
            # TODO: Will need a more creative solution, perhaps checking whether
            #       a file is "in use" before dragging to Mini vMac.
            for i in xrange(1): #xrange(2):
                for disk_filepath in disk_filepaths:
                    subprocess.call(['open', '-a', emulator_filepath, disk_filepath])
            
            # Wait for Mini vMac to terminate
            minivmac_process.wait()
            returncode = minivmac_process.returncode
        finally:
            os.remove(rom_link_filepath)
        
        # Exit with emulator's return code
        sys.exit(returncode)
        return
        
    else:
        # Create preferences file
        with open(prefs_filepath, 'wb') as prefs:
            # Write ROM section
            prefs.write('# ROM\n')
            prefs.write('rom ' + rom_filepath + '\n')
            rom_prefs_filepath = rom_filepath + '.prefs'
            if os.path.exists(rom_prefs_filepath):
                prefs.write(open(rom_prefs_filepath, 'rb').read())
            
            # Write disks section
            prefs.write('# Disks\n')
            for root, dirs, files in os.walk(mount_dirpath):
                for file in files:
                    if is_basilisk_supported_disk_image(file):
                        prefs.write('disk ' + os.path.join(root, file) + '\n')
            
            # Write shared folder section
            if os.path.exists(share_dirpath):
                prefs.write('# Shared folder\n')
                prefs.write('extfs ' + share_dirpath + '\n')
            
            # Write networking section
            prefs.write('# Networking\n')
            if using_basilisk:
                prefs.write('udptunnel true\n')
                prefs.write('udpport 6066\n')   # default, but it's nice to be explicit
            
            # Write extra preferences
            for root, dirs, files in os.walk(etc_dirpath):
                for file in files:
                    if file.lower().endswith('.prefs'):
                        prefs.write('# Extra: ' + file + '\n')
                        prefs.write(open(os.path.join(root, file), 'rb').read())
        
        zap_pram_if_rom_changed(rom, etc_dirpath)
        rom = None  # permit early garbage collection
        
        # Launch Basilisk/SheepShaver, relocating its preferences file to the 'etc' directory
        returncode = subprocess.call([emulator_filepath], cwd=box_dirpath, env={
            'HOME': etc_dirpath,
        })
        
        # Exit with emulator's return code
        sys.exit(returncode)
        return


def get_oldworld_rom_embedded_checksum(rom):
    if len(rom) < 4:
        return 0
    
    # read_uint32(0)
    return (
        (ord(rom[0]) << 24) |
        (ord(rom[1]) << 16) |
        (ord(rom[2]) << 8) |
        (ord(rom[3]) << 0)
    )


def compute_oldworld_rom_actual_checksum(rom):
    """
    Computes the checksum of the ROM which can be verified
    against the checksum stored in the first 4 bytes of the ROM.
    
    Kudos for Dennis Nedry for discovering the algorithm by
    reverse engineering the checksum verification code in the
    Mac SE ROM.
    """
    rom_size = len(rom)
    
    start = 4
    # Only sum the first 3 MB for 4 MB ROMs
    end = min(rom_size & ~1, 3 * 1024 * 1024)
    
    # The checksum for the Mac Classic ROM covers only the 
    # first 256k out of the full 512k.
    if get_oldworld_rom_embedded_checksum(rom) == 0xA49F9914:   # Mac Classic
        end = 256 * 1024
    
    sum = 0
    i = start
    while i < end:
        sum += (ord(rom[i]) << 8) | ord(rom[i + 1])
        sum &= 0xFFFFFFFF
        i += 2
    
    return sum


def zap_pram_if_rom_changed(rom, etc_dirpath):
    last_rom_md5_filepath = os.path.join(etc_dirpath, '.last_rom_md5')
    pram_filepath = os.path.join(etc_dirpath, '.basilisk_ii_xpram')
    
    # Compute MD5 of current ROM
    rom_md5 = md5.new(rom).hexdigest()
    
    # Lookup MD5 of last ROM
    if os.path.exists(last_rom_md5_filepath):
        with open(last_rom_md5_filepath, 'rb') as last_rom_md5_file:
            last_rom_md5 = last_rom_md5_file.read()
    else:
        last_rom_md5 = None
    
    # Zap PRAM if current ROM is different than last ROM
    if rom_md5 != last_rom_md5:
        if os.path.exists(pram_filepath):
            print 'Zapping PRAM because ROM changed.'
            os.remove(pram_filepath)
    
    # Save MD5 of current ROM
    with open(last_rom_md5_filepath, 'wb') as last_rom_md5_file:
        last_rom_md5_file.write(rom_md5)


if __name__ == '__main__':
    main(sys.argv[1:])