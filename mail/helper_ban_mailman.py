#!/usr/bin/python

import sys
sys.path.append('$MAILMAN_BIN')

def add_banned(mlist, address):
	if not mlist.Locked():
		mlist.Lock()
	if address not in mlist.ban_list:
		mlist.ban_list.append(address)
	mlist.Save()
	mlist.Unlock()
