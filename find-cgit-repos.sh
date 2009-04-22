#!/bin/sh

# This script should be run with the output written to /git/cgit.repositories, which
# is included from /etc/cgitrc

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

		if test -f $r/pending ; then
		    pending="[PENDING] "
		else
		    pending=""
		fi

		desc=""

		if ! cmp $r/description /git/empty-description 2>/dev/null ; then
		    desc=$(test -f $r/description && cat $r/description)
		fi

		if test -z "$desc"; then
		    desc="Please create $shortname.doap (see http://live.gnome.org/Git/FAQ)"
		fi

		test -z "$group" || echo repo.group=$group
		echo repo.url=$url
		echo repo.name=$shortname
		echo repo.desc=$pending$desc
		echo repo.path=$r
		echo
	    fi
	done
    done
}

list_repos "/git" "GNOME git repositories"
list_repos "/git/preview" "Git conversion preview repositories"
