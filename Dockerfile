FROM ubuntu:bionic

ENV DEBIAN_FRONTEND=noninteractive
ENV ETS_TOOLKIT=qt4

WORKDIR /app

RUN apt-get update && apt-get -y install \
  git \
  build-essential \
  python \
  python-setuptools \
  python-pip \
  python-virtualenv \
  swig \
  libicu-dev \
  python-enable \
  python-chaco \
  python-vtk6 \
  python-wxgtk3.0 \
  python-pyside \
  python-sip \
  libpythonqt-qt5-python2-dev

RUN pip install \
  'pip>=1.5.6' \
  'setuptools>=5.3' \
  traits \
  traitsui \
  pyserial \
  pylibftdi \
  'pyparsing==1.5.7' \
  pygments \
  intelhex \
  kiwisolver \
  six \
  construct \
  sbp==0.29

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app
RUN python setup.py install

CMD python piksi_tools/console/console.py
