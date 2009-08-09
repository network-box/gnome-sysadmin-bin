#!/usr/bin/env python
# Determine what databases to backup and do it

import os, sys
import subprocess

do_verbose = False
for a in sys.argv:
    if a == '--verbose' or a == '-v':
        do_verbose = True

def verbose(s):
    if do_verbose:
        print >>sys.stderr, s

dbs = [] # Databases on the machine, got from MySQL
uidbs = {} # Databases not to be backed up, read from copy-db.exclude

# Get available DBs list
for db in os.popen ('mysqlshow').readlines ()[3:-1]:
    dbs.append (db.replace ('|', ' ').strip ())

# Get not-to-be-backed-up list
list = open ('/etc/copy-db.exclude')
for line in list.readlines ():
    if not line.startswith ('#'):
        dbname, who, when = line.strip ().split ()
        uidbs[dbname] = (who, when)

# Spit warnings and remove not-to-be-backed-up databases from the list
for i in uidbs:
    if i not in dbs:
        sys.stderr.write ('WARNING: redundant entry for database %s in copy-db.exclude\n\n' % i)
    else:
        sys.stdout.write ('WARNING: database %s not being backed up (request by %s on %s)\n\n' % (i, uidbs[i][0], uidbs[i][1]))
        dbs.remove (i)

# Backup!
for db in dbs:
    # mysqlhotcopy only works for MyISAM and ARCHIVE tables. If a database has
    # only tables of those types, then we use mysqlhotcopy.
    #
    # For InnoDB tables we can use mysqldump --single-transaction to get a
    # consistent snapshot of the database.
    #
    # For tables with a mixture of InnoDB and MyISAM tables, neither of the
    # above methods will work and give a consistent snapshot. We could
    # use 'mysqldump --lock-tables', but that would keep the entire database
    # locked for the entire length of the dump. Instead we assume that in
    # this case, the application doesn't care much about the consistentcy
    # of the MyISAM tables and use --single-transaction anyways. (This is the
    # right thing to do for bugzilla where everything but the bugs_fulltext
    # table is InnoDB. bugs_fulltext is just a mirror of the other tables for
    # searching purposes.)
    #
    # Note that mysqlhotcopy is not necessarily faster than mysqldump - the
    # compressed dump will typically be much smaller and faster to write to
    # disk than the copy. The hot copy, on the other hand, may be more rsync
    # friendly when we rsync the databases to the backup machine (This theory
    # is untested.)
    #
    # Future enhancement would be to extent copy-db.exclude to allow specifying
    # per-database backup methods.

    # Figure out what types of tables the database has
    table_status = subprocess.Popen(['mysql', '--batch', '-e', 'show table status', db],
                                    stdout=subprocess.PIPE)
    first = True
    can_hotcopy = True
    for line in table_status.stdout:
        if first: # skip header line
            first = False
            continue
        fields = line.rstrip().split("\t")
        table = fields[0]
        engine = fields[1]
        if engine != 'MyISAM' and engine != 'ARCHIVE':
            can_hotcopy = False
    table_status.stdout.close()
    table_status.wait()

    if can_hotcopy:
        verbose("Backing up %s via mysqlhotcopy"% db)
        hotcopy = subprocess.Popen(['mysqlhotcopy', '--quiet', '--allowold', db, '/var/lib/mysql-backup'])
        hotcopy.wait()
    else:
        verbose("Backing up %s via mysqldump" % db)
        outfilename = os.path.join('/var/lib/mysql-backup/', db + ".dump.gz")
        outfile = open(outfilename, "w")
        dump = subprocess.Popen(['mysqldump', '--single-transaction', db],
                                stdout=subprocess.PIPE)
        gzip = subprocess.Popen(['gzip', '-c'],
                                stdin=dump.stdout, stdout=outfile)
        gzip.wait()
        outfile.close()
