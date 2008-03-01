#!/usr/bin/python
#
# This script is called from cron every minute or so. It will read a list
# of modules and check the timestamps for each module. Any modules that
# have commits since their last build will be rebuilt. Rebuilding is just
# a case of spawning a 'svn update' in the right directory, and maybe
# calling a post-update hook script if one exists.
#

import sys
import os
import os.path
import getopt
import ConfigParser
import subprocess
import fcntl

import xml.dom.minidom # to parse svn xml output

timestamp_dir = "/usr/local/www/gnomeweb/timestamps"
hookscripts_dir = "/usr/local/www/gnomeweb/hooks"
checkout_url = "http://svn.gnome.org/svn/%s/trunk" # %s for module name
checkout_basedir = "/usr/local/www/gnomeweb/svn-wd" # default base directory for checkouts
log_dir = "/usr/local/www/gnomeweb/logs"
configfile = ""
verbose = 0
updated = []

FAILURE_MAIL = """Failure updating %(url)s.

Last commit by: %(author)s
ViewCVS: http://svn.gnome.org/viewcvs/%(module)s?rev=%(rev)s&view=rev

Last few lines of output:

%(outputtail)s

Full output can be seen at http://www.gnome.org/updatelogs/%(module)s.out"""




def usage():
    print "usage: " + sys.argv[0] + " [-v] -c <configfile>"
    print "  -v    Be verbose"
    print "  -c    Read list of modules from <configfile>"

try:                                
    opts, args = getopt.getopt(sys.argv[1:], "vc:", ["verbose", "configfile="])
except getopt.GetoptError:
        usage()
        sys.exit()
for opt, arg in opts:
    if opt in ("-c", "--configfile"):
        configfile = arg
    elif opt in ("-v", "--verbose"):
        verbose = 1
if configfile == "":
    usage()
    sys.exit()

def get_svn_info(path):
    xmls = subprocess.Popen(["svn", "info", '--xml', path], stdout=subprocess.PIPE).communicate()[0]
    document = xml.dom.minidom.parseString(xmls)
    
    try: author = document.getElementsByTagName('author')[0].firstChild.nodeValue
    except: author = ""

    try: rev = document.getElementsByTagName('entry')[0].getAttribute('revision')
    except: rev = ""

    return author, rev

cfg = ConfigParser.ConfigParser()
cfg.read([configfile])

for module in cfg.sections():
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

    # Compare timestamps
    if verbose:
        print "Checking '" + module + "'..."
    build_flag = os.path.join(timestamp_dir, module + ".buildflag")
    built_flag = os.path.join(timestamp_dir, module + ".built")
        lock_file  = os.path.join(timestamp_dir, module + '.lock')

    # If the buildflag hasn't been set, ignore this module for now
    if not os.access(build_flag, os.F_OK):
        continue

    # Only need to compare if built flag exists
    if os.access(built_flag, os.F_OK):
                t_built = os.stat(built_flag)
        t_build = os.stat(build_flag)
        if t_build.st_mtime <= t_built.st_mtime:
            # No need to build
            continue

        # Ensure only one copy will be running
        fpl = open(lock_file, 'w')
        try:
            fcntl.flock(fpl, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            if verbose:
                print "Already running"
            continue
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
        retval = os.spawnlp(os.P_WAIT, 'svn', 'svn', 'checkout', '-q', '--non-interactive', checkout_url % module, moduleroot)
    else:
        if verbose:
            print "Running 'svn update " + moduleroot + "'..."
        retval = os.spawnlp(os.P_WAIT, 'svn', 'svn', 'update', '-q', '--non-interactive', moduleroot)
    if retval != 0:
        print "Updating the '" + module + "' site failed"
                fpl.close()
        continue

    # Remember to update the timestamp later
    updated.append(module)

    # We're done if there isn't a post-update hook to run
    hook_file = os.path.join(hookscripts_dir, module)
    if not os.access(hook_file, os.X_OK):
                os.utime(built_flag, (t_build.st_mtime, t_build.st_mtime))
                fpl.close()
        continue

    # Run the hook script and save the stdout+stderr in a logfile
    if verbose:
        print "Running hook script..."
    logfile_name = "%s/%s.out.%s" % (log_dir, module, os.getpid())
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
        os.rename(logfile_name, "%s/%s.out" % (log_dir, module))
    else:
        os.remove(logfile_name)

        # Update atime, utime
        # This ensures the website will update again in case the build_flag file timestamp was updated during the execution of this script
        os.utime(built_flag, (t_build.st_mtime, t_build.st_mtime))
    if verbose:
        print "Built flag set."


if verbose:
    print "Done"

