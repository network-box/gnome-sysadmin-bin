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
parser.add_option("-b", "--branch", dest="branch", action="store_true",
                          help="Read branch to update from stdin")

parser.set_defaults(branch=False)

(opts, args) = parser.parse_args()

if not opts.module:
    parser.print_usage()
    sys.exit(1)

def update_flag(module, flagline):
    build_flag = os.path.join(timestamp_dir, module + ".buildflag")

    # Create the flag file (write the first line of the e-mail, which
    # I suppose can help identify the last committer)
    flagfile = open(build_flag, 'w')
    flagfile.write(flagline)
    flagfile.close()

if opts.branch:
    branches = [l.strip() for l in sys.stdin.readlines()]
    branches = [l for l in branches if l]
    if len(branches) < 2:
        sys.exit(1)

    flagline = branches.pop()

    for branch in branches:
        module = '%s!%s' % (opts.module, branch)
        update_flag(module, flagline)
else:
    update_flag(opts.module, sys.stdin.readline())

print "Build flag set."

