#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import MySQLdb
import email
import codecs

QUEUES = {
    'accounts': {
        'nr': 3,
        'title': 'Account processing status',
        'desc': 'Status of the accounts queue'
    },
    'membership': {
        'nr': 5,
        'title': 'Membership processing status',
        'desc': 'Status of the Foundation Membership queue'
    },
    'general': {
        'nr': 1,
        'title': 'General support queue processing status',
        'desc': 'Status of the General RT queue'
    },
    'git': {
        'nr': 10,
        'title': 'Git related issues queue processing status',
        'desc': 'Status of the Git RT queue'
    },
    'mailman': {
        'nr': 4,
        'title': 'Mailman related issues queue processing status',
        'desc': 'Status of the Mailman RT queue'
    },
    'planet': {
        'nr': 8,
        'title': 'Planet related issues processing status',
        'desc': 'Status of the Planet RT queue'
    }
}

def write_stat_file(cursor, queue):
    qinfo = QUEUES[queue]
    qnr = qinfo['nr']
    OUTPUT = '/usr/local/www/rt4stats/%s.html' % queue

    cursor.execute ('SELECT COUNT(*) FROM Tickets WHERE Type="ticket" AND Queue=%s AND Status="new"', qnr)
    newc = cursor.fetchone ()[0]

    cursor.execute ('SELECT COUNT(*) FROM Tickets WHERE Type="ticket" AND Queue=%s AND Status="open"', qnr)
    openc = cursor.fetchone ()[0]

    cursor.execute ('SELECT COUNT(*) FROM Tickets WHERE Type="ticket" AND Queue=%s AND Status="stalled"', qnr)
    stalledc = cursor.fetchone ()[0]

    cursor.execute ('SELECT COUNT(*) FROM Tickets WHERE Type="ticket" AND Queue=%s AND (Status="resolved" OR Status="rejected") AND LastUpdated > ADDDATE(CURRENT_DATE, INTERVAL -7 DAY)', qnr)
    last = cursor.fetchone ()[0]

    cursor.execute('SELECT id, Status FROM Tickets WHERE Type="ticket" AND Queue=%s AND Status IN ("new", "open", "stalled") ORDER BY id', qnr)
    tickets = {}
    for row in cursor.fetchall():
        tickets[row[0]] = {'Status': row[1]}

    cursor.execute('SELECT id, Subject FROM Tickets WHERE Type="ticket" AND Queue=%s AND Status IN ("new", "open", "stalled") ORDER BY id', qnr)
    description = {}
    for row in cursor.fetchall():
        description[row[0]] = row[1]

    cursor.execute('SELECT id, LastUpdated FROM Tickets WHERE Type="ticket" AND Queue=%s AND Status IN ("new", "open", "stalled") ORDER BY id', qnr)
    lastupdated = {}
    for row in cursor.fetchall():
        lastupdated[row[0]] = row[1]

    cursor.execute("SELECT MAX(Transactions.id) AS TID, Tickets.id AS TID from Tickets INNER JOIN Transactions ON Tickets.id = Transactions.ObjectId WHERE Tickets.Queue=%s AND ObjectType = 'RT::Ticket' AND Transactions.Type = 'Comment' and Tickets.Status = 'stalled' GROUP BY Tickets.id", qnr)
    trans = dict(cursor.fetchall())

    tid = trans.keys()
    if len(tid):
        cursor.execute("SELECT TransactionId, Headers FROm Attachments  where  TransactionId IN (%s)" % ",".join([str(t) for t in tid]))
        headers = dict(cursor.fetchall())
    else:
        headers = {}

    for tid, header in headers.items():
        ticket = trans[int(tid)]


    table = u'<table border=1><tr><th>Ticket</th><th>State</th><th>Description</th><th>Last updated on</th></tr>%s</table>' % u''.join([u'<tr><td><a href="https://rt.gnome.org/Ticket/Display.html?id=%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (ticket, ticket, tickets[ticket]['Status'], description[ticket], lastupdated[ticket]) for ticket in sorted(tickets)])

    output = codecs.open (OUTPUT, 'w', 'utf-8')

    s = u'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
<head>
  <title>GNOME: %s</title>
  <link rel="icon" type="image/png" href="http://www.gnome.org/img/logo/foot-16.png" />
</head>
<body>
<h1>%s</h1>
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
</html>''' % (qinfo['title'], qinfo['desc'], newc, openc, stalledc, last, table)
    s.encode("utf-8")
    output.write(s)

    output.close ()

if __name__ == "__main__":
    f = open ('/home/admin/secret/rt4stats')
    dbpass = f.readline ().strip ()
    f.close ()

    connection = MySQLdb.connect ('drawable-back', 'rtstats', dbpass, 'rt4', use_unicode=True, charset='UTF8')
    cursor = connection.cursor ()

    for queue in QUEUES.keys():
        write_stat_file(cursor, queue)
