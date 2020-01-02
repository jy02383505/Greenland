#!/usr/bin/env python
# coding: utf-8

import traceback
import time
from datetime import datetime, timedelta

import os
import logging
import tornado
from tornado.options import options
from tornado.log import access_log, gen_log, app_log


def makeLog(fname):
    fname = fname[:fname.index('.log')] if fname.endswith('.log') else fname
    fname = os.path.join(os.path.dirname(__file__), 'logs', '%s.log' % (fname, ))
    logging.basicConfig(filename=fname)

    options['logging'] = 'DEBUG'
    # options['log_file_num_backups'] = 60
    # options['log_file_prefix'] = fname # 设置了此项,日志3倍重复,但不设置此项,无法自动切割日志
    # options['log_rotate_mode'] = 'time'
    # options['log_rotate_when'] = 'M'

    access_log.propagate = False

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    fm = tornado.log.LogFormatter(
        # fmt='[%(asctime)s]%(color)s[%(levelname)s]%(end_color)s[%(funcName)s:%(lineno)d]: %(message)s',
        fmt='%(asctime)s(%(levelname)s)-%(filename)s-[%(funcName)s|%(lineno)d]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S' + '.%3s' % datetime.now().microsecond)
    tornado.log.enable_pretty_logging(logger=logger)
    logger.handlers[0].setFormatter(fm)

    return logger

logger = makeLog('limiter')
