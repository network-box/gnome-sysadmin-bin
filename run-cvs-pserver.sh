#!/bin/sh
#
# $Id$
#
# This one is used by container (for r/w pserver) and window (r/o anoncvs)
# where it is copied to /usr/local/bin and referenced from
# /etc/xinetd.d/cvspserver
#

ulimit -d 131072

# We want a $HOME set to "/" so cvs can look there as the user for config files
export HOME="/"
 
exec /usr/bin/cvs \
  --allow-root /cvs/devel    \
  --allow-root /cvs/gnome    \
  --allow-root /cvs/gtk-book \
  --allow-root /cvs/parted   \
  --allow-root /cvs/websites \
  -b /usr/bin pserver
