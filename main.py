# -*- coding: utf-8 -*-
# Module: default
# Author: cache
# Created on: 10.5.2020
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html
# Modified for Not Another WebShare Plugin (NAWSP), 2026-08-31.

import sys

import search_results_ui
import yawsp


search_results_ui.install(yawsp)


if __name__ == '__main__':
    yawsp.router(sys.argv[2][1:])
