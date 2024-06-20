"""
Routes and views for the flask application.
"""

from datetime import datetime
from os import environ

from BTPlugin import list_devices, BTNearbyDevices, BTClient, sms

from markupsafe import Markup
from flask import (
    request, redirect, url_for,
    render_template, send_file
)
from . import forms
from . import app

nearby = BTNearbyDevices()
BT_PHONE = environ.get('BT_PHONE', '<NO_PHONE>')

@app.route('/')
@app.route('/home')
def home():
    """Renders the home page."""
    return render_template(
        'index.html',
        title='Home Page',
        year=datetime.now().year
    )

@app.route('/contact')
def contact():
    """Renders the contact page."""
    return render_template(
        'contact.html',
        title='Contact',
        year=datetime.now().year,
        message='Your contact page.'
    )

@app.route('/about')
def about():
    """Renders the about page."""
    return render_template(
        'about.html',
        title='About',
        year=datetime.now().year,
        message='Your application description page.'
    )

@app.route('/btdevices')
def btdevices():
    """Renders the devices page."""
    return render_template(
        'btdevices.html',
        title='Bluetooth',
        year=datetime.now().year,
        message=Markup(list_devices())
        
    )

@app.route('/sendsms', methods=['GET', 'POST'])
def sendsms() :
    """Renders the sendsms page"""
    form = forms.SendSMSForm(request.form)

    if request.method == 'POST' and form.validate() :
        try :
            feedback = sms.send_sms_pdu(
                nearby.service_dialup(BT_PHONE),
                numero=form.phoneno.data,
                message=form.textsms.data
            )   
        except OSError :
            feedback = 'Autorisation refusée'

        return render_template(
            'smssent.html',
            title='SMS Envoyé',
            year=datetime.now().year,
            message=feedback
        )

    return render_template(
        'smsform.html',
        title='Envoi SMS',
        year=datetime.now().year,
        form=form
    )
