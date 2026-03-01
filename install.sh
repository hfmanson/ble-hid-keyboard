#! /bin/bash
set -x
mkdir -p /usr/local/lib/ble-hid-keyboard

cp gatt_server.py /usr/local/lib/ble-hid-keyboard
cp requirements.txt /usr/local/lib/ble-hid-keyboard
cp -r core /usr/local/lib/ble-hid-keyboard/core

python3 -m venv /usr/local/lib/ble-hid-keyboard/venv
. /usr/local/lib/ble-hid-keyboard/venv/bin/activate
pip3 install -r requirements.txt
deactivate

cp service/bluetooth-init.sh /usr/local/lib/ble-hid-keyboard
cp service/ble-hid-keyboard.service /usr/lib/systemd/system

systemctl enable ble-hid-keyboard.service
systemctl start ble-hid-keyboard.service