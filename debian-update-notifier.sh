#!/bin/bash

aptitude update > /dev/null

t=`aptitude -F %p search ~U`
if [[ "$t" =~ '[[:alpha:]]' ]]; then
        echo $t
fi
