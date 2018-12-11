# -*- encoding: utf-8 -*-

from datetime import datetime
from . import app

@app.template_filter('now')
def f_now(s) :
    return datetime.now()
