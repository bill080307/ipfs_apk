#!/bin/bash

function ui() {
  apt install -y npm
  echo registry=https://registry.npm.taobao.org > ~/.npmrc
  npm install -g npm
  cd ../webui
  npm install
  npm run build
  if [ ! -d "/var/www/ipfsapk/webui" ]; then
    mkdir -p /var/www/ipfsapk/webui
  fi
  cp -r dist/* /var/www/ipfsapk/webui/
  hash=`ipfs add -r --quieter dist`
  cd ../api
  sed -i "s/\"uiTemplate\":.*/\"uiTemplate\": \"$hash\"/g" config.json
}

function admin() {
  apt install -y npm
  echo registry=https://registry.npm.taobao.org > ~/.npmrc
  npm install -g npm
  cd ../admin
  npm install
  npm run build
  if [ ! -d "/var/www/ipfsapk" ]; then
    mkdir -p /var/www/ipfsapk
  fi
  cp -r dist/* /var/www/ipfsapk/
  cd ../api
}

function api() {
  apt install -y python3 python3-pip
  if [ ! -d "~/.pip" ]; then
    mkdir -p ~/.pip
  fi
  echo "[global]" > ~/.pip/pip.conf
  echo "index-url = https://mirrors.aliyun.com/pypi/simple/" >> ~/.pip/pip.conf
  echo "[install]" >> ~/.pip/pip.conf
  echo "trusted-host=mirrors.aliyun.com" >> ~/.pip/pip.conf
  pip3 install -r requirements.txt
  dir=`pwd`
  cp ipfsapk.service /lib/systemd/system/ipfsapk.service
  sed -i "s#ExecStart.*#ExecStart=/usr/bin/python3 "$dir"/admin-api.py#g" /lib/systemd/system/ipfsapk.service
  systemctl enable ipfsapk.service
  systemctl start ipfsapk.service
  cp ipfsapk.conf /etc/nginx/sites-available/ipfsapk
  ln -sf /etc/nginx/sites-available/ipfsapk /etc/nginx/sites-enabled/ipfsapk
  systemctl restart nginx.service
}

apt install -y nginx
if [ -z $1 ]
then
#	ui
#	admin
#	api
echo all
fi
if [ "$1" == "ui" ]
then
	ui
fi
if [ "$1" == "admin" ]
then
	admin
fi
if [ "$1" == "api" ]
then
	api
fi

