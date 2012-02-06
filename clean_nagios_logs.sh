#!/bin/sh

LOGS_DIR=/var/log/nagios3/archives

# Cleanup older than 5 days nagios logs
find $LOGS_DIR/* -mtime +5 -exec rm {} \;

