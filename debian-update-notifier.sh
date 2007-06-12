#!/bin/bash

aptitude update > /dev/null

t=`aptitude -F %p search ~U`
if [[ "$t" =~ '[[:alpha:]]' ]]; then
    echo "Updates available for the following package(s) are available:"
    echo $t
fi
