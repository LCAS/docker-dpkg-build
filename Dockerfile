ARG  BASE_IMAGE=ubuntu:bionic

FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y lsb-release curl software-properties-common build-essential debhelper apt-transport-https curl devscripts equivs git-buildpackage && \
    apt-get clean

RUN sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list' && \
    apt-key adv --keyserver 'hkp://keyserver.ubuntu.com:80' --recv-key C1CF6E31E6BADE8868B172B4F42ED6FBAB17C654 && \
    curl -s http://lcas.lincoln.ac.uk/repos/public.key | apt-key add - && sh -c 'echo "deb http://lcas.lincoln.ac.uk/ubuntu/main $(lsb_release -sc) main" > /etc/apt/sources.list.d/lcas-latest.list'

RUN apt-get update 
#RUN apt-get install -y python-rosdep 
#RUN rosdep init
#RUN curl -o /etc/ros/rosdep/sources.list.d/20-default.list https://raw.githubusercontent.com/LCAS/rosdistro/master/rosdep/sources.list.d/20-default.list
#RUN curl -o /etc/ros/rosdep/sources.list.d/50-lcas.list https://raw.githubusercontent.com/LCAS/rosdistro/master/rosdep/sources.list.d/50-lcas.list
#RUN mkdir -p ~/.config/rosdistro && echo "index_url: https://raw.github.com/lcas/rosdistro/master/index-v4.yaml" > ~/.config/rosdistro/config.yaml
#RUN rosdep update

RUN mkdir /package

COPY run.sh /run.sh
RUN chmod u+x /run.sh

CMD [""]
ENTRYPOINT ["./run.sh"]