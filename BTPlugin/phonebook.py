# -*- encoding: utf-8 -*-

import re
import csv
from collections import namedtuple

# Bluetooth access to PhoneBook

PhoneBookEntry = namedtuple('PhoneBookEntry', ['index', 'number', 'numtype', 'label', 'flag'])

def pbStorage(bt_client, storage=None) :

    # select storage before requesting properties
    if storage is not None :
        at_command = 'AT+CPBS="{}"'.format(storage)
        bt_client.send(at_command)

    at_command = 'AT+CPBS?'
    response = bt_client.send(at_command)

    storage_records = re.findall('\+CPBS:(.+)\r\n', response.decode())
    storage_list = [
        entry
        for entry in csv.reader(storage_records)
    ]

    return storage_list

def pbRead(bt_client, start_index=1, stop_index=None, storage=None) :

    # choisir le storage du phonebook
    # "SM" = Carte SIM, "ME" = mémoire du téléphone
    storage_list = pbStorage(bt_client, storage=storage)

    if stop_index is None :
        stop_index = start_index

    if stop_index == -1 :
        stop_index = storage_list[0][2]

    at_command = 'AT+CPBR={},{}'.format(start_index, stop_index)
    response = bt_client.send(at_command)

    phonebook_records = re.findall('\+CPBR:\s+(.+)\r\n', response.decode())

    phonebook_list = [
        PhoneBookEntry(*entry)
        for entry in csv.reader(phonebook_records)
    ]

    return phonebook_list


def pbAdd(bt_client, phonebook_entry) :
    at_command = 'AT+CPBW=,"{r.number}",{r.numtype},"{r.label}",{r.flag}'.format(
        r=phonebook_entry
    )
    response = bt_client.send(at_command)
    
    return response.decode()

def pbUpdate(bt_client, phonebook_entry) :
    at_command = 'AT+CPBW={r.index},"{r.number}",{r.numtype},"{r.label}",{r.flag}'.format(
        r=phonebook_entry
    )
    response = bt_client.send(at_command)

    return response.decode()
