# -*- coding: utf-8 -*-
import os
from pymongo import MongoClient
import redis

# SM
# M_CONNECT = MongoClient("mongodb://bermuda:bermuda_refresh@10.11.30.18:27017,10.11.30.20:27017,10.11.30.21:27017/cc")
# REDIS_INFO = ['10.11.30.90', 19000]
# M_CONNECT = MongoClient("mongodb://bermuda:bermuda_refresh@223.202.211.233:27017,223.202.211.234:27017/cc")
M_CONNECT = MongoClient("mongodb://bermuda:bermuda_refresh@223.202.211.233:27017/cc")
REDIS_INFO = ['223.202.211.249', 6379, 'bermuda_refresh']

# TEST
#M_CONNECT = MongoClient("mongodb://bermuda:bermuda_refresh@192.168.56.139:27017/cc")
#REDIS_INFO = ['192.168.56.139' ,6379]

M_DB = M_CONNECT['cc']
REDIS_CONNECT_0 = redis.Redis(host=REDIS_INFO[0], port=REDIS_INFO[1], db=0, password=REDIS_INFO[2])
# REDIS_CONNECT_0 = redis.Redis(host=REDIS_INFO[0], port=REDIS_INFO[1], db=0)

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates")
STATIC_PATH = os.path.join(os.path.dirname(__file__), "static")
DEBUG = True

RCMS_ROOT = "https://rcmsapi.chinacache.com/channelsByName?channelName=%s"
PORTAL_API = "https://portal-api.chinacache.com:444/api/internal/getCustomer.do?username=%s"
UPPER_RATE_API = "https://api.chinacache.com/reportdata/monitor/queryByChannels?type=bandiwidth&withtime=true&layerdetail=false&username=%s&pass=%s&channelId=%s&starttime=%s&endtime=%s&format=json&isUP=true"
