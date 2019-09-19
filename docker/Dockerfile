FROM ubuntu:bionic

WORKDIR /work

ENV DEBIAN_FRONTEND=noninteractive

RUN \
  apt-get update && \
  apt-get -y install \
    git \
    build-essential \
    ca-certificates \
    sudo \
    software-properties-common \
    tox \
    tzdata \
    locales \
    vim

RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen

ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8    

ADD . /piksi_tools

RUN make -C /piksi_tools deps
