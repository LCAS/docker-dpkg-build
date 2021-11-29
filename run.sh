#!/bin/bash

cd /package/$PACKAGE_NAME

apt-get update 
mk-build-deps -i -r -t "apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends -y"
gbp buildpackage --git-ignore-branch --git-ignore-new -S --no-sign
dpkg-buildpackage $@
