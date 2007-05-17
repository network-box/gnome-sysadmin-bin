#!/usr/bin/python

import os
import MySQLdb
import email

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

cursor.execute('SELECT id, Status FROM Tickets WHERE Type="ticket" AND Queue=3 AND Status IN ("new", "open", "stalled") ORDER BY id')
tickets = {}
for row in cursor.fetchall():
	tickets[row[0]] = {'Status': row[1]}


cursor.execute("SELECT MAX(Transactions.id) AS TID, Tickets.id AS TID from Tickets INNER JOIN Transactions ON Tickets.id = Transactions.ObjectId where ObjectType = 'RT::Ticket' AND Transactions.Type = 'Comment' and Tickets.Status = 'stalled' GROUP BY Tickets.id;")
trans = dict(cursor.fetchall())

tid = trans.keys()
if len(tid):
    cursor.execute("SELECT TransactionId, Headers FROm Attachments  where  TransactionId IN (%s)" % ",".join([str(t) for t in tid]))
    headers = dict(cursor.fetchall())
else:
    headers = {}

for tid, header in headers.items():
    ticket = trans[int(tid)]

    msg = email.message_from_string(header)
    tickets[ticket]['CC'] = msg['RT-Send-CC']


table = '<table border=1><tr><th>Ticket</th><th>State</th><th>Waiting for</th></tr>%s</table>' % ''.join(['<tr><td><a href="http://www.gnome.org/rt3/Ticket/Display.html?id=%s">%s</a></td><td>%s</td><td>%s</td></tr>' % (ticket, ticket, tickets[ticket]['Status'], tickets[ticket].get('CC', '')) for ticket in sorted(tickets)])

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
