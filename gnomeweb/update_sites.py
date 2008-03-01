#!/usr/bin/python
#
# This script is called from cron every minute or so. It will read a list
# of modules and check the timestamps for each module. Any modules that
# have commits since their last build will be rebuilt. Rebuilding is just
# a case of spawning a 'svn update' in the right directory, and maybe
# calling a post-update hook script if one exists.
#

import glob
import sys
import os
import os.path
import ConfigParser
import subprocess
import fcntl
import re
from optparse import OptionParser

import xml.dom.minidom # to parse svn xml output

timestamp_dir = "/usr/local/www/gnomeweb/timestamps"
hookscripts_dir = "/usr/local/www/gnomeweb/hooks"
checkout_url = "http://svn.gnome.org/svn/%s/%s" # %s for module name
checkout_basedir = "/usr/local/www/gnomeweb/svn-wd" # default base directory for checkouts
log_dir = "/usr/local/www/gnomeweb/logs"
re_branch_versioned = r'^gnome-([0-9]+)-([0-9]+)$'

FAILURE_MAIL = """Failure updating %(url)s.

Last commit by: %(author)s
ViewCVS: http://svn.gnome.org/viewcvs/%(module)s?rev=%(rev)s&view=rev

Last few lines of output:

%(outputtail)s

Full output can be seen at http://www.gnome.org/updatelogs/%(module)s.out"""


parser = OptionParser()
parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                          help="Be verbose")
parser.add_option("-c", "--config", dest="configfile", metavar="FILE",
                                  help="Read list of modules from FILE")
parser.set_defaults(verbose=False)


def get_svn_info(path):
    xmls = subprocess.Popen(["svn", "info", '--xml', path], stdout=subprocess.PIPE).communicate()[0]
    document = xml.dom.minidom.parseString(xmls)
    
    try: author = document.getElementsByTagName('author')[0].firstChild.nodeValue
    except: author = ""

    try: rev = document.getElementsByTagName('entry')[0].getAttribute('revision')
    except: rev = ""

    return author, rev

def update_modules(configfile, verbose):
    cfg = ConfigParser.ConfigParser()
    cfg.read([configfile])

    for module in sorted(cfg.sections(),
                         lambda a, b: cmp((cfg.has_option(a, 'order')
                                           and [cfg.get(a, 'order')]
                                           or [a])[0],
                                          (cfg.has_option(b, 'order')
                                           and [cfg.get(b, 'order')]
                                           or [b])[0])):
        # Check if the module is disabled
        if cfg.has_option(module, 'disabled') and cfg.getboolean(module, 'disabled'):
            continue

        # Retrieve configuration settings
        url = cfg.get(module, 'url')
        if cfg.has_option(module, 'root'):
            moduleroot = cfg.get(module, 'root')
        else:
            moduleroot = os.path.join(checkout_basedir, module)
        if cfg.has_option(module, 'owner'):
            owner = cfg.get(module, 'owner')
        else:
            owner = None
        if cfg.has_option(module, 'branches'):
            branches = cfg.getboolean(module, 'branches')
        else:
            branches = False

        if branches:
            # FIXME: Add branches support
            files = glob.glob(os.path.join(timestamp_dir, module + "!*.buildflag"))
            for fn in files:
                branch = re.sub(r'^' + re.escape(module) + r'!(.*)\.buildflag', 
                                r'\1', os.path.basename(fn))

                checkfile = '%s!%s' % (module, branch) # Merge again for update_module
                version = re.sub(re_branch_versioned, r'\1.\2', branch)

                url = checkout_url % (module, 'branches/' + branch)
                b_moduleroot = '%s-%s' % (moduleroot, version)
                update_module(module, checkfile, b_moduleroot, url, verbose=verbose)
        else:
            url = checkout_url % (module, 'trunk')
            update_module(module, module, moduleroot, url, verbose=verbose)


def update_module(module, checkfile, moduleroot, url, verbose=False):
    # Compare timestamps
    if verbose:
        print "Checking '" + module + "'..."
    build_flag = os.path.join(timestamp_dir, checkfile + ".buildflag")
    built_flag = os.path.join(timestamp_dir, checkfile + ".built")
    lock_file  = os.path.join(timestamp_dir, checkfile + '.lock')

    # If the buildflag hasn't been set, ignore this module for now
    if not os.access(build_flag, os.F_OK):
        return False

    # Only need to compare if built flag exists
    t_build = os.stat(build_flag)
    if os.access(built_flag, os.F_OK):
        t_built = os.stat(built_flag)
        if t_build.st_mtime <= t_built.st_mtime:
            # No need to build
            return False

        # Ensure only one copy will be running
        fpl = open(lock_file, 'w')
        try:
            fcntl.flock(fpl, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            if verbose:
                print "Already running"
            return False
        fpl.write("%d" % os.getpid())
        fpl.flush()
        if verbose:
            print "Wrote PID to lock file (PID: %d)" % os.getpid()

    # Run a svn checkout/update
    retval = 0
    if not os.path.exists(moduleroot):
        # Path does not exist.. so check it out of SVN
        if verbose:
            print "Running 'svn checkout " + moduleroot + "'..."
        retval = os.spawnlp(os.P_WAIT, 'svn', 'svn', 'checkout', '-q', '--non-interactive', url, moduleroot)
    else:
        if verbose:
            print "Running 'svn update " + moduleroot + "'..."
        retval = os.spawnlp(os.P_WAIT, 'svn', 'svn', 'update', '-q', '--non-interactive', moduleroot)
    if retval != 0:
        print "Updating the '" + module + "' site failed"
        return False

    # We're done if there isn't a post-update hook to run
    hook_file = os.path.join(hookscripts_dir, module)
    if not os.access(hook_file, os.X_OK):
        if not os.path.isfile(built_flag):
            f = open(built_flag, 'w')
            f.close()
        os.utime(built_flag, (t_build.st_mtime, t_build.st_mtime))
        return True

    # Run the hook script and save the stdout+stderr in a logfile
    if verbose:
        print "Running hook script..."
    logfile_name = "%s/%s.out.%s" % (log_dir, checkfile, os.getpid())
    logfile = open(logfile_name, "w")
    retval = subprocess.call([hook_file, module, moduleroot], stdout=logfile, stderr=subprocess.STDOUT, close_fds=True, cwd=moduleroot)
    logfile.close()

    if retval != 0 and verbose:
        print "Hook script failed with exitcode: %s" % retval

    # When an error occurs: inform the owner via email
    if retval != 0 and owner:
        # Generate contents of the mail
        author, rev = get_svn_info(moduleroot)
        outputtail = subprocess.Popen(["tail", "-n30", logfile_name], stdout=subprocess.PIPE).communicate()[0]
        mailmessage = FAILURE_MAIL % locals()
        
        # Send the mail
        cmd = ['mail', '-s', "Failure updating %s" % url, owner]
        if author:
            cmd.append("%s@svn.gnome.org" % author)
        obj = subprocess.Popen(cmd, stdin=subprocess.PIPE, close_fds=True)
        obj.stdin.write(mailmessage)
        obj.stdin.close()
        obj.wait()

    # Only keep non-empty logfiles by renaming them to ${MODULE}.out
    if os.stat(logfile_name)[6]:
        os.rename(logfile_name, "%s/%s.out" % (log_dir, checkfile))
    else:
        os.remove(logfile_name)

        # Update atime, utime
        # This ensures the website will update again in case the build_flag file timestamp was updated during the execution of this script
        os.utime(built_flag, (t_build.st_mtime, t_build.st_mtime))
    if verbose:
        print "Built flag set."



def main():
    (opts, args) = parser.parse_args()

    if not opts.configfile:
        parser.print_usage()
        sys.exit(1)

    update_modules(opts.configfile, opts.verbose)

    if opts.verbose:
        print "Done"


if __name__ == "__main__":
    main()


