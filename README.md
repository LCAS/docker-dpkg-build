# A ROS2 L-CAS GBP builder

## Build the Docker image

`docker build -t builder .`

## example run

create a package directory `package/`, and work entirely in it.

set `GBP_REPO` to the GBP repository (generated from bloom), and set `GBP_TAG` to the respective tag

```
docker run -it --rm -e GBP_REPO=https://github.com/ros2-gbp/common_interfaces-release.git -e GBP_TAG=debian/ros-humble-geometry-msgs_4.2.3-1_jammy -v `pwd`/package:/package builder
```

