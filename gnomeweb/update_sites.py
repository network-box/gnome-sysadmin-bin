#!/usr/bin/python
#
# This script is called from cron every minute or so. It will read a list
# of modules and check the timestamps for each module. Any modules that
# have commits since their last build will be rebuilt. Rebuilding is just
# a case of refreshing the git checkout in the right directory, and maybe
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

sys.path.insert(0, "/home/admin/gitadmin-bin")

from git import *

timestamp_dir = "/usr/local/www/gnomeweb/timestamps"
hookscripts_dir = "/usr/local/www/gnomeweb/hooks"
checkout_url = "git://git.gnome.org/%(module)s"
checkout_basedir = "/var/cache/gnomeweb/git" # default base directory for checkouts
log_dir = "/usr/local/www/gnomeweb/logs"
re_branch_versioned = r'^gnome-([0-9]+)-([0-9]+)$'

FAILURE_MAIL = """Failure updating %(url)s.

Last commit by: %(committer)s
CGIT: http://git.gnome.org/browse/%(module)s/commit/?id=%(rev)s

THE PERSON WHO BREAKS THE BUILD IS RESPONSIBLE TO FIX IT!

Last few lines of output:

%(outputtail)s

Full output can be seen at http://www.gnome.org/updatelogs/%(checkfile)s.out"""


parser = OptionParser()
parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                          help="Be verbose")
parser.add_option("-c", "--config", dest="configfile", metavar="FILE",
                                  help="Read list of modules from FILE")
parser.add_option("-d", "--config-dir", dest="configdir", metavar="DIR",
                                  help="Read *.conf configuration files from DIR")
parser.set_defaults(verbose=False, configfile=None, configdir=None)


def get_git_info(path):
    os.chdir(path)
    committer = git.log("HEAD^!", pretty="format:%cn <%ce>")
    rev = git.rev_parse("HEAD")

    return committer, rev

def update_modules(configfile, configdir, verbose):
    configfiles = []
    if configfile is not None:
        configfiles.append(configfile)
    if configdir is not None and os.path.exists(configdir):
        configfiles.extend(glob.glob(os.path.join(configdir, '*.conf')))

    cfg = ConfigParser.ConfigParser()
    cfg.read(configfiles)

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
            check_branches = cfg.getboolean(module, 'branches')
        else:
            check_branches = False

        checkfile = module
        url = checkout_url % { 'module' : module }

        if check_branches:
            lock = try_lock(checkfile, verbose)
            if not lock:
                continue

            if not update_module_real(moduleroot, url, clone_only=True, verbose=verbose):
                continue

            os.chdir(moduleroot)
            branches = [l.strip()[7:] for l in git.branch('-r', '--no-color', '--no-merged', _split_lines=True) if l.strip().startswith('origin/')]

            for branch in branches:
                b_checkfile = '%s!%s' % (module, branch)
                # Transform gnome-x-y to x.y
                version = re.sub(re_branch_versioned, r'\1.\2', branch)

                b_moduleroot = '%s-%s' % (moduleroot, version)
                b_url = moduleroot
                update_module(module, b_checkfile, b_moduleroot, b_url, owner, branch=branch, 
                              real_remote_url=url, verbose=verbose)
            if lock:
                lock.close()
                lock = None
        else:
            update_module(module, module, moduleroot, url, owner, verbose=verbose)

def try_lock(checkfile, verbose=False):
    lock_file  = os.path.join(timestamp_dir, checkfile + '.lock')
    # Ensure only one copy will be running
    fpl = open(lock_file, 'w')
    try:
        fcntl.flock(fpl, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        if verbose:
            print "Already running"
        return None
    fpl.write("%d" % os.getpid())
    fpl.flush()
    if verbose:
        print "Wrote PID to lock file (PID: %d)" % os.getpid()

    return fpl

def update_module_real(moduleroot, url, branch='master', clone_only=False, verbose=False):
    # Get the latest git contents
    try:
        retval = 0
        if not os.path.exists(moduleroot):
            # Path does not exist.. so check it out of GIT
            if verbose:
                print "Running 'git clone' to create " + moduleroot
            git.clone(url, moduleroot)
            os.chdir(moduleroot)
            if branch != 'master':
                if verbose:
                    print "Running git checkout -b", branch, "origin/" + branch
                git.checkout('-b', branch, 'origin/' + branch)
        elif clone_only:
            pass
        else:
            if not os.path.exists(os.path.join(moduleroot, ".git")):
                print "%s exists and is not a git clone" % moduleroot
                return False
            os.chdir(moduleroot)
            if verbose:
                print "Running 'git fetch' to update " + moduleroot
            git.fetch('--all', "origin")
            if verbose:
                print "Resetting to latest content"
            git.reset('origin/' + branch, hard=True)
    except CalledProcessError, e:
        print str(e)
        return False

    return True


def update_module(module, checkfile, moduleroot, url, owner, branch='master', verbose=False, real_remote_url=None):
    # Compare timestamps
    if verbose:
        print "Checking '" + module + "'..."
    build_flag = os.path.join(timestamp_dir, checkfile + ".buildflag")
    built_flag = os.path.join(timestamp_dir, checkfile + ".built")

    # Built before?
    t_build = None
    if os.access(built_flag, os.F_OK):
        if not os.access(build_flag, os.F_OK):
            # If the buildflag hasn't been set, it likely means the module was
            # built once and hasn't yet been updated since that time
            return False

        # Built and build files exist, so check if module needs to be rebuild
        t_build = os.stat(build_flag)
        t_built = os.stat(built_flag)
        if t_build.st_mtime <= t_built.st_mtime:
            # No need to build
            return False
    # If we get here, the module has either not been built before, or we're building again


    lock = try_lock(checkfile, verbose)
    if lock is None:
        return False
    if t_build is None:
        t_build = os.stat(lock.name)


    if real_remote_url is not None:
        # This git module is hard linked to another git module
        # Update the original module first, then update this module
        if not update_module_real(url, real_remote_url, verbose=verbose):
            return False
        if branch != 'master' and not os.path.exists(os.path.join(moduleroot, ".git")):
            try:
                os.chdir(url)
                git.branch(branch, 'origin/%s' % branch)
            except CalledProcessError, e:
                # local branch probably exists already
                pass

    if not update_module_real(moduleroot, url, branch, verbose=verbose):
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
    if retval != 0:
        # Generate contents of the mail
        committer, rev = get_git_info(moduleroot)
        outputtail = subprocess.Popen(["tail", "-n30", logfile_name], stdout=subprocess.PIPE).communicate()[0]
        mailmessage = FAILURE_MAIL % locals()
        
        # Send the mail
        cmd = ['mail', '-s', "Failure updating %s" % url, committer]
        if owner:
            cmd.append(owner)
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
    if not os.path.isfile(built_flag):
        f = open(built_flag, 'w')
        f.close()
    os.utime(built_flag, (t_build.st_mtime, t_build.st_mtime))
    if verbose:
        print "Built flag set."



def main():
    (opts, args) = parser.parse_args()

    if not opts.configfile and not opts.configdir:
        parser.print_usage()
        sys.exit(1)

    update_modules(opts.configfile, opts.configdir, opts.verbose)

    if opts.verbose:
        print "Done"


if __name__ == "__main__":
    os.nice(19)
    main()


