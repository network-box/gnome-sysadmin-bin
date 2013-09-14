#!/usr/bin/python

import MySQLdb
from time import gmtime, strftime

file = open('/home/admin/secret/mango','r')
lines = file.readlines()

for line in lines:
    if line.find("mysql_password") > -1:
        dirty_password = line.split()
        mirrors_password = str(dirty_password)

        sanitize_file=["\'","(",")","mysql_password","=","[","]","\"",";"]
        for i in range(len(sanitize_file)):
            mirrors_password = mirrors_password.replace(sanitize_file[i],"")
file.close()

db = MySQLdb.connect(host="drawable-back",
                     user="mirrors",
                     passwd=mirrors_password,
                     db="mirrors")
cur = db.cursor()

continents_list = ['Europe', 'Asia', 'South America', 'United States and Canada', 'Australia', 'Other']
time = strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime())

f = open ('/ftp/pub/GNOME/MIRRORS', 'w' )
f.write('GNOME HTTP and FTP mirrors list' + '\n')

for location in continents_list:
    f.write('\n' + location + '\n')

    cur.execute("select url from ftpmirrors where location = '%s' and active = '1'" % location)
    result = cur.fetchall()

    if not result:
        f.write('\n' + '\t' + "No available mirrors for this country / continent as of now.")
    else:
        for i in result:
            f.write('\n' + '\t' + (str(i[0])))
    f.write('\n')

f.write('\n')
f.write('------------------------------------------------------------' + '\n')
f.write('Maintained by the Gnome Systems Administration Team <gnome-sysadmin@gnome.org>' + '\n')
f.write('Last updated: %s' % time + '\n')
f.close()
