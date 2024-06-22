# -*- encoding: utf-8 -*-

__all__ = [
    'list_devices',
    'BTNearbyDevices',
    'BTSERVICES',
    'BTClient',
]

import sys
import logging
import time
from datetime import datetime

import contribs
import bluetooth

# --------------------------------------------------------------------------

def list_devices() :
    try :
        devices = bluetooth.discover_devices(
            duration = 1,
            lookup_names = True
        )
    except OSError :
        devices = [('OSError','Bluetooth inactive ?')]

    html = ''
    for addr, name in sorted(devices) :
        html = html + '<tr><td>{}</td><td>{}</td></tr>'.format(name, addr)

    return html


# --------------------------------------------------------------------------

# Bluetooth Devices

class BTDevice(object) :

    def __init__(self, addr, name, classe) :
        self._addr = addr
        self._name = name
        self._classe = classe
        self._lastseen = datetime.now()

    @property
    def addr(self) :
        return self._addr
    
    @property
    def name(self) :
        return self._name
    
    @property
    def classe(self) :
        return self._classe

    @property
    def lastseen(self) :
        return self._lastseen

    def __repr__(self) :
        return "{}(addr='{}', name='{}', classe={})".format(
            self.__class__.__name__,
            self._addr, self._name, self._classe
        )

# --------------------------------------------------------------------------

# Bluetooth Services

BTSERVICES = {
    name.replace('_CLASS','') : bluetooth.__dict__.get(name)
    for name in dir(bluetooth)
    if name.endswith('_CLASS')

}
NO_BTSERVICE = '00:00:00:00:00:00', -1

class BTService :

    def __init__(self, host, name, description, port,
                 protocol, rawrecord, service_classes,
                 profiles, provider, service_id, handle) :
        self._host = host
        self._name = (name or b'').decode()
        self._description = description
        self._port = port or float('nan')
        self._protocol = protocol
        self._rawrecord = rawrecord
        self._service_classes = service_classes
        self._profiles = profiles
        self._provider = provider
        self._service_id = service_id
        self._handle = handle

    @property
    def host(self) :
        return self._host
    
    @property
    def name(self) :
        return self._name

    @property
    def port(self) :
        return self._port

    @property
    def protocol(self) :
        return self._protocol

    @property
    def connection(self) :
        return self._host, self._port
        
    def __repr__(self) :
        return (
            f"{self.__class__.__name__}(name='{self.name}', host='{self.host}', " +
            f"port={self.port}, protocol='{self.protocol}')"
        )
        
# --------------------------------------------------------------------------

# Bluetooth Nearby Devices

class BTNearbyDevices(object) :

    def __init__(self) :
        self._devices = []
        self.discover(duration=1)

    def discover(self, duration=8) :
        new_devices = [
            BTDevice(*dev)
            for dev in bluetooth.discover_devices(
                duration=duration,
                lookup_names=True,
                lookup_class=True
            )
        ]

        self._devices = list(
            filter(
                lambda dv : dv.addr not in [ d.addr for d in new_devices ],
                self._devices
            )
        )

        self._devices.extend(new_devices)

    def get_addr_byname(self, name) :
        addr = None
        for dev in self._devices :
            if name == dev.name :
                addr = dev.addr
                break

        return addr

    def browse_services(self, uuid=None) :
        services = dict()
        list_uuid = BTSERVICES.values() if uuid is None else [uuid]
        for dev in self._devices :
            services[dev.name] = [
                BTService(*_serv.values())
                for _uuid in list_uuid
                for _serv in bluetooth.find_service(
                    address=dev.addr,
                    uuid=_uuid
                )
            ]

        return services

    def find_service(self, name, uuid=None) :
        addr = self.get_addr_byname(name)
        if addr is None :
            return NO_BTSERVICE
        services = bluetooth.find_service(
            address=addr,
            uuid=uuid
        )

        if len(services) == 0 :
            return NO_BTSERVICE

        return addr, services[0]['port']

    def service_dialup(self, name) :
        return self.find_service(name, uuid=bluetooth.DIALUP_NET_CLASS)

    def service_serial(self, name) :
        return self.find_service(name, uuid=bluetooth.SERIAL_PORT_CLASS)

    def service_obexpush(self, name) :
        return self.find_service(name, uuid=bluetooth.OBEX_OBJPUSH_CLASS)

    def service_obextrans(self, name) :
        return self.find_service(name, uuid=bluetooth.OBEX_FILETRANS_CLASS)

    @property
    def devices(self) :
        return self._devices

    @property
    def names(self) :
        return [ dev.name for dev in self._devices ]

# --------------------------------------------------------------------------

# Bluetooth Client for RFCOMM Service

class BTClient(object) :

    def __init__(self, service) :
        self._service = service
        self._sock = None

    def connect(self) :
        self._sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self._sock.connect(self._service)
        self._sock.settimeout(1)

    def __enter__(self) :
        self.connect()
        return self

    def __exit__(self, *args) :
        self._sock.close()

    def close(self) :
        self._sock.close()

    def _send(self, message, wait=1) :
        ret = self._sock.send(message + '\r\n')
        logging.debug(f'_send: {message} -> {ret}')
        time.sleep(wait)

    def _recv(self, bufsize=8) :
        response = b''
        while True :
            try :
                chunk = self._sock.recv(bufsize)
                logging.debug(f'_recv: chunk: {len(chunk)} <- {chunk}')
                response += chunk
            except OSError as e :
                break
        logging.debug(f'_recv: {len(response)} <- {response}')
        return response

    def send(self, message, wait=1, bufsize=8) :
        self._send(message, wait)
        resp = self._recv(bufsize)
        return resp

    def ask(self, message, wait=1, bufsize=8, encoding='utf8') :
        print(self.send(message, wait, bufsize).decode(encoding, errors='replace'))


def show_status(bt_client) :
    bt_client.ask('AT+CPMS?')
    bt_client.ask('AT+CMGF?')
    bt_client.ask('AT+CPBS?')
