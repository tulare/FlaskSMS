# -*- encoding: utf-8 -*-

__all__ = [
    'send_sms', 'send_sms_pdu',
    'get_sms',
    'store_sms', 'store_draft_sms',
    'send_from_storage',
    'delete_sms'
]

import re
import logging
from enum import Enum
from .core import BTClient
from .pdu import decodeSmsPdu, encodeSmsSubmitPdu

# Bluetooth for sending SMS

# ----------------------------------------------------------

class SMSFormat(Enum) :
    PDU = 0
    TEXT = 1

# ----------------------------------------------------------

class SMS :

    def __init__(self, service, encoding='utf-8') :
        self._service = service
        self._encoding = encoding

    @property
    def mode(self) :
        response = b''
        with BTClient(self._service) as bt_client :
            response = bt_client.send('AT+CMGF?', wait=1, bufsize=32)
        mode, = re.findall(b'\\+CMGF:([0-9]+)', response)
        return SMSFormat(int(mode))

    @mode.setter
    def mode(self, mode) :
        mode = SMSFormat(mode)
        with BTClient(self._service) as bt_client :
            bt_client.send(f'AT+CMGF={mode.value}', wait=1, bufsize=32)
        
    def getMessage(self, index, storage="SM") :
        ret = get_sms(self._service, index, encoding=self._encoding, storage=storage)
        return ret        

    def sendMessage(self, numero, message) :
        ret = send_sms_pdu(self._service, numero, message)
        return ret

    def listMessages(self, retries=10, storage="SM") :
        sms_data_pdu = get_all_sms_pdu(self._service, retries=retries, storage=storage)
        ret = parse_messages_pdu(sms_data_pdu)
        return ret

    def getServiceCenter(self) :
        ret = get_smsc(self._service)
        return ret

# ----------------------------------------------------------

RE_COMPO = re.compile(b'\xd4\x80(..)\xe0\xa0(.)(.+)', re.DOTALL)

def parse_messages(messages_data) :

    messages = []

    # suppression header, trailer
    data = messages_data.partition(b'\r\n')[-1]
    data = data.rpartition(b'OK\r\n')[0]
    
    # scinder en une liste de messages
    messages_list = [x for x in data.split(b'+CMGL:') if x != b'']
    
    for msg in messages_list :
        # scinder chaque message en header + body
        header, body = [x for x in msg.split(b'\r\n\r\n') if x != b'']

        # détecter les messages composés
        match = RE_COMPO.match(body)
        if match is None :
            messages.append({'header' : header, 'ident' : None, 'text' : body})
        else :
            ident, order, content = match.groups()
            logging.debug(f'{ident} {order} {content}')
            if ord(order) == 0x81 :
                # premier morceau
                messages.append({'header' : header, 'ident' : ident, 'text' : content})
            else :
                # morceaux suivants (on complète le message avec cet ident)
                for message in filter(lambda x : x.get('ident') == ident, messages) :
                    message['text'] += content

    return messages

# ----------------------------------------------------------

def parse_messages_pdu(messages_data) :

    messages = []

    # suppression header, trailer
    data = messages_data.partition(b'\r\n')[-1]
    data = data.rpartition(b'OK\r\n')[0]

    # scinder en une liste de messages
    messages_list = [x.strip() for x in data.split(b'+CMGL:') if x != b'']

    for msg in messages_list :
        # scinder chaque message en header + body
        header, body = [x for x in msg.split(b'\r\n') if x != b'']
        record = decodeSmsPdu(body)
        if 'udh' in record :
            # indique un message composé
            for udh in record['udh'] :
                if udh.number == 1 :
                    record.update({'reference' : udh.reference, 'parts' : udh.parts})
                    messages.append(record)
                else :
                    for message in filter(lambda x : x.get('reference',-1) == udh.reference, messages) :
                        message['text'] += record.get('text')
        else :
            # message simple
            record.update({'reference' : None, 'parts' : 1 })
            messages.append(record)

    return messages

# ----------------------------------------------------------

def bt_cmd(bt_client, cmd, wait=1) :
    ret = bt_client.send(cmd, wait)
    logging.debug(f'{cmd} -> {ret}')
    return ret

# ----------------------------------------------------------

def set_sms_mode(bt_client, mode=SMSFormat.PDU) :
    mode = SMSFormat(mode)
    response = bt_client.send(f'AT+CMGF={mode.value}', wait=1, bufsize=32)
    return response

# ----------------------------------------------------------

def set_sms_storage(bt_client, storage_1="SM", storage_2="SM", storage_3="SM") :
    response = bt_client.send(f'AT+CPMS="{storage_1}","{storage_2}","{storage_3}"', bufsize=32, wait=1)
    return response

# ----------------------------------------------------------

def get_smsc(service) :
    response = b''

    with BTClient(service) as bt_client :
        response = bt_client.send('AT+CSCA?', wait=2, bufsize=64)

    return response

# ----------------------------------------------------------

def send_sms(service, numero, message) :
    response = b''

    with BTClient(service) as bt_client :
        # passer en mode texte
        set_sms_mode(bt_client, mode=SMSFormat.TEXT)

        # envoi direct du sms
        bt_client.send(f'AT+CMGS="{numero}"')
        response = bt_client.send(f'{message}{chr(0x1a)}', wait=3, bufsize=32)

        # revenir au mode binaire PDU par défaut
        set_sms_mode(bt_client)

    return response

# ----------------------------------------------------------

def send_sms_pdu(service, numero, message) :

    responses = []

    # composition du SMS
    smspdu = encodeSmsSubmitPdu(
        number=numero,
        text=message,
        requestStatusReport=False
    )
    
    with BTClient(service) as bt_client :
        # s'assurer du mode binaire PDU
        set_sms_mode(bt_client, SMSFormat.PDU)

        # envoi du sms par morceaux
        for _sms in smspdu :
            bt_client.send(f'AT+CMGS={_sms.tpduLength}', wait=2, bufsize=16)
            response = bt_client.send(f'{_sms}{chr(0x1a)}', wait=2, bufsize=16)
            responses.append(response.decode())

    return responses

# ----------------------------------------------------------

def get_sms(service, index, wait=3, encoding='utf-8', storage="SM") :

    response = b''

    with BTClient(service) as bt_client :
        # passer en mode binaire PDU
        set_sms_mode(bt_client, SMSFormat.PDU)

        # sélectionner le storage "SM" ou "ME"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_1=storage)
        else :
            set_sms_storage(bt_client, storage_1="SM")
            
        response = bt_client.send(f'AT+CMGR={index}', wait=wait, bufsize=64)

        # revenir au storage "SM"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_1="SM")

    logging.debug(f'get_sms: {response}')
    data = response.decode(encoding, errors='replace')
    pdu_records = re.findall('\+CMGR:.+\r\n(.+)\r\n', data)
    logging.debug(f'get_sms: {pdu_records}')

    liste_sms = []
    for smspdu in pdu_records :
        _sms = decodeSmsPdu(smspdu)
        liste_sms.append(_sms)

    return liste_sms

# ----------------------------------------------------------

def store_sms(service, numero, message, storage="SM") :

    response = b''

    with BTClient(service) as bt_client :
        # passer en mode texte
        set_sms_mode(bt_client, SMSFormat.TEXT)

        # sélectionner le storage "SM" ou "ME"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_2=storage)
        else :
            set_sms_storage(bt_client, storage_2="SM")

        # stockage du sms en mémoire
        bt_client.send(f'AT+CMGW="{numero}",,"REC UNREAD"')
        response = bt_client.send(f'{message}{chr(0x1a)}', wait=3, bufsize=32)

        # revenir au mode binaire PDU
        set_sms_mode(bt_client)

        # revenir au storage "SM"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_2="SM")

    slot = re.findall('\+CMGW:(\w+)', response.decode())
    return slot

# ----------------------------------------------------------

def store_draft_sms(service, numero, message, storage="SM") :

    response = b''

    with BTClient(service) as bt_client :
        # passer en mode texte
        set_sms_mode(bt_client, SMSFormat.TEXT)

        # sélectionner le storage "SM" ou "ME"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_2=storage)
        else :
            set_sms_storage(bt_client, storage_2="SM")

        # stockage du sms en mémoire
        bt_client.send(f'AT+CMGW="{numero}",,"STO UNSENT"')
        response = bt_client.send(f'{message}{chr(0x1a)}', wait=3, bufsize=32)

        # revenir au mode binaire PDU
        set_sms_mode(bt_client)

        # revenir au storage "SM"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_2="SM")

    slot = re.findall('\+CMGW:(\w+)', response.decode())
    return slot

# ----------------------------------------------------------

def send_from_storage(service, index, numero=None, storage="SM") :

    response = b''

    with BTClient(service) as bt_client :
        # passer en mode texte
        set_sms_mode(bt_client, SMSFormat.TEXT)

        # sélectionner le storage "SM" ou "ME"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_2=storage)
        else :
            set_sms_storage(bt_client, storage_2="SM")

        # Envoi du sms depuis le storage (SIM)
        if numero is None :
            at_command = f'AT+CMSS={index}'
        else :
            at_command = f'AT+CMSS={index},"{numero}"'
        response = bt_client.send(at_command, wait=3, bufsize=32)

        # revenir au mode binaire PDU
        set_sms_mode(bt_client)

        # revenir au storage "SM"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_2="SM")

    return response

# ----------------------------------------------------------

def delete_sms(service, index, storage="SM") :

    response = b''

    with BTClient(service) as bt_client :
        # sélectionner le storage "SM" ou "ME"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_1=storage)
        else :
            set_sms_storage(bt_client, storage_1="SM")

        # Suppression du sms depuis le storage
        response = bt_client.send(f'AT+CMGD={index}', wait=1)

        # revenir au storage "SM"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_1="SM")

    return response

# ----------------------------------------------------------

def get_all_sms(service, retries=10, storage="SM") :

    data = b''
    
    with BTClient(service) as bt_client :        
        # passer en mode texte
        set_sms_mode(bt_client, SMSFormat.TEXT)

        # sélectionner le storage "SM" ou "ME"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_1=storage)
        else :
            set_sms_storage(bt_client, storage_1="SM")

        for r in range(retries) :
            response = bt_client.send('AT+CMGL="ALL"', wait=3, bufsize=64)
            indexes = re.findall(b'\\+CMGL:([0-9]+)', response)
            if len(indexes) > 0 :
                data = response
                break

        # revenir en mode binaire PDU
        set_sms_mode(bt_client)
        
        # revenir au storage "SM"
        set_sms_storage(bt_client, storage_1="SM")
    
    return data

# ----------------------------------------------------------

def get_all_sms_pdu(service, retries=10, storage="SM") :

    data = b''
    
    with BTClient(service) as bt_client :        
        # s'assurer du mode binaire PDU
        set_sms_mode(bt_client, SMSFormat.PDU)

        # sélectionner le storage "SM" ou "ME"
        if storage == "ME" :
            set_sms_storage(bt_client, storage_1=storage)
        else :
            set_sms_storage(bt_client, storage_1="SM")

        for r in range(retries) :
            # "ALL" = 4 en mode PDU
            response = bt_client.send('AT+CMGL=4', wait=3, bufsize=64)
            indexes = re.findall(b'\\+CMGL:([0-9]+)', response)
            if len(indexes) > 0 :
                data = response
                break

        # revenir en mode binaire PDU
        set_sms_mode(bt_client)
        
        # revenir au storage "SM"
        set_sms_storage(bt_client, storage_1="SM")
    
    return data

