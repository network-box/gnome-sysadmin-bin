#!/bin/sh

function list_repos() {
    paths=$1
    group=$2
    for p in $paths; do
	for r in $(echo $p/*); do
	    if test -d $r/objects; then
		shortname=${r/\/git\//}
		shortname=${shortname/\/srv\//}
		shortname=${shortname%%.git}
		shortname=${shortname/\/home\//\~}
		url=${shortname}
		test -z "$group" || echo repo.group=$group
		echo repo.url=$url
		echo repo.name=$shortname
		echo repo.desc=$(test -f $r/description && cat $r/description)
		echo repo.path=$r
		echo repo.owner=$(stat -c %U $r)
		echo
	    fi
	done
    done
}

list_repos "/git" "GNOME git repositories"
