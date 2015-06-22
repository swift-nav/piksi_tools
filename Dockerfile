FROM ubuntu:trusty

WORKDIR /app

RUN apt-get update && apt-get -y --force-yes install \
  git \
  build-essential \
  python \
  python-setuptools \
  python-pip \
  python-virtualenv \
  swig

RUN pip install \
  'pip>=1.5.6' \
  'setuptools>=5.3'

RUN apt-get update && apt-get -y --force-yes install \
  libicu-dev \
  libqt4-scripttools \
  python-enable \
  python-chaco \
  python-vtk \
  python-wxgtk2.8 \
  python-pyside \
  python-qt4-dev \
  python-sip \
  python-qt4-gl \
  python-software-properties

RUN pip install \
  traits \
  traitsui \
  pyserial \
  pylibftdi \
  'pyparsing==1.5.7' \
  pygments \
  intelhex \
  six \
  construct \
  sbp==0.29

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app
RUN python setup.py install

CMD python piksi_tools/console/console.py
