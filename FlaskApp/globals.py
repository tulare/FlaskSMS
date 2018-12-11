# -*- encoding: utf-8 -*-

from datetime import datetime
from . import app

@app.template_global('now')
def g_now() :
    return int( datetime.now().timestamp() * 1000 )
