#!/usr/bin/python

import os
import MySQLdb

f = open ('/home/admin/secret/rt3stats')
dbpass = f.readline ().strip ()
f.close ()

connection = MySQLdb.connect ('button-back', 'rtstats', dbpass, 'rt3')
cursor = connection.cursor ()

cursor.execute ('SELECT COUNT(*) FROM Tickets WHERE Type="ticket" AND Queue=3 AND Status="new"')
newc = cursor.fetchone ()[0]

cursor.execute ('SELECT COUNT(*) FROM Tickets WHERE Type="ticket" AND Queue=3 AND Status="open"')
openc = cursor.fetchone ()[0]

cursor.execute ('SELECT COUNT(*) FROM Tickets WHERE Type="ticket" AND Queue=3 AND Status="stalled"')
stalledc = cursor.fetchone ()[0]

cursor.execute ('SELECT COUNT(*) FROM Tickets WHERE Type="ticket" AND Queue=3 AND (Status="resolved" OR Status="rejected") AND LastUpdated > ADDDATE(CURRENT_DATE, INTERVAL -7 DAY)')
last = cursor.fetchone ()[0]

cursor.execute('SELECT id, Status FROM Tickets WHERE Type="ticket" AND Queue=3 AND Status IN ("new" "open", "stalled")')
tickets = cursor.fetchall()

table = '<table><tr><th>Ticket</th><th>State</th></tr>%s</table>' % ''.join(['<tr><td>%s</td><td>%s</td></tr>' % a, b for a, b in tickets])

OUTPUT = '/home/users/gpastore/public_html/stats/accounts.html'

os.remove (OUTPUT) 
output = open (OUTPUT, 'a')

output.write ('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
<head>
  <title>GNOME: Account processing status</title>
  <link rel="icon" type="image/png" href="http://www.gnome.org/img/logo/foot-16.png" />
</head>
<body>
<h1>Status of the accounts queue</h1>
<p>
  <ul>
    <li>Tickets awaiting processing: %d</li>
    <li>Tickets being processed: %d</li>
    <li>Tickets awaiting requestor reply: %d</li>
    <li>Tickets closed in the last 7 days: %d</li>
  </ul>
</p>
%s
</body>
</html>''' % (newc, openc, stalledc, last, table))

output.close ()
