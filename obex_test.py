# -*- coding: utf-8 -*-

import sys
from BTPlugin import BTNearbyDevices, obex

nbt = BTNearbyDevices()
obex_service = nbt.service_obextrans('Sauron 400i')

c = obex.BrowserClient(*obex_service)
c.connect()
print(c.listdir())

