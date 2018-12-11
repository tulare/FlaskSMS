"""
The flask application package.
"""
from flask import Flask
app = Flask(__name__)

import FlaskApp.globals
import FlaskApp.filters
import FlaskApp.views
