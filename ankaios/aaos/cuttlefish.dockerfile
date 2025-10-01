# This file was created based on the documentation in the following page https://source.android.com/docs/devices/cuttlefish/get-started

# First part: Install Android cuttlefish dependencies

FROM ubuntu:latest

RUN apt update

RUN apt install -y git devscripts equivs config-package-dev debhelper-compat golang curl sudo wget zip

WORKDIR /opt

RUN git clone https://github.com/google/android-cuttlefish

WORKDIR /opt/android-cuttlefish

RUN wget http://security.ubuntu.com/ubuntu/pool/universe/n/ncurses/libtinfo5_6.3-2ubuntu0.1_amd64.deb

RUN apt install ./libtinfo5_6.3-2ubuntu0.1_amd64.deb

RUN tools/buildutils/build_packages.sh

RUN dpkg -i .cuttlefish-base_*_*64.deb || sudo apt-get install -f

RUN dpkg -i .cuttlefish-user_*_*64.deb || sudo apt-get install -f

RUN usermod -aG kvm,cvdnetwork,render $USER

# Second part: Install and run Android cuttlefish

WORKDIR /opt/cf

COPY aosp_cf_x86_64_only_phone-img-13912524.zip cvd-host_package.tar.gz /opt/cf/

RUN unzip ./aosp_cf_x86_64_only_phone-img-13912524.zip

RUN tar -xvf cvd-host_package.tar.gz

RUN ./bin/launch_cvd --daemon
