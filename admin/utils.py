# -*- coding: utf-8 -*-
from settings import M_DB, REDIS_CONNECT_0
from logutil import logger
import pymongo, math ,datetime
import json
import traceback
import sys
reload(sys)
sys.setdefaultencoding('utf8')
RETRY_COUNT = 3



def makeSthStrInDict(tempDict, k):
    if tempDict.get(k):
        v = tempDict.pop(k)
        tempDict[k] = json.dumps(v)


def get_all_conf(page=0, query={}, col=M_DB.control_conf):
    '''
    根据页数获取配置
    '''
    cf = col
    per_page = 30
    totalpage = int(math.ceil(cf.find(query).count(True)/(per_page*1.00)))
    all_conf = [u for u in cf.find(query).sort('created_time', pymongo.DESCENDING).skip(page*per_page).limit(per_page)]
    return {'all_conf': all_conf, 'totalpage': totalpage}


def db_update(collection,find,modification):
    for retry_count in range(RETRY_COUNT):
        try:
            ret = collection.update(find, modification)
            if ret.get("updatedExisting") == True and ret.get("n") > 0:
                return
        except Exception as e:
            logger.info("db_update[error]: %s" % (traceback.format_exc(e), ))

def make_normal_date_range():
    '''
    生成默认时间查询范围
    '''
    end_date = datetime.datetime.now()
    begin_date = end_date - datetime.timedelta(days=30)
    return begin_date.strftime("%m/%d/%Y"), end_date.strftime("%m/%d/%Y")


def make_date_query(begin_str, end_str):
    '''
    生成日期查询参数
    @begin_str 04/20/2016 月／日／年
    @end_str 同上
    '''
    begin_list = begin_str.split('/')
    end_list = end_str.split('/')
    begin_date = datetime.datetime(int(begin_list[2]), int(begin_list[0]), int(begin_list[1]), 0,0,0)
    end_date = datetime.datetime(int(end_list[2]), int(end_list[0]), int(end_list[1]), 23,59,59)
    if begin_date >= end_date:
        #输入错误
        return False
    return {'created_time': {'$gte': begin_date, '$lte': end_date}}


def get_channel_cache_key(channel, category):
    '''
    获取配置缓存key
    '''
    return '%s_%s' %(channel, category)


def add_config_cache(channel, category, conf):
    '''
    配置缓存加入
    '''
    try:
        for k, v in conf.items():
            if isinstance(v, datetime.datetime):
                conf[k] = datetime.datetime.strftime(v, '%Y-%m-%dT%H:%M:%S')
            if k == '_id':
                conf[k] = str(v)
        _key = get_channel_cache_key(channel, category)
        REDIS_CONNECT_0.hmset(_key, conf)
    except Exception as e:
        logger.info('add_config_cache[error]: %s' % (traceback.format_exc(e), ))

def get_config_cache(channel, category):
    '''
    获取配置
    '''
    res = None
    try:
        _key = get_channel_cache_key(channel, category)
        res = REDIS_CONNECT_0.hgetall(_key)
    except Exception as e:
        logger.info('get_config_cache[error]: %s' % (traceback.format_exc(e), ))
    return res

def del_config_cache(channel, category):
    '''
    删除配置
    '''
    try:
        _key = get_channel_cache_key(channel, category)
        REDIS_CONNECT_0.delete(_key)
    except Exception as e:
        logger.info('del_config_cache[error]: %s' % (traceback.format_exc(e), ))

def add_limiter_cache(channels, category, info):
    '''
    添加limiter cache缓存
    '''
    try:
        for channel in channels:
            _key = "%s_limiter_%s" %(channel, category)
            REDIS_CONNECT_0.set(_key, json.dumps(info))
            REDIS_CONNECT_0.expire(_key, 604800)
            _key1 = "%s_limiter" %channel
            REDIS_CONNECT_0.set(_key1, json.dumps(info))
    except Exception as e:
        logger.info('add_limiter_cache[error]: %s' % (traceback.format_exc(e), ))


def del_limiter_cache(channels, category):
    '''
    删除limiter配置
    '''
    try:
        for channel in channels:
            _key = "%s_limiter_%s" %(channel, category)
            _key1 = "%s_limiter" %channel
            logger.info("del_limiter_cache _key: %s" %_key)
            REDIS_CONNECT_0.delete(_key)
            REDIS_CONNECT_0.delete(_key1)
    except Exception as e:
        logger.info('del_limiter_cache[error]: %s' % (traceback.format_exc(e), ))


def error_res(msg):

    return '<html><script type="text/javascript">alert("%s");history.go(-1)</script></html>' %(msg)


def pager(total_page, current_page, max_page_len=10):
    '''
    返回页码
    return page_list, can_pre, can_next
    '''
    can_pre = True
    can_next = True
    if total_page <= max_page_len:
        return range(total_page), False, False

    #前段个数
    half_num = max_page_len / 2
    #后段个数
    other_half = max_page_len - half_num

    res = [current_page]
    for x in xrange(1, other_half+1):
        page = current_page + x
        if page < total_page:
            res.append(page)
            other_half -= 1
        else:
            can_next = False
            break

    if other_half > 0:
        left_num = half_num + other_half
    else:
        left_num = half_num

    for n in xrange(1, left_num+1):
        pre_page = current_page - n
        if pre_page >= 0:
            res.insert(0, pre_page)
        else:
            can_pre = False
            break

    return res, can_pre, can_next

def analysis_directions(directions):
    edge_str = "边缘"
    upper_str = "上层"
    flag="00"
    try:
        for line in directions.split(','):
            if 'e' in line:
                if flag=='01' or flag=='11':
                    flag='11'
                else:
                    flag='10'
                edge_str = edge_str + line[1]+","
            if line=='in' or line=='out':
                if flag=='10' or flag=='11':
                    flag='11'
                else:
                    flag=='10'
                upper_str = upper_str + line+","
        if flag=="10":
            return edge_str[:-1]+"方向"
        elif flag=='01':
            return upper_str[:-1]+"方向"
        else:
            return edge_str[:-1]+"方向,"+upper_str[:-1]+"方向"
    except Exception as e:
        logger.info('analysis_directions[error]: %s' % (traceback.format_exc(e), ))
        return edge_str

