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

apt-get update 
rosdep update

# hack to avoid conflict
apt-get -y purge python3-rosinstall-generator python3-catkin-pkg python3-rospkg python3-rosdistro

# mkdir -p /tmp/additional_debs
# for url in "$DEB_URLS"; do
#     package_name=`basename $url`
#     while true; do
#         if curl -o /tmp/additional_debs/$package_name $url; then
#             echo "downloaded $url as $package_name"
#             apt-get install -y /tmp/additional_debs/$package_name
#             break
#         else
#             echo "keep waiting for $url to become available"
#             sleep 10
#         fi
#     done
# done
# rm -rf /tmp/additional_debs
export DEB_BUILD_OPTIONS=nocheck

mk-build-deps -i -r -t "apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends -y"
gbp buildpackage --git-ignore-branch --git-ignore-new -S "$sign_arg"
dpkg-buildpackage "$sign_arg" 

# example run: docker run -it --rm -e DEB_URLS="https://lcas.lincoln.ac.uk/repository/repository/misc/debs/melodic/ros-melodic-mqtt-bridge_1.4.1-6bionic_amd64.deb" -e PACKAGE_NAME=mqtt_bridge -e GPG_KEY=920D962674D20298F82483C72B1C511EE8905F4E -v ~/.gnupg:/root/.gnupg -v `pwd`/..:/package debuild 
