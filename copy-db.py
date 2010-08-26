#!/usr/bin/env python
# Determine what databases to backup and do it

import os, sys
import re
import subprocess
import MySQLdb
import optparse

parser = optparse.OptionParser()
parser.add_option('-v', '--verbose', action="store_true",
                  help = "Enable verbose output",
                  dest = "verbose",
                  default = False)
parser.add_option('-s', '--secrets-file', action="store",
                  help = "Secrets file containing mysql login (%default)",
                  dest = "secret",
                  default = "/root/.my.cnf")
parser.add_option('-e', '--exclude-file', action="store",
                  help = "File of databases to exclude from backup, one per line (%default)",
                  dest = "exclude",
                  default = "/etc/copy-db.exclude")
parser.add_option('-d', '--backup-dir', action="store",
                  help = "Directory to store backup (%default)",
                  dest = "backup_dir",
                  default = "/var/lib/mysql-backup")

do_verbose = False
(options,args) = parser.parse_args()

do_verbose = options.verbose
secret_file = options.secret
exclude_file = options.exclude
backup_dir = options.backup_dir

def verbose(s):
    if do_verbose:
        print >>sys.stderr, s

# we connect multiple times to avoid leaving an idle connection open
# while we do long dump operations; it might get timed out
def connect_to_db():
    return MySQLdb.connect(host="localhost",
                           user="root",
                           read_default_file=secret_file)

dbs = [] # Databases on the machine, got from MySQL
uidbs = {} # Databases not to be backed up, read from copy-db.exclude

# Get available DBs list
conn = connect_to_db()
conn.set_character_set("utf8")
cursor = conn.cursor()
cursor.execute("SHOW DATABASES")
for fields in cursor.fetchall():
    dbs.append(unicode(fields[0], "utf8"))
cursor.close()
conn.close()

# Get not-to-be-backed-up list
list = open(exclude_file)
for line in list.readlines ():
    if not line.startswith ('#'):
        dbname, who, when = line.strip ().split ()
        uidbs[dbname] = (who, when)

# Spit warnings and remove not-to-be-backed-up databases from the list
for i in uidbs:
    if i not in dbs:
        sys.stderr.write('WARNING: redundant entry for database %s in %s\n\n' % (i, exclude_file))
    else:
        verbose ('database %s not being backed up (request by %s on %s)' % (i, uidbs[i][0], uidbs[i][1]))
        dbs.remove (i)

# Turn a database name into a filename. What we consider
# filename-safe is the same MySQL, but the encoding of non-safe
# characters differs. MySQL has tables for some non-ASCII unicode -
# e.g. U+00C0 LATIN CHARACTER CAPITAL LETTER A WITH ACUTE is @0G
# then it uses @xxxx for the rest. We use @xxxx for everything.
# We don't actually need a match with what MySQL does, just
# something that won't contain meta-characters like '/', but matching
# up for ASCII names like 'db_backup' is slightly useful
def encode_as_filename(s):
    return re.sub('[^A-Za-z0-9]', escape_match, s)

def escape_match(m):
    o = ord(m.group(0))
    if o < 0x10000:
        return "@%04x" % o
    else:
        return "@%04x@%04x" % (0xd800 + (o / 1024), 0xdc00 + (o % 1024))

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

    can_hotcopy = True

    db_filename = encode_as_filename(db)
    if db_filename != db:
        # mysqlhotcopy doesn't understand encoded database names
        can_hotcopy = False

    # Figure out what types of tables the database has
    conn = connect_to_db()
    conn.set_character_set("utf8")
    conn.select_db(db.encode("utf8"))
    cursor = conn.cursor()
    cursor.execute("SHOW TABLE STATUS")
    for fields in cursor.fetchall():
        engine = fields[1]
        if engine != 'MyISAM' and engine != 'ARCHIVE':
            can_hotcopy = False
    cursor.close()
    conn.close()

    if can_hotcopy:
        verbose("Backing up %s via mysqlhotcopy"% db)
        hotcopy = subprocess.Popen(['mysqlhotcopy', '--quiet', '--allowold', db, backup_dir])
        hotcopy.wait()
    else:
        verbose("Backing up %s via mysqldump" % db)
        outfilename = os.path.join(backup_dir, db_filename + ".dump.gz")
        outfilename_tmp = outfilename + ".tmp"
        outfile = open(outfilename_tmp, "w")
        dump = subprocess.Popen(['mysqldump',
                                 '--single-transaction',
                                 '--default-character-set=utf8',
                                 db.encode("utf8")],
                                stdout=subprocess.PIPE)
        gzip = subprocess.Popen(['gzip', '-c'],
                                stdin=dump.stdout, stdout=outfile)
        dump.wait()
        gzip.wait()
        outfile.close()
        if dump.returncode == 0 and gzip.returncode == 0:
            os.rename(outfilename_tmp, outfilename)
        else:
            print >>sys.stderr, "Failed to back up %s, leaving old backup" % db
            os.remove(outfilename_tmp)
