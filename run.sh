#!/bin/bash

if [ "$GPG_KEY" ]; then
    sign_arg="-k$GPG_KEY"
else
    sign_arg="--no-sign"
fi

set -x 
cd /package/$PACKAGE_NAME

apt-get update 
mk-build-deps -i -r -t "apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends -y"
gbp buildpackage --git-ignore-branch --git-ignore-new -S "$sign_arg"
dpkg-buildpackage "$sign_arg" -b

# example run: docker run -it --rm -e PACKAGE_NAME=mqtt_bridge -e GPG_KEY=920D962674D20298F82483C72B1C511EE8905F4E -v ~/.gnupg:/root/.gnupg -v `pwd`/..:/package debuild 