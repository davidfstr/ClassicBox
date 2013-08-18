# Classic Box <small>(CPM Project)</small>

The CPM project contains a collection of tools and prototypes for manipulating virtual machines that run early Macintosh operating systems (System 1 - Mac OS 9).

Much of this software is incomplete. I am publishing it now because I am no longer actively working on it.

## Vision

Allow one-click installation of arbitrary Mac OS 0.x - 9.x
games and apps from the 1980s and 1990s.

## Tools

* **app_archive_install**
    - Attempts to automatically install an application from an archive
      file downloaded from Macintosh Garden or a similar site into a box.
    - This tool is incomplete.
* **box_create, box_up**
    - Low-level tools for manipulating boxes.
    - A **box** is a self-contained classic Mac OS virtual machine.
      It is a directory in a special layout containing emulation
      software, a machine ROM, mounted disk images, and preferences.
* **box_bootstrap**
    - Similar to box_create but automatically installs the minimum
      set of components for the box to function, namely an emulator,
      a machine ROM, and a boot disk image.
    - Requires an emulator package, a ROM package, and an OS boot
      disk package as inputs.
    - I am not currently distributing any of these packages myself
      for copyright reasons.
* **catalog_create, catalog_diff**
    - Utilities that manipulate *catalog* structures, which describe the
      name and last modified date of files on an HFS disk image.

## Libraries

Much functionality here is likely to be useful in other tools.

* **classicbox.alias.file**
    - Read and write alias files.
* **classicbox.alias.record**
    - Read and write alias records, typically found in alias files.
* **classicbox.archive**
    - Extracts compressed archives in arbitrary formats.
    - Depends on [unar] to do the heavy lifting.
* **classicbox.disk.hfs**
    - Manipulate and inspect HFS disk images and contained files.
    - Depends on [hfsutils] to do the heavy lifting.
* **classicbox.io**
    - Read and write complex binary structures.
    - Shims for performing I/O in Python 2 and 3 with the same interface.
* **classicbox.macbinary**
    - Read MacBinary I, II, or III files.
    - Write MacBinary III files.
* **classicbox.resource_fork**
    - Read and write Mac resource forks.

## Requirements

* Mac OS X 10.7 (Lion)
    * Support for Windows and other versions of Mac OS X will be added over time.
* Python 2.7
    * Experimental support for Python 3 exists after conversion by the `2to3` tool.  
      Particularly for code exercised by the `test` tool.
* The following tools must be installed and in your system path:
    * [hfsutils] 3.2.6 &ndash; hdel, hdir, hmkdir, hmount, hpwd
    * [unar] 1.3 &ndash; unar

[hfsutils]: http://www.mars.org/home/rob/proj/hfs/
[unar]: http://unarchiver.c3.cx/commandline

## License

Copyright (c) 2013 David Foster.

This software is licensed under the GPLv2. See the [LICENSE](LICENSE-GPLv2.txt) file for more information.

## Historical Notes

### Names

The acronym "CPM" originally signified "Classic Package Manager", when I
conceived of this project as a kind of package manager that could install
prepared packages into a classic Mac OS virtual machine.
CPM is now an umbrella term for all tools related to the effort of
making it *easy* to run classic Mac software on modern hardware.

"Classic Box" refers to the idea of a classic Mac OS virtual machine
bundled as a single executable program. Similar to VMware or Parallels,
but without support for managing multiple machines. Classic Box is part
of the larger CPM project.

"classicbox" is the root package name for shared and reusable components
of the CPM project.
