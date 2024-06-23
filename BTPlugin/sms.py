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
import enum
from .core import BTClient
from .pdu import decodeSmsPdu, encodeSmsSubmitPdu

# Bluetooth for sending SMS

# ----------------------------------------------------------

class SMSFormat(enum.IntEnum) :
    PDU  = 0
    TEXT = 1

class SMSFilter(enum.Enum) :
    REC_UNREAD = 0, "REC UNREAD"
    REC_READ   = 1, "REC READ"
    STO_UNSENT = 2, "STO UNSENT"
    STO_SENT   = 3, "STO SENT"
    ALL        = 4, "ALL"
    def __new__(cls, code, label) :
        entry = object.__new__(cls)
        entry.code = entry._value_ = code
        entry.label = label
        return entry

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
        mode, = parse_response(response)
        return SMSFormat(int(mode))

    @mode.setter
    def mode(self, mode) :
        mode = SMSFormat(mode)
        with BTClient(self._service) as bt_client :
            bt_client.send(f'AT+CMGF={mode}', wait=1, bufsize=32)

    @property
    def storage(self) :
        response = at_cmd(self._service, 'AT+CPMS?')
        ret = parse_response(response)
        return ret

    @storage.setter
    def storage(self, storage) :
        at_cmd(self._service, f'AT+CPMS={storage}')
        
    def getMessage(self, index, storage="SM") :
        ret = get_sms(self._service, index, encoding=self._encoding, storage=storage)
        return ret        

    def sendMessage(self, numero, message) :
        ret = send_sms_pdu(self._service, numero, message)
        return ret

    def listMessages(self, retries=20, storage="SM", filter_by=SMSFilter.ALL) :
        sms_data_pdu = get_all_sms_pdu(self._service, retries=retries, storage=storage, filter_by=filter_by)
        ret = parse_messages_pdu(sms_data_pdu)
        return ret

    def getServiceCenter(self) :
        response = get_smsc(self._service)
        ret = parse_response(response)
        return ret

    @property
    def phoneManufacturer(self) :
        response = at_cmd(self._service, 'AT+CGMI')
        ret = parse_response(response)
        return ret

    @property
    def phoneModel(self) :
        response = at_cmd(self._service, 'AT+CGMM')
        ret = parse_response(response)
        return ret

    @property
    def softwareVersion(self) :
        response = at_cmd(self._service, 'AT+CGMR')
        ret = parse_response(response)
        return ret

    @property
    def phoneIMEI(self) :
        response = at_cmd(self._service, 'AT+CGSN')
        ret = parse_response(response)
        return ret

    @property
    def phoneIMSI(self) :
        response = at_cmd(self._service, 'AT+CIMI')
        ret = parse_response(response)
        return ret

# ----------------------------------------------------------

def parse_response(response_data) :
    ret_list = []

    # cas limite
    if response_data == b'' :
        return ret_list
    
    # identification commande
    commande, = re.findall(b'AT(\\+....)', response_data)
    
    # suppression header, trailer
    data = response_data.partition(b'\r\n')[-1]
    data = data.rpartition(b'OK\r\n')[0]

    # découpage en liste de résultats
    ret_list = [x.strip() for x in data.split(commande + b':') if x != b'']

    return ret_list


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
    messages_list = parse_response(messages_data)

    for msg in messages_list :
        # scinder chaque message en header + body
        header, body = [x for x in msg.split(b'\r\n') if x != b'']
        slot, filter_type, _, _ = header.decode().split(',')
        record = {
            'slot' : int(slot),
            'reference' : None,
            'filter_type' : SMSFilter(int(filter_type)),
            'parts' : 1,
            'time' : None,
            'validity' : None
        }
        record.update(decodeSmsPdu(body))
        if 'udh' in record :
            # indique un message composé
            for udh in record['udh'] :
                if udh.number == 1 :
                    record.update({
                        'reference' : udh.reference,
                        'parts' : udh.parts
                    })
                    messages.append(record)
                else :
                    for message in filter(lambda x : x.get('reference',-1) == udh.reference, messages) :
                        message['text'] += record.get('text')
        else :
            # message simple
            messages.append(record)

    return messages

# ----------------------------------------------------------

def at_cmd(service, cmd, wait=1, bufsize=32) :
    response = b''

    with BTClient(service) as bt_client :
        response = bt_client.send(cmd, wait=wait, bufsize=bufsize)
    
    return response

# ----------------------------------------------------------

def ask(service, cmd, wait=1, bufsize=32) :
    print(at_cmd(service, cmd=cmd, wait=wait, bufsize=bufsize).decode())

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

def get_all_sms(service, retries=10, storage="SM", filter_by=SMSFilter.ALL) :

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
            response = bt_client.send(f'AT+CMGL="{filter_by.label}"', wait=3, bufsize=64)
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

def get_all_sms_pdu(service, retries=20, storage="SM", filter_by=SMSFilter.ALL) :

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
            response = bt_client.send(f'AT+CMGL={filter_by.value}', wait=2, bufsize=64)
            indexes = re.findall(b'\\+CMGL:([0-9]+)', response)
            if len(indexes) > 0 :
                data = response
                break

        # revenir au storage "SM"
        set_sms_storage(bt_client, storage_1="SM")
    
    return data

