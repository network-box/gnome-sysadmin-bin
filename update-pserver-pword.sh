#!/bin/sh

LIVEFILE=/cvs/gnome/CVSROOT/passwd
TMPFILE=/tmp/cvspword.$$
PATCHFILE=/tmp/cvspword.diff.$$

echo "anoncvs::gnomecvs" >$TMPFILE
/home/admin/bin/update-pserver-pword >>$TMPFILE

# Check for differences
diff $LIVEFILE $TMPFILE > $PATCHFILE
patchlength=`cat $PATCHFILE | wc -l`

# If no differences, our work is done
if [ $patchlength -eq 0 ]; then
	#echo "No changes";
	exit 0;
fi

# If differences are extreme, dump the TMPFILE with an error message
if [ $patchlength -gt 50 ]; then
	echo "Generated password file radically different to existing one."
	exit 1;
fi

# Basic checks complete, instate new file
cat $TMPFILE > $LIVEFILE

# Report changes to sysadmin
cat $PATCHFILE

# Tidyup
rm -f $TMPFILE
