#!/usr/bin/perl -w
#
# ciabot -- Mail a git log message to a given address, for the purposes of CIA
#
# Loosely based on cvslog by Russ Allbery &lt;rra@stanford.edu&gt;
# Copyright 1998  Board of Trustees, Leland Stanford Jr. University
#
# Copyright 2001, 2003, 2004, 2005  Petr Baudis &lt;pasky@ucw.cz&gt;
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2, as published by the
# Free Software Foundation.
#
# The master location of this file is in the Cogito repository
# (see http://www.kernel.org/git/).
#
# This program is designed to run as the .git/hooks/post-commit hook. It takes
# the commit information, massages it and mails it to the address given below.
#
# The calling convention of the post-commit hook is:
#
#	.git/hooks/post-commit $commit_sha1 $branch_name
#
# If it does not work, try to disable $xml_rpc in the configuration section
# below. Also, remember to make the hook file executable.
#
#
# Note that you can (and it might be actually more desirable) also use this
# script as the GIT update hook:
#
#	refname=${1#refs/heads/}
#	[ "$refname" = "master" ] &amp;&amp; refname=
#	oldhead=$2
#	newhead=$3
#	for merged in $(git-rev-list $newhead ^$oldhead | tac); do
#		/path/to/<b style="color: black; background-color: rgb(255, 255, 102);">ciabot.pl</b> $merged $refname
#	done
#
# This is useful when you use a remote repository that you only push to. The
# update hook will be triggered each time you push into that repository, and
# the pushed commits will be reported through CIA.

use strict;
use vars qw ($project $from_email $dest_email $noisy $rpc_uri $sendmail
		$xml_rpc $ignore_regexp $alt_local_message_target);




### Configuration

# Project name (as known to CIA).
$project = 'GNOME';

# The from address in generated mails.
# (Not sure if this has to be specifically svnmaster@gnome.org to use
# our existing config or whether we could change it. It probably could
# be changed.)
$from_email = 'svnmaster@gnome.org';

# Mail all reports to this address.
$dest_email = 'cia@cia.vc';

# If using XML-RPC, connect to this URI.
$rpc_uri = 'http://cia.vc/RPC2';

# Path to your USCD sendmail compatible binary (your mailer daemon created this
# program somewhere).
$sendmail = '/usr/sbin/sendmail';

# If set, the script will send CIA the full commit message. If unset, only the
# first line of the commit message will be sent.
$noisy = 0;

# This script can communicate with CIA either by mail or by an XML-RPC
# interface. The XML-RPC interface is faster and more efficient, however you
# need to have RPC::XML perl module installed, and some large CVS hosting sites
# (like Savannah or Sourceforge) might not allow outgoing HTTP connections
# while they allow outgoing mail. Also, this script will hang and eventually
# not deliver the event at all if CIA server happens to be down, which is
# unfortunately not an uncommon condition.
$xml_rpc = 0;

# This variable should contain a regexp, against which each file will be
# checked, and if the regexp is matched, the file is ignored. This can be
# useful if you do not want auto-updated files, such as e.g. ChangeLog, to
# appear via CIA.
#
# The following example will make the script ignore all changes in two specific
# files in two different modules, and everything concerning module 'admin':
#
# $ignore_regexp = "^(gentoo/Manifest|elinks/src/bfu/inphist.c|admin/)";
$ignore_regexp = "";

# It can be useful to also grab the generated XML message by some other
# programs and e.g. autogenerate some content based on it. Here you can specify
# a file to which it will be appended.
$alt_local_message_target = "";




### The code itself

use vars qw ($commit $tree @parent $author $committer);
use vars qw ($user $branch $rev @files $logmsg $message);
my $line;



### Input data loading


# The commit stuff
$commit = $ARGV[0];
$branch = $ARGV[1];

open COMMIT, "git-cat-file commit $commit|" or die "git-cat-file commit $commit: $!";
my $state = 0;
$logmsg = '';
while (defined ($line = &lt;COMMIT&gt;)) {
  if ($state == 1) {
    $logmsg .= $line;
    $noisy or $state++;
    next;
  } elsif ($state &gt; 1) {
    next;
  }

  chomp $line;
  unless ($line) {
    $state = 1;
    next;
  }

  my ($key, $value) = split(/ /, $line, 2);
  if ($key eq 'tree') {
    $tree = $value;
  } elsif ($key eq 'parent') {
    push(@parent, $value);
  } elsif ($key eq 'author') {
    $author = $value;
  } elsif ($key eq 'committer') {
    $committer = $value;
  }
}
close COMMIT;


open DIFF, "git-diff-tree -r $parent[0] $tree|" or die "git-diff-tree $parent[0] $tree: $!";
while (defined ($line = &lt;DIFF&gt;)) {
  chomp $line;
  my @f;
  (undef, @f) = split(/\t/, $line, 2);
  push (@files, @f);
}
close DIFF;


# Figure out who is doing the update.
# XXX: Too trivial this way?
($user) = $author =~ /&lt;(.*?)@/;


$rev = substr($commit, 0, 12);




### Remove to-be-ignored files

@files = grep { $_ !~ m/$ignore_regexp/; } @files
  if ($ignore_regexp);
exit unless @files;



### Compose the mail message


my ($VERSION) = '1.0';
my $ts = time;

$message = &lt;&lt;EM
&lt;message&gt;
   &lt;generator&gt;
       &lt;name&gt;CIA Perl client for Git&lt;/name&gt;
       &lt;version&gt;$VERSION&lt;/version&gt;
   &lt;/generator&gt;
   &lt;source&gt;
       &lt;project&gt;$project&lt;/project&gt;
EM
;
$message .= "       &lt;branch&gt;$branch&lt;/branch&gt;" if ($branch);
$message .= &lt;&lt;EM
   &lt;/source&gt;
   &lt;timestamp&gt;
       $ts
   &lt;/timestamp&gt;
   &lt;body&gt;
       &lt;commit&gt;
           &lt;author&gt;$user&lt;/author&gt;
           &lt;revision&gt;$rev&lt;/revision&gt;
           &lt;files&gt;
EM
;

foreach (@files) {
  s/&amp;/&amp;amp;/g;
  s/&lt;/&amp;lt;/g;
  s/&gt;/&amp;gt;/g;
  $message .= "  &lt;file&gt;$_&lt;/file&gt;\n";
}

$logmsg =~ s/&amp;/&amp;amp;/g;
$logmsg =~ s/&lt;/&amp;lt;/g;
$logmsg =~ s/&gt;/&amp;gt;/g;

$message .= &lt;&lt;EM
           &lt;/files&gt;
           &lt;log&gt;
$logmsg
           &lt;/log&gt;
       &lt;/commit&gt;
   &lt;/body&gt;
&lt;/message&gt;
EM
;



### Write the message to an alt-target

if ($alt_local_message_target and open (ALT, "&gt;&gt;$alt_local_message_target")) {
  print ALT $message;
  close ALT;
}



### Send out the XML-RPC message


if ($xml_rpc) {
  # We gotta be careful from now on. We silence all the warnings because
  # RPC::XML code is crappy and works with undefs etc.
  $^W = 0;
  $RPC::XML::ERROR if (0); # silence perl's compile-time warning

  require RPC::XML;
  require RPC::XML::Client;

  my $rpc_client = new RPC::XML::Client $rpc_uri;
  my $rpc_request = RPC::XML::request-&gt;new('hub.deliver', $message);
  my $rpc_response = $rpc_client-&gt;send_request($rpc_request);

  unless (ref $rpc_response) {
    die "XML-RPC Error: $RPC::XML::ERROR\n";
  }
  exit;
}



### Send out the mail


# Open our mail program

open (MAIL, "| $sendmail -t -oi -oem") or die "Cannot execute $sendmail : " . ($?&gt;&gt;8);


# The mail header

print MAIL &lt;&lt;EOM;
From: $from_email
To: $dest_email
Content-type: text/xml
Subject: DeliverXML

EOM

print MAIL $message;


# Close the mail

close MAIL;
die "$0: sendmail exit status " . ($? &gt;&gt; 8) . "\n" unless ($? == 0);

# vi: set sw=2:
