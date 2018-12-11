# -*- encoding: utf-8 -*-

from wtforms import (
    Form,
    BooleanField, StringField, TextAreaField, PasswordField,
    validators
)

class RegistrationForm(Form):
    username = StringField('Username', [validators.Length(min=4, max=25)])
    email = StringField('Email Address', [validators.Length(min=6, max=35)])
    password = PasswordField('New Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Repeat Password')
    accept_tos = BooleanField('I accept the TOS', [validators.DataRequired()])

class SendSMSForm(Form) :
    phoneno = StringField(
        'Numéro tél.',
        [
            validators.DataRequired(),
            validators.Regexp('^\+?[0-9]+$')
        ]
    )
    textsms = TextAreaField(
        'Texte SMS',
        [
            validators.DataRequired()
        ],
        render_kw={'rows' : 6, 'cols' : 60}
    )
