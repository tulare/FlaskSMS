"""
This script runs the FlaskApp application using a development server.
"""

from os import environ
from FlaskApp import app

if __name__ == '__main__':
    HOST = environ.get('FLASK_RUN_HOST', 'localhost')
    try:
        PORT = int(environ.get('FLASK_RUN_PORT', '5000'))
    except ValueError:
        PORT = 5000
    app.run(HOST, PORT)
