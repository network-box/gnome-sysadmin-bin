#!/usr/bin/python
#
# Script to create a timestamp file to trigger a GNOME website update.
# Based on the perl scripts we were using with CVS.
#

import sys
import os
import os.path
import time
from optparse import OptionParser

timestamp_dir = "/usr/local/www/gnomeweb/timestamps"

def usage():
    print "usage: " + sys.argv[0] + " [-h] [-m <module>]"
    print "  -m    Set the build flag for <modulename>"

parser = OptionParser()
parser.add_option("-m", "--module", dest="module",
                          help="Module to trigger an update for")
parser.add_option("-b", "--branch", dest="branch", action="store_true",
                          help="Remaining arguments are branches")

parser.set_defaults(branch=False)

(opts, args) = parser.parse_args()

if not opts.module:
    parser.print_usage()
    sys.exit(1)

def update_flag(module, body):
    build_flag = os.path.join(timestamp_dir, module + ".buildflag")

    flagfile = open(build_flag, 'w')
    # Write the time into file
    flagfile.write(time.strftime("Date: %F %T UTC\n", time.gmtime()))
    flagfile.write(body)
    flagfile.close()

# We echo the body into the flag file for debugging purposes
# (it contains the old and new revisions)
body = sys.stdin.read()

if opts.branch:
    for branch in args:
        module = '%s!%s' % (opts.module, branch)
        update_flag(module, body)
else:
    update_flag(opts.module, body)

print "Build flag set."

