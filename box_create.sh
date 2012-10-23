#!/bin/sh

# 
# Creates a blank box directory, for use with the box_up command.
# 
# The user must manually populate the box with:
# (1) [bin] An emulator such as Basilisk.
# (2) [rom] A ROM package.
# (3) [mount] A boot disk.
# 
# Syntax:
#   box_create.sh <dirpath>
# 

mkdir "$1"
mkdir "$1/bin"
mkdir "$1/etc"
mkdir "$1/mount"
mkdir "$1/mount-disabled"
mkdir "$1/rom"
mkdir "$1/share"
