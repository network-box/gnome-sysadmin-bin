#!/bin/sh

LOGS_DIR=/var/log/nagios3/archives

# Cleanup older than 5 days nagios logs
find $LOGS_DIR/* -type f -mtime +5 -print0 | xargs -0 -r rm -f
