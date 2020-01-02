# -*- coding: utf-8 -*-
from settings import M_DB, REDIS_CONNECT_0
import pymongo
import math
import datetime
import json
from logutil import logger

limiter_conf = M_DB.limiter_conf
CHANNEL_LIMITER = '%s_limiter'
CACHE_TTL = 604800


def find_group(channel):
    cache_key = CHANNEL_LIMITER % channel
    logger.info("find_group cache_key: %s" % cache_key) # cache_key:http://download.52xuexi.net_limiter
    group = ''
    rate = ''
    category = ''
    Bbase = ''
    Balarm = ''
    Bhard = ''
    Bgrade = ''
    Bpolice = ''
    cache = REDIS_CONNECT_0.get(cache_key)
    '''
    ---(2018-06-29 16:15:31.964469)cache---
    b'{"category": "e1,e2,e3,e4", "rate": 800.0, "Bpolice": 1.2, "user": "hwapu", "Bhard": 1.0, "_id": "599ab249d101b441a84bb1a5", "Bbase": 170.0, "Bgrade": 3, "Balarm": 0.75}'
    '''
    if cache:
        data = json.loads(cache)
        group = data["_id"]
        rate = data["rate"]
        category = data["category"]
        user = data["user"]
        Bbase = data["Bbase"]
        Balarm = data["Balarm"]
        Bhard = data["Bhard"]
        Bgrade = data["Bgrade"]
        Bpolice = data["Bpolice"]
    if group and rate and category and user:
        return group, rate, category, user, Bbase, Balarm, Bhard, Bgrade, Bpolice
    result = limiter_conf.find({'channels': channel}, {'rate': 1, '_id': 1, 'category': 1,
                                                       'user': 1, 'Bbase': 1, 'Balarm': 1, 'Bhard': 1, 'Bgrade': 1, 'Bpolice': 1})
    logger.info("find_group result.count(): %s" % result.count())
    if not result or result.count() == 0:
        logger.info("find_group [channel not found.]: %s" % channel)
        return None, None, None, None, None, None, None, None, None
        
    for line in result:
        group = "rate_%s" % line["_id"]
        rate = line["rate"]
        category = line["category"]
        user = line["user"]
        Bbase = line["Bbase"]
        Balarm = line["Balarm"]
        Bhard = line["Bhard"]
        Bgrade = line["Bgrade"]
        Bpolice = line["Bpolice"]
    logger.info('find_group [config] group: %s|| rate: %s|| category: %s|| user: %s|| Bbase: %s|| Balarm: %s|| Bhard: %s|| Bgrade: %s|| Bpolice: %s' % (group, rate, category, user, Bbase, Balarm, Bhard, Bgrade, Bpolice))
    cache = {}
    cache["_id"] = group
    cache["rate"] = rate
    cache["category"] = category
    cache["user"] = user
    cache["Bbase"] = Bbase
    cache["Balarm"] = Balarm
    cache["Bhard"] = Bhard
    cache["Bgrade"] = Bgrade
    cache["Bpolice"] = Bpolice
    REDIS_CONNECT_0.set(cache_key, json.JSONEncoder().encode(cache)) # json.dumps(cache)
    REDIS_CONNECT_0.expire(CHANNEL_LIMITER, CACHE_TTL)
    return group, rate, category, user, Bbase, Balarm, Bhard, Bgrade, Bpolice
