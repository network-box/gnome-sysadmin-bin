#!/usr/bin/python
#
# Script to create a timestamp file to trigger a GNOME website update.
# Based on the perl scripts we were using with CVS.
#

import sys
import os
import os.path
from optparse import OptionParser

timestamp_dir = "/usr/local/www/gnomeweb/timestamps"

def usage():
    print "usage: " + sys.argv[0] + " [-h] [-m <module>]"
    print "  -m    Set the build flag for <modulename>"

parser = OptionParser()
parser.add_option("-m", "--module", dest="module",
                          help="Module to trigger an update for")
parser.add_option("-b", "--branch", dest="branch",
                          help="Branch to update")

parser.set_defaults(kill=False, remove_seen=False, delete=False)

(opts, args) = parser.parse_args()

if not opts.module:
    parser.print_usage()
    sys.exit(1)

if opts.branch:
    module = '%s!%s' % (opts.module, opts.branch)
else:
    module = opts.module

build_flag = os.path.join(timestamp_dir, module + ".buildflag")

# Create the flag file (write the first line of the e-mail, which
# I suppose can help identify the last committer)
flagfile = open(build_flag, 'w')
flagfile.write(sys.stdin.readline())
flagfile.close()

print "Build flag set."

