#!/bin/bash

if [ "$GPG_KEY" ]; then
    sign_arg="-k$GPG_KEY"
else
    sign_arg="--no-sign"
fi

set -x 
cd /package
mkdir -p gbp
git clone  ${GBP_REPO} gbp/
cd gbp
git checkout ${GBP_TAG}

apt-get update && apt-get dist-upgrade -y && apt-get autoremove -y && apt-get autoclean 
rosdep update

export DEB_BUILD_OPTIONS=nocheck

mk-build-deps -i -r -t "apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends -y"
gbp buildpackage --git-ignore-branch --git-ignore-new -S "$sign_arg"
dpkg-buildpackage "$sign_arg" 

# example run: docker run -it --rm -e DEB_URLS="https://lcas.lincoln.ac.uk/repository/repository/misc/debs/melodic/ros-melodic-mqtt-bridge_1.4.1-6bionic_amd64.deb" -e PACKAGE_NAME=mqtt_bridge -e GPG_KEY=920D962674D20298F82483C72B1C511EE8905F4E -v ~/.gnupg:/root/.gnupg -v `pwd`/..:/package debuild 
