# -*- encoding: utf-8 -*-

__all__ = [
    'send_sms', 'send_sms_pdu',
    'get_sms',
    'store_sms', 'store_draft_sms',
    'send_from_storage',
    'delete_sms'
]

import re
from .pdu import decodeSmsPdu, encodeSmsSubmitPdu 

# Bluetooth for sending SMS

def send_sms(bt_client, numero, message) :
    # passer en mode texte
    bt_client.send('AT+CMGF=1', wait=0.5)

    # envoi direct du sms
    bt_client.send('AT+CMGS="{}"'.format(numero))
    response = bt_client.send('{}{}'.format(message, '\x1a'), wait=2)

    # revenir au mode binaire PDU
    bt_client.send('AT+CMGF=0', wait=0.5)

    return response

def send_sms_pdu(bt_client, numero, message) :
    # s'assurer du mode binaire PDU
    bt_client.send('AT+CMGF=0', wait=0.5)

    # composition du SMS
    smspdu = encodeSmsSubmitPdu(
        number=numero,
        text=message,
        requestStatusReport=False
    )

    # envoi du sms par morceaux
    responses = []
    for _sms in smspdu :
        bt_client.send('AT+CMGS={}'.format(_sms.tpduLength))
        response = bt_client.send('{}{}'.format(_sms, '\x1a'), wait=2)
        responses.append(response.decode())

    return responses


def get_sms(bt_client, index, storage="SM") :
    # passer en mode binaire PDU
    bt_client.send('AT+CMGF=0', wait=0.2)

    # sélectionner le storage "SM" ou "ME"
    if storage == "ME" :
        bt_client.send('AT+CPMS="ME"', wait=0.2)
    else :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    response = bt_client.send('AT+CMGR={}'.format(int(index)), wait=0.5)
    pdu_records = re.findall('\+CMGR:.+\r\n(.+)\r\n', response.decode())
    liste_sms = []
    for smspdu in pdu_records :
        _sms = decodeSmsPdu(smspdu)
        liste_sms.append(_sms)

    # revenir au storage "SM"
    if storage == "ME" :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    return liste_sms


def store_sms(bt_client, numero, message, storage="SM") :
    # passer en mode texte
    bt_client.send('AT+CMGF=1', wait=0.2)

    # sélectionner le storage "SM" ou "ME"
    if storage == "ME" :
        bt_client.send('AT+CPMS="SM","ME"', wait=0.2)
    else :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    # stockage du sms en mémoire
    bt_client.send('AT+CMGW="{}",,"REC UNREAD"'.format(numero))
    response = bt_client.send('{}{}'.format(message, '\x1a'))

    # revenir au mode binaire PDU
    bt_client.send('AT+CMGF=0', wait=0.2)

    # revenir au storage "SM"
    if storage == "ME" :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    slot = re.findall('\+CMGW:(\w+)', response.decode())
    return slot

def store_draft_sms(bt_client, numero, message, storage="SM") :
    # passer en mode texte
    bt_client.send('AT+CMGF=1', wait=0.2)

    # sélectionner le storage "SM" ou "ME"
    if storage == "ME" :
        bt_client.send('AT+CPMS="SM","ME"', wait=0.2)
    else :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    # stockage du sms en mémoire
    bt_client.send('AT+CMGW="{}",,"STO UNSENT"'.format(numero))
    response = bt_client.send('{}{}'.format(message, '\x1a'))

    # revenir au mode binaire PDU
    bt_client.send('AT+CMGF=0', wait=0.2)

    # revenir au storage "SM"
    if storage == "ME" :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    slot = re.findall('\+CMGW:(\w+)', response.decode())
    return slot

def send_from_storage(bt_client, index, numero=None, storage="SM") :
    # passer en mode texte
    bt_client.send('AT+CMGF=1', wait=0.2)

    # sélectionner le storage "SM" ou "ME"
    if storage == "ME" :
        bt_client.send('AT+CPMS="SM","ME"', wait=0.2)
    else :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    # Envoi du sms depuis le storage (SIM)
    if numero is None :
        at_command = 'AT+CMSS={}'.format(index)
    else :
        at_command = 'AT+CMSS={},"{}"'.format(index, numero)
    response = bt_client.send(at_command)

    # revenir au mode binaire PDU
    bt_client.send('AT+CMGF=0', wait=0.2)

    # revenir au storage "SM"
    if storage == "ME" :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    return response


def delete_sms(bt_client, index, storage="SM") :
    # sélectionner le storage "SM" ou "ME"
    if storage == "ME" :
        bt_client.send('AT+CPMS="SM","ME"', wait=0.2)
    else :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    # Suppression du sms depuis le storage
    response = bt_client.send('AT+CMGD={}'.format(index))

    # revenir au storage "SM"
    if storage == "ME" :
        bt_client.send('AT+CPMS="SM","SM"', wait=0.2)

    return response


def get_sms_indexes(bt_client, retries=5) :
    # passer en mode texte
    bt_client.send('AT+CMGF=1', wait=0.5)

    for r in range(retries) :
        message_list = bt_client.send('AT+CMGL="ALL"')
        indexes = re.findall('\+CMGL:([0-9]+)', message_list.decode())
        if len(indexes) > 0 :
            break

    # revenir en mode binaire PDU
    bt_client.send('AT+CMGF=0', wait=0.5)

    return indexes


def get_all_sms(bt_client, retries=5) :
    indexes = get_sms_indexes(bt_client, retries)

    sms_records = dict()
    for index in indexes :
        sms_records[index] = get_sms(bt_client, int(index))

    return sms_records
