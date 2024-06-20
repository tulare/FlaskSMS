# -*- coding: utf-8 -*-

import sys
import os
import logging
from BTPlugin import BTNearbyDevices, sms
from BTPlugin.sms import SMS


def affichage(messages) :
    for m in messages :
        print('-'*50)
        print(f'{{type}}: {{number}} {{time}} [{{parts}}]\n\n{{text}}\n\n'.format(**m))


logging.basicConfig(level='DEBUG')

nbt = BTNearbyDevices()

telephone = os.environ.get('BT_PHONE')
dialup = nbt.service_dialup(telephone)
serial = nbt.service_serial(telephone)

objSms = SMS(serial)

