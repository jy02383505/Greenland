#!/usr/bin/python
# -*- coding: utf-8 -*-
from logutil import logger
import json
import traceback
import urllib2
import time
from settings import M_DB, PORTAL_API, RCMS_ROOT, UPPER_RATE_API
from bson import ObjectId
limiter_conf = M_DB.limiter_conf


def get_ApiPassword(username):
    try:
        req = urllib2.Request(PORTAL_API % (username))
        rcms_res = urllib2.urlopen(req, timeout=10)
        res_data = rcms_res.read()
        res_obj = json.loads(res_data)
        logger.info('get_ApiPassword res_obj: %s' % (res_obj, ))
        return res_obj['apiPassword']
    except Exception as e:
        logger.info('get_ApiPassword[error]: %s' % (traceback.format_exc(e), ))


def get_ChannelCode(channelname):
    try:
        req = urllib2.Request(RCMS_ROOT % (channelname))
        rcms_res = urllib2.urlopen(req, timeout=10)
        res_data = rcms_res.read()
        res_obj = json.loads(res_data)
        logger.info('get_ChannelCode res_obj: %s' % res_obj)
        for line in res_obj:
            if line['channelName'] == channelname:
                return line['channelCode']
    except Exception as e:
        logger.info('get_ChannelCode[error]: %s' % (traceback.format_exc(e), ))


def get_rate(username, group):
    try:
        had_config_channel = limiter_conf.find(
            {'_id': ObjectId(group)}, {'channels': 1})
        all_channels = []
        for h in had_config_channel:
            all_channels = h['channels']
        logger.info("get_rate all_channels: %s" % all_channels)
        sum_upper_rate = 0.0
        for line in all_channels:
            channelCode = get_ChannelCode(line)
            apiPassword = get_ApiPassword(username)
            now_time = time.strftime('%Y%m%d%H%M', time.localtime(time.time()))
            if int(now_time[-1]) < 5:
                now_time = now_time[:-1] + '0'
            else:
                now_time = now_time[:-1] + '5'
            logger.info('get_rate now_time: %s' % (now_time))
            url = UPPER_RATE_API % (
                username, apiPassword, channelCode, now_time, now_time)
            logger.info('get_rate url: %s' % (url))
            req = urllib2.Request(url)
            rcms_res = urllib2.urlopen(req, timeout=10)
            res_data = rcms_res.read()
            res_obj = json.loads(res_data)
            logger.info("get_rate res_obj['Datas'][0]['value']: %s" % (res_obj['Datas'][0]['value'], ))
            sum_upper_rate = sum_upper_rate + float(res_obj['Datas'][0]['value'])
        return sum_upper_rate
    except Exception as e:
        logger.info('get_rate[error]: %s' % (traceback.format_exc(e), ))
