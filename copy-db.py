#!/usr/bin/env python
# Determine what databases to backup and do it

import os, sys

dbs = [] # Databases on the machine, got from MySQL
uidbs = {} # Databases not to be backed up, read from db-list

# Get available DBs list
for db in os.popen ('mysqlshow').readlines ()[3:-1]:
	dbs.append (db.replace ('|', ' ').strip ())

# Get not-to-be-backed-up list
list = open ('/root/bin/db-list')
for line in list.readlines ():
	if not line.startswith ('#'):
		dbname, who, when = line.strip ().split ()
		uidbs[dbname] = (who, when)

# Spit warnings and remove not-to-be-backed-up databases from the list
for i in uidbs:
	if i not in dbs:
		sys.stderr.write ('WARNING: redundant entry for database %s in db-list\n\n' % i)
	else:
		sys.stderr.write ('WARNING: database %s not being backed up (request by %s on %s)\n\n' % (i, uidbs[i][0], uidbs[i][1]))
		dbs.remove (i)

# Backup!
for db in dbs:
	os.system ('mysqlhotcopy --allowold %s /var/lib/mysql-backup' % db)
