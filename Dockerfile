ARG  BASE_IMAGE=ubuntu:jammy

FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get dist-upgrade -y && \
    apt-get autoremove -y && \
    apt-get install -y --no-install-recommends python3-pip lsb-release curl software-properties-common build-essential \
            python3-pygraphviz python3-rosinstall-generator \
            debhelper apt-transport-https curl devscripts equivs git-buildpackage pkg-config && \
    apt-get autoclean

RUN sh -c 'echo "deb http://packages.ros.org/ros2/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list' && \
    curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | apt-key add -

RUN sh -c 'echo "deb https://lcas.lincoln.ac.uk/apt/lcas $(lsb_release -sc) lcas" > /etc/apt/sources.list.d/lcas-latest.list' && \
    sh -c 'echo "deb https://lcas.lincoln.ac.uk/apt/staging $(lsb_release -sc) lcas" > /etc/apt/sources.list.d/lcas-staging.list' && \
    curl -s https://lcas.lincoln.ac.uk/apt/repo_signing.gpg | apt-key add -


    #&& curl -s http://lcas.lincoln.ac.uk/repos/public.key | apt-key add - && sh -c 'echo "deb http://lcas.lincoln.ac.uk/ubuntu/main $(lsb_release -sc) main" > /etc/apt/sources.list.d/lcas-latest.list'

#RUN pip install -U bloom pip install pyyaml==5.1 git+https://github.com/ros-infrastructure/ros_buildfarm.git@3.0.1 aptly-api-client pygithub

ENV ROS_DISTRO=humble
ENV ROS_PYTHON_VERSION=3
ENV ROS_VERSION=2
ENV ROSDISTRO_INDEX_URL=https://raw.github.com/lcas/rosdistro/master/index-v4.yaml

RUN mkdir -p ~/.config/rosdistro && echo "index_url: https://raw.github.com/lcas/rosdistro/master/index-v4.yaml" > ~/.config/rosdistro/config.yaml

RUN mkdir /package

COPY run.sh /run.sh
COPY python/build_chain.py /build_chain.py
RUN chmod u+x /run.sh /build_chain.py

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && pip uninstall -y empy

# invalidate cache to ensure we always have the latest
ADD "https://www.random.org/cgi-bin/randbyte?nbytes=10&format=h" skipcache
RUN rosdep init || true
RUN curl -o /etc/ros/rosdep/sources.list.d/20-default.list https://raw.githubusercontent.com/LCAS/rosdistro/master/rosdep/sources.list.d/20-default.list
RUN curl -o /etc/ros/rosdep/sources.list.d/50-lcas.list https://raw.githubusercontent.com/LCAS/rosdistro/master/rosdep/sources.list.d/50-lcas.list
#RUN apt-get update 
#RUN rosdep update

ENV MAKEOPTS="--jobs 8 --load-average 9"
ENV BLOOM_DONT_ASK_FOR_DOCS=1
ENV BLOOM_DONT_ASK_FOR_SOURCE=1
ENV BLOOM_DONT_ASK_FOR_MAINTENANCE_STATUS=1

# empy is driving me nuts... so apparently we have to install a version <4 to make it work
RUN pip install "empy<4"

CMD ["./run.sh"]
#ENTRYPOINT ["./run.sh"]