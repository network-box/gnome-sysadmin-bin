#!/usr/bin/python
#
# Script to create a timestamp file to trigger a GNOME website update.
# Based on the perl scripts we were using with CVS.
#

import sys
import os
import getopt

timestamp_dir = "/usr/local/www/gnomeweb/timestamps"

def usage():
	print "usage: " + sys.argv[0] + " [-h] [-m <module>]"
	print "  -m    Set the build flag for <modulename>"

try:                                
	opts, args = getopt.getopt(sys.argv[1:], "hm:", ["help", "module="])
except getopt.GetoptError:
        usage()
        sys.exit()
for opt, arg in opts:
	if opt in ("-m", "--module"):
		module = arg
if(module == ""):
	usage()
	sys.exit()

build_flag = timestamp_dir + "/" + module + ".buildflag"

# Create the flag file (write the first line of the e-mail, which
# I suppose can help identify the last committer)
flagfile = open(build_flag, 'w')
flagfile.write(sys.stdin.readline())
flagfile.close()

print "Build flag set."

