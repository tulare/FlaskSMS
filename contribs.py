# -*- encoding: utf-8 -*-

import sys
import pkg_resources

pkg_resources.working_set.add_entry('.contribs')
pkg_resources.require('pybluez')

pyobex_wheel = '.contribs/PyOBEX-0.27-py3-none-any.whl'
if pyobex_wheel not in sys.path :
    sys.path.insert(0, pyobex_wheel)

