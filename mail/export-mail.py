#!/usr/bin/python

import ldap
import ldap.modlist
import ldap.filter
import subprocess

LDAP_URL='ldap://ldap-back/'
LDAP_BINDDN='cn=Manager,dc=gnome,dc=org'
LDAP_GROUP_BASE='ou=groups,dc=gnome,dc=org'
LDAP_USER_BASE='ou=people,dc=gnome,dc=org'

ALIASES = [
    ('/etc/gnome.org/cvs-mail/virtual',    'cvs.gnome.org', 'gnomecvs'),
    ('/etc/gnome.org/svn-mail/virtual',    'svn.gnome.org', 'gnomecvs'),
    ('/etc/gnome.org/src-mail/virtual',    'src.gnome.org', 'gnomecvs'),
    ('/etc/gnome.org/master-mail/aliases', '', 'mailusers'),
]

_cache_email = {}
def fetch_email_addresses(members):
    unknown_emails = members.difference(_cache_email.keys())

    if len(unknown_emails):
        format = '(uid=%s)' * len(unknown_emails)
        filter = '(|%s)' % ldap.filter.filter_format(format, list(unknown_emails))
        results = l.search_s(LDAP_USER_BASE, ldap.SCOPE_SUBTREE, filter, ('uid', 'mail'))
        for entry in results:
            id = entry[0]
            attr = entry[1]
            if 'mail' not in attr:
                continue

            _cache_email[attr['uid'][0]] = attr['mail'][0]

    return [(uid, _cache_email[uid]) for uid in sorted(members) if uid in _cache_email]

_cache_group = {}
def fetch_group_members(group):
    if group in _cache_group:
        return _cache_group[group]

    filter = ldap.filter.filter_format('(&(objectClass=posixGroup)(cn=%s))', (group, ))
    results = l.search_s(LDAP_GROUP_BASE, ldap.SCOPE_SUBTREE, filter, ('memberUid', ))

    members = set()
    for entry in results:
        id = entry[0]
        attr = entry[1]

        members.update(attr['memberUid'])

    _cache_group[group] = members
    return members


if __name__ == '__main__':
    global l
    l = ldap.initialize(LDAP_URL)
    l.protocol_version = ldap.VERSION3

    for aliasfile, domain, group in ALIASES:
        newaliasfile = '%s.new2' % aliasfile
        members = fetch_group_members(group)
        emails = fetch_email_addresses(members)

        if domain == "":
            file_format = "%s%s:\t\t%s\n"
        else:
            file_format = "%s%s %s\n"
            if not domain.startswith("@"):
                domain = "@" + domain

        f = file(newaliasfile, 'w')
        f.write("# WARNING: Do not edit this file directly. Users who should have\n")
        f.write("#          aliases should be added to the %s group\n\n" % group)
        f.writelines((file_format % (uid, domain, mail) for uid, mail in emails))
        f.close()

        p = subprocess.Popen(['/usr/bin/diff', '-U0', '--', aliasfile, newaliasfile], stdout=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
        if p.returncode != 0:
            print stdout
            print
            print
            subprocess.call(['/bin/mv', '-f', '--', newaliasfile, aliasfile])
            if domain == '':
                subprocess.call(['/usr/sbin/postalias', '-w', aliasfile])
            else:
                subprocess.call(['/usr/sbin/postmap', 'hash:%s' % aliasfile])
            subprocess.call(['/usr/sbin/postfix', 'reload']);


    l.unbind_s()

