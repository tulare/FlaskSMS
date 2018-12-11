# -*- encoding: utf-8 -*-

from PyOBEX import client, responses
from lxml import etree
from io import BytesIO

class BrowserClient(object) :

    def __init__(self, addr, port) :
        self._cli = None
        self._addr = addr
        self._port = port
        
    def connect(self) :
        if self._cli is None :
            try :
                self._cli = client.BrowserClient(self._addr, self._port)
                r = self._cli.connect()

                if not isinstance(r, responses.ConnectSuccess) :
                    self._cli = None
                    
            except OSError :
                self._cli = None

    def disconnect(self) :
        if self._cli is not None :
            try :
                self._cli.disconnect()
            except OSError :
                pass

        self._cli = None

    def listdir(self) :
        r, r_xml  = self._cli.listdir()
        
        tree = etree.parse(BytesIO(r_xml))

        dirs = tree.xpath('//folder/@name')
        if len(tree.xpath('//parent-folder')) > 0 :
            dirs.append('..')
        files = tree.xpath('//file/@name')

        return { 'dirs' : dirs, 'files' : files }

    def chdir(self, name) :

        if name == '..' :
            r = self._cli.setpath(to_parent=True)
        else :
            r = self._cli.setpath(name)

        if isinstance(r, responses.FailureResponse) :
            return False

        return True
        
