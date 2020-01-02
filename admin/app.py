#!/usr/bin/env python
# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
from tornado.gen import coroutine
from tornado.httpserver import HTTPServer
from tornado.httpclient import AsyncHTTPClient
from tornado.options import define, options
import time
import os
import redis
import datetime
import random
import xlwt
import StringIO
import urllib2
import json
from multiprocessing import Process
from pymongo import *
from utils import get_all_conf, db_update, add_config_cache, get_config_cache, del_config_cache, make_normal_date_range, make_date_query, error_res, pager, add_limiter_cache, del_limiter_cache, analysis_directions, makeSthStrInDict
from settings import M_DB, TEMPLATE_PATH, STATIC_PATH, DEBUG
from bson import ObjectId
import traceback
from limiter import report_data
from logutil import logger


def get_time():
    return time.strftime('%Y-%m-%d %H:%M:%S') + '.%s' % datetime.datetime.now().microsecond


control_conf = M_DB.control_conf
limiter_conf = M_DB.limiter_conf
limiter_public_conf = M_DB.limiter_public_conf
RCMS_API = "https://cms3-apir.chinacache.com/customer/%s/channels"

settings = {"template_path": TEMPLATE_PATH, "static_path": STATIC_PATH, 'debug': DEBUG}


class Index(tornado.web.RequestHandler):
    '''
    /首页 暂时做跳转
    '''

    def get(self):
        self.redirect('/conf')


class ConfigTop(tornado.web.RequestHandler):
    '''
    鉴权配置首页
    '''

    def get(self):

        res = get_all_conf()
        self.render('conf.html', query_id='', all_conf=res[
                    'all_conf'], totalpage=res['totalpage'], c_page=0)

    def post(self):

        query = {}
        query_id = self.get_argument('query_id', '')
        if query_id:
            query = {'$or': [{'user': query_id}, {'channel': query_id}]}
        c_page = int(self.get_argument('c_page', 0))
        res = get_all_conf(c_page, query)
        self.render('conf.html', query_id=query_id, all_conf=res[
                    'all_conf'], totalpage=res['totalpage'], c_page=c_page)


class ConfigAdd(tornado.web.RequestHandler):
    '''
    鉴权配置添加
    '''

    def get(self):

        self.render('conf_add.html')

    def post(self):

        category = self.get_argument('category', '')
        # logger.info('ConfigAdd[post] category: %s' % category)
        user = self.get_argument('user', '')
        # logger.info('ConfigAdd[post] user: %s' % user)
        channels = self.get_arguments('box_channels')
        # logger.info('ConfigAdd[post] channel: %s' % channel)

        suffix = self.get_argument('suffix')
        if not suffix:
            suffix = ''
        cycle = self.get_argument('cycle', 0)
        # if not cycle:
        #     return self.write(error_res('Please put cycle'))
        cycle = 0 if not cycle else int(cycle)

        # logger.info('ConfigAdd[post] cycle: %s' % cycle)
        num = self.get_argument('num', 0)
        # if not num:
        #     return self.write(error_res('Please put num'))
        num = 0 if not num else int(num)

        # logger.info('ConfigAdd[post] num: %s' % num)
        visit_cycle = self.get_argument('visit_cycle', 0)
        # if not visit_cycle:
        #     return self.write(error_res('Please put visit_cycle'))
        visit_cycle = 0 if not visit_cycle else int(visit_cycle)
        # logger.info("ConfigAdd[post] visit_cycle: %s" % visit_cycle)
        visit_num = self.get_argument('visit_num', 0)
        # if not visit_num:
        #     return self.write(error_res('Please put visit_num'))
        visit_num = 0 if not visit_num else int(visit_num)
        # logger.info("ConfigAdd[post] visit_num: %s" % visit_num)
       # cache_invalid_time = self.get_argument('cache_invalid_time')
       # if not cache_invalid_time:
       #     return self.write(error_res('Please put cache_invalid_time'))
        cache_invalid_time = int(cycle)
        # logger.info("ConfigAdd[post] cache_invalid_time: %s" % cache_invalid_time)
        add_query_time = self.get_argument('add_query_time')

        rules_str = self.get_argument('rules_map')
        if rules_str:
            for line in rules_str.split('\n'):
                if len(line.split(',')) != 4:
                    return self.write(error_res('Please enter the right field: multi-rules-config-board.'))
            rules_map = [{"theKey": i.split(',')[0].strip(), "theCycle": int(i.split(',')[1].strip()), "theNum": int(
                i.split(',')[2].strip()), "thePeriod": int(i.split(',')[3].strip())} for i in rules_str.split('\n')]
        else:
            rules_map = []
        # logger.info('ConfigAdd[post] rules_map: %s' % (rules_map, ))

        named_str = self.get_argument('named_map')
        if named_str:
            for line in named_str.split('\n'):
                if len(line.split(',')) != 5:
                    return self.write(error_res('Please enter the right field: named.'))
            named_map = [{"named": i.split(',')[0].strip(), "locationName": i.split(',')[1].strip(), "namedCycle": int(i.split(',')[2].strip(
            )), "namedNum": int(i.split(',')[3].strip()), "namedPeriod": int(i.split(',')[4].strip())} for i in named_str.split('\n')]
        else:
            named_map = []
        logger.info('ConfigAdd[post] named_map: %s' % (named_map, ))

        if not add_query_time:
            # if not have add_query_time  the add_query_time equal cycle
            add_query_time = cycle
        add_query_time = int(add_query_time)

        all_query_time = self.get_argument('all_query_time')
        if not all_query_time:
            all_query_time = 24 * 60 * 60
        all_query_time = int(all_query_time)
        for c in channels:
            config_cache = get_config_cache(c + suffix, category)
            if config_cache:
                return self.write(error_res('%s %s config cache had already added' % (c + suffix, category)))

        for i in channels:
            logger.info('ConfigAdd[post] i: %s|| category: %s|| num: %s|| cycle: %s' % (
                i, category, num, cycle, ))
            tempDict = {'user': user, 'channel': i, 'suffix': suffix, 'num': num, 'category': category, 'cycle': cycle,
                        'visit_cycle': visit_cycle, 'visit_num': visit_num, 'cache_invalid_time': cache_invalid_time,
                        'created_time': datetime.datetime.now(), 'add_query_time': add_query_time,
                        'all_query_time': all_query_time}
            if rules_map:
                tempDict.update({'rules_map': rules_map})
            if named_map:
                tempDict.update({'named_map': named_map})
            control_conf.insert(tempDict)
            logger.info('ConfigAdd[post] type(suffix): %s|| suffix: %s' % (type(suffix), suffix))

            makeSthStrInDict(tempDict, 'rules_map')
            makeSthStrInDict(tempDict, 'named_map')

            add_config_cache("%s%s" % (i, str(suffix)), category, tempDict)

        self.redirect('/conf')


class CheckUserToRcms(tornado.web.RequestHandler):
    '''
    根据用户名获取可配置频道
    '''
    @coroutine
    def post(self):

        username = self.get_argument('user')
        conf_type = self.get_argument('conf_type', 'auth')
        resp = yield AsyncHTTPClient().fetch(RCMS_API % (username))
        w = {'code': 0, 'channels': []}
        all_channel = []
        if resp.code == 200:
            if resp.body:
                resp_json = json.loads(resp.body)
                if resp_json:
                    all_channel = [i['name'] for i in resp_json]
                else:
                    # 用户名错误or用户无任何频道
                    w['code'] = 1
            else:
                # 用户名错误or用户无任何频道
                w['code'] = 1

        else:
            # rcms 异常
            w['code'] = 2

        if conf_type == 'auth':
            can_set_channel = set()
            if all_channel:
                a_set = set(all_channel)
                h_set = set()
              #  had_config_channel = control_conf.find({'channel':{'$in':all_channel}},{'channel':1})
              #  for h in had_config_channel:
              #      h_set.add(h['channel'])
                can_set_channel = a_set.difference(h_set)
            w['channels'] = list(can_set_channel)
        elif conf_type == 'limiter':
            can_set_channel = set()
            if all_channel:
                a_set = set(all_channel)
                h_list = []
               # had_limiter_channel = limiter_conf.find({'channels':{'$in':all_channel}},{'channels':1})
               # for h in had_limiter_channel:
               #     h_list.extend(h['channels'])
                can_set_channel = a_set.difference(set(h_list))
                logger.info('CheckUserToRcms[post] len(set(h_list)): %s' % len(set(h_list)))
            w['channels'] = list(can_set_channel)

        self.write(json.dumps(w))


class ConfigChange(tornado.web.RequestHandler):
    '''
    配置更改
    '''

    def get(self, conf_id):

        _conf = control_conf.find_one({'_id': ObjectId(conf_id)})
        named_map = _conf.get('named_map')
        named_str = ''
        if named_map:
            for r in named_map:
                named_str += str(r.get('named')) + ', '
                named_str += str(r.get('locationName')) + ', '
                named_str += str(r.get('namedCycle')) + ', '
                named_str += str(r.get('namedNum')) + ', '
                named_str += str(r.get('namedPeriod'))
                named_str += '\n'
        _conf['named_map_str'] = named_str

        rules_map = _conf.get('rules_map')
        rules_str = ''
        if rules_map:
            for r in rules_map:
                rules_str += str(r.get('theKey')) + ', '
                rules_str += str(r.get('theCycle')) + ', '
                rules_str += str(r.get('theNum')) + ', '
                rules_str += str(r.get('thePeriod'))
                rules_str += '\n'
        _conf['rules_map_str'] = rules_str
        self.render('conf_change.html', conf=_conf)


class ConfigChangeExec(tornado.web.RequestHandler):
    '''
    配置更改执行
    '''

    def post(self):

        _id = self.get_argument('conf_id', '')
        cycle = self.get_argument('cycle', 0)
        num = self.get_argument('num', 0)
        visit_cycle = self.get_argument('visit_cycle', 0)
        visit_num = self.get_argument('visit_num', 0)
        named_str = self.get_argument('named_map')
        rules_str = self.get_argument('rules_map')
        cache_invalid_time = cycle
        add_query_time = self.get_argument('add_query_time')
        all_query_time = self.get_argument('all_query_time')
        # if not cycle:
        #     return self.write(error_res('Please put cycle'))
        # if not num:
        #     return self.write(error_res('Please put num'))
        # if not visit_cycle:
        #     return self.write(error_res('Please put visit_cycle'))
        # if not visit_num:
        #     return self.write(error_res('Please put visit_num'))
        if rules_str:
            for line in rules_str.split('\n'):
                if len(line.split(',')) != 4:
                    return self.write(error_res('Please enter the right rules_map'))
        if named_str:
            for line in named_str.split('\n'):
                if len(line.split(',')) != 5:
                    return self.write(error_res('Please enter the right named_map'))
        # if not cache_invalid_time:
        #     return self.write(error_res('Please put cache_invalid_time'))
        if not add_query_time:
            return self.write(error_res('Please put add_query_time'))
        if not all_query_time:
            return self.write(error_res('Please put all_query_time'))
        cycle = 0 if not cycle else int(cycle)
        num = 0 if not num else int(num)
        visit_cycle = 0 if not visit_cycle else int(visit_cycle)
        visit_num = 0 if not visit_num else int(visit_num)
        cache_invalid_time = 0 if not cache_invalid_time else int(cache_invalid_time)
        add_query_time = int(add_query_time)
        all_query_time = int(all_query_time)
        if named_str:
            named_map = [{'named': i.split(',')[0].strip(), 'locationName': i.split(',')[1].strip(), 'namedCycle': int(i.split(',')[2].strip()), 'namedNum': int(i.split(',')[3].strip()), 'namedPeriod': int(i.split(',')[4].strip())} for i in named_str.split('\n')]
        else:
            named_map = []

        if rules_str:
            rules_map = [{'theKey': i.split(',')[0].strip(), 'theCycle': int(i.split(',')[1].strip()), 'theNum': int(i.split(',')[2].strip()), 'thePeriod': int(i.split(',')[3].strip())} for i in rules_str.split('\n')]
        else:
            rules_map = []

        new_conf = {"cycle": cycle, "num": num, "visit_cycle": visit_cycle,
                    "visit_num": visit_num, "cache_invalid_time": cache_invalid_time,
                    "add_query_time": add_query_time, "all_query_time": all_query_time}
        if rules_map:
            new_conf.update({'rules_map': rules_map})
        if named_map:
            new_conf.update({'named_map': named_map})
        old_conf = control_conf.find_one({'_id': ObjectId(_id)})
        if not old_conf:
            return self.write(error_res('This config had already deleted'))

        try:
            db_update(control_conf, {'_id': ObjectId(_id)}, {'$set': new_conf})
        except Exception:
            logger.info('ConfigChangeExec[post][error]: %s' % (traceback.format_exc(), ))
        else:
            logger.info('ConfigChangeExec[post] channel: %s|| suffix: %s|| category: %s' %
                        (old_conf['channel'], str(old_conf.get('suffix', '')), old_conf['category']))
            makeSthStrInDict(new_conf, 'rules_map')
            makeSthStrInDict(new_conf, 'named_map')
            add_config_cache("%s%s" % (old_conf['channel'], str(old_conf.get('suffix', ''))),
                             old_conf['category'], new_conf)

        self.redirect('/conf')


class ConfigDel(tornado.web.RequestHandler):
    '''
    配置删除
    '''

    def get(self, conf_id):

        info = control_conf.find_one({'_id': ObjectId(conf_id)})
        if not info:
            return self.write(error_res('This config had already deleted'))
        try:
            control_conf.remove({'_id': ObjectId(conf_id)})
        except Exception as e:
            logger.info('ConfigDel[error]: %s' % (traceback.format_exc(e), ))
        else:
            del_config_cache(info['channel'] + info.get('suffix', ''), info['category'])

        self.redirect('/conf')


class LogQuery(tornado.web.RequestHandler):
    '''
    Log结果查询
    '''

    def get(self):

        begin_date, end_date = make_normal_date_range()

        _query = make_date_query(begin_date, end_date)

        res = get_all_conf(col=M_DB.deny_list, query=_query)

        page_list, can_pre_page, can_next_page = pager(res['totalpage'], 0)

        self.render('log.html', begin_date=begin_date, end_date=end_date, channel_id='', old_query_channel='', all_log=res[
                    'all_conf'], totalpage=res['totalpage'], c_page=0, page_list=page_list, can_pre_page=can_pre_page, can_next_page=can_next_page)

    def post(self):

        channel_id = self.get_argument('channel_id', '')
        old_query_channel = self.get_argument('old_query_channel', '')
        if old_query_channel:
            channel_id = old_query_channel
        begin_str = self.get_argument('begin_date')
        end_str = self.get_argument('end_date')
        c_page = int(self.get_argument('c_page', 0))

        _query = make_date_query(begin_str, end_str)
        if not _query:
            return self.write(error_res('begin data or end data is error'))

        if channel_id:
            _query['channel'] = channel_id
        res = get_all_conf(page=c_page, col=M_DB.deny_list, query=_query)

        page_list, can_pre_page, can_next_page = pager(res['totalpage'], c_page)

        self.render('log.html', begin_date=begin_str, end_date=end_str, channel_id=channel_id, old_query_channel=old_query_channel, all_log=res[
                    'all_conf'], totalpage=res['totalpage'], c_page=c_page, page_list=page_list, can_pre_page=can_pre_page, can_next_page=can_next_page)


class LogToExcel(tornado.web.RequestHandler):
    '''
    log生成excel
    '''

    def post(self):

        channel_id = self.get_argument('channel_id', '')
        begin_str = self.get_argument('begin_date')
        end_str = self.get_argument('end_date')

       # logger.info('LogToExcel[post] channel_id: %s' % channel_id)
       # logger.info('LogToExcel[post] begin_str: %s' % begin_str)
       # logger.info('LogToExcel[post] end_str: %s' % end_str)

       # if not channel_id:
       #     raise

        _query = make_date_query(begin_str, end_str)

        if not _query:
            return self.write(error_res('begin data or end data is error'))

        if channel_id:
            _query['channel'] = channel_id

        res = M_DB.deny_list.find(_query).sort('created_time', DESCENDING)

        if res.count() == 0:
            return self.write(error_res('no query data'))

        sheet_name = channel_id if channel_id else u'all'
        self.set_header('Content-type', 'application/vnd.ms-excel')
        # self.set_header('Transfer-Encoding','chunked')
        self.set_header('Content-Disposition', 'attachment;filename="%s.xls"' % (sheet_name))
        wb = xlwt.Workbook()
        wb.encoding = 'gbk'
        ws = wb.add_sheet(sheet_name)

        title = ['channel', 'URL', 'IPs', 'created_time']

        for r in xrange(res.count() + 1):
            if r == 0:
                for x in xrange(4):
                    ws.write(r, x, title[x])
            else:
                for x in xrange(4):
                    _data = res[r - 1][title[x]]
                    if title[x] == 'IPs':
                        _data = '&'.join(_data)
                    elif title[x] == 'created_time':
                        _data = _data.strftime('%Y-%m-%d %H:%M:%S')
                    ws.write(r, x, _data)

        sio = StringIO.StringIO()
        wb.save(sio)
        self.write(sio.getvalue())


class LimiterConfigTop(tornado.web.RequestHandler):
    '''
    限速配置首页
    '''

    def get(self):

        res = get_all_conf(col=limiter_conf)
        logger.info('LimiterConfigTop[get] res: %s' % res)
        for k, v in res.items():
            if k == 'all_conf':
                for line in v:
                    line['category'] = analysis_directions(line['category'])
        self.render('limiter_conf.html', query_id='', all_conf=res[
                    'all_conf'], totalpage=res['totalpage'], c_page=0)

    def post(self):

        query = {}
        query_id = self.get_argument('query_id', '')
        logger.info('LimiterConfigTop[post] query_id: %s' % query_id)
        if query_id:
            query = {'$or': [{'user': query_id}, {'channel': query_id}]}
        c_page = int(self.get_argument('c_page', 0))
        res = get_all_conf(c_page, query, col=limiter_conf)
        for k, v in res.items():
            if k == 'all_conf':
                for line in v:
                    line['category'] = analysis_directions(line['category'])

        self.render('limiter_conf.html', query_id=query_id, all_conf=res[
                    'all_conf'], totalpage=res['totalpage'], c_page=c_page)


class LimiterConfigAdd(tornado.web.RequestHandler):
    '''
    限速配置添加
    '''

    def get(self):

        self.render('limiter_conf_add.html')

    def post(self):
        category = self.get_argument('hidden_direction')
        logger.info("LimiterConfigAdd[post] all_directions: %s" % category)
        category = category.encode("utf-8")
        user = self.get_argument('user', '')
        # logger.info('LimiterConfigAdd[post] user: %s' % user)
        channels = self.get_arguments('box_channels')
        # logger.info('LimiterConfigAdd[post] channel: %s' % channel)
        # logger.info('LimiterConfigAdd[post] cycle: %s' % cycle)

        num = self.get_argument('num').encode("utf-8")

        Bbase = float(self.get_argument('bbase', 170))
        Balarm = float(self.get_argument('balarm', 0.75))
        Bhard = float(self.get_argument('bhard', 1))
        Bgrade = int(self.get_argument('bgrade', 1))
        Bpolice = float(self.get_argument('bpolice', 1.2))
        if not category:
            return self.write(error_res('Please put category'))
        if not user:
            return self.write(error_res('Please put user'))
        if not num:
            return self.write(error_res('Please put num'))
        if float(num) < 0 or float(num) > 500:
            return self.write(error_res('Rate must be in 0, 500'))

        num = float(num) * 1024

        logger.info('LimiterConfigAdd[post] num: %s' % num)

        is_had = limiter_conf.find({'user': user, 'category': category,
                                    'channels': {'$in': channels}}).count()
        if is_had > 0:
            return self.write(error_res('This config had already added'))

        insert_id = limiter_conf.insert({'user': user, 'channels': channels, 'rate': float(num), 'category': category, 'Bbase': Bbase,
                                         'Balarm': Balarm, 'Bhard': Bhard, 'Bgrade': Bgrade, 'Bpolice': Bpolice, 'created_time': datetime.datetime.now()})
        logger.info('LimiterConfigAdd[post] insert_id: %s' % insert_id)
        add_limiter_cache(channels, category, {'rate': float(num), '_id': str(
            insert_id), 'category': category, 'user': user, 'Bbase': Bbase, 'Balarm': Balarm, 'Bhard': Bhard, 'Bgrade': Bgrade, 'Bpolice': Bpolice})
        self.redirect('/limiter_conf')


class LimiterConfigDel(tornado.web.RequestHandler):
    '''
    限速配置删除
    '''

    def get(self, conf_id):

        info = limiter_conf.find_one({'_id': ObjectId(conf_id)})
        if not info:
            return self.write(error_res('This config had already deleted'))
        try:
            limiter_conf.remove({'_id': ObjectId(conf_id)})
        except Exception as e:
            logger.info('LimiterConfigDel[get][error]: %s' % (traceback.format_exc(e), ))
        else:
            del_limiter_cache(info['channels'], info['category'])

        self.redirect('/limiter_conf')


class LimiterConfigChange(tornado.web.RequestHandler):
    '''
    限速配置更改
    '''

    def get(self, conf_id):

        _conf = limiter_conf.find_one({'_id': ObjectId(conf_id)})
        user = _conf['user']
        try:
            req = urllib2.Request(RCMS_API % (user))
            rcms_res = urllib2.urlopen(req, timeout=2)
            res_data = rcms_res.read()
            res_obj = json.loads(res_data)
            all_channel = [i['name'] for i in res_obj]

            a_set = set(all_channel)
            h_list = []
            had_limiter_channel = limiter_conf.find(
                {'channels': {'$in': all_channel}}, {'channels': 1})
            for h in had_limiter_channel:
                h_list.extend(h['channels'])
            can_set_channel = a_set.difference(set(h_list))

            logger.info(
                'LimiterConfigChange[get] limiter_conf len had_channel: %s' % len(set(h_list)))
            can_set_channel_l = list(can_set_channel)
            logger.info('LimiterConfigChange[get] limiter_conf len can_set_channel_l: %s' % len(
                can_set_channel_l))
            can_set_channel_l.extend(_conf['channels'])
            logger.info('LimiterConfigChange[get] limiter_conf len had_channel all: %s' % len(
                can_set_channel_l))
            can_set_channel_l.reverse()
        except Exception as e:
            logger.info('LimiterConfigChange[get][error]: %s' % (traceback.format_exc(e), ))
        logger.info("LimiterConfigChange[get] category: %s" % _conf['category'])
        _conf['category_old'] = _conf['category'].encode("utf-8")
        logger.info('LimiterConfigChange[get] category_old: %s' % _conf['category_old'])
        for k, v in _conf.items():
            if k == "category":
                _conf['category'] = analysis_directions(_conf['category'])
        self.render('limiter_conf_change.html', conf=_conf, all_channel=can_set_channel_l)


class LimiterConfigChangeExec(tornado.web.RequestHandler):
    '''
    限速配置更改执行
    '''

    def post(self):

        conf_id = self.get_argument('conf_id')
        old_category = self.get_argument('old_category')
        category = self.get_argument('hidden_direction_c')
        logger.info("LimiterConfigChangeExec [post] category: %s" % category)
        old_channels = self.get_argument('old_channels')
        old_channels = old_channels.split(',')
        new_channels = self.get_arguments('box_channels')
        rate = float(self.get_argument('rate', 0.0))
        Bbase = float(self.get_argument('bbase', 170))
        Balarm = float(self.get_argument('balarm', 0.75))
        Bhard = float(self.get_argument('bhard', 1))
        Bgrade = int(self.get_argument('bgrade', 1))
        Bpolice = float(self.get_argument('bpolice', 1))
        if rate < 0:
            return self.write(error_res('Rate must be in 0, 500'))
        if rate > 500:
            return self.write(error_res('Rate must be in 0, 500'))

        # 单位换算 前台为Gb
        rate *= 1024

        if not new_channels:
            return self.write(error_res('Please check channel'))

        limiter_conf.update({"_id": ObjectId(conf_id)}, {'$set': {'channels': new_channels, 'category': category,
                                                                  'rate': rate, 'Bbase': Bbase, 'Balarm': Balarm, 'Bhard': Bhard, 'Bgrade': Bgrade, 'Bpolice': Bpolice}})
        # 删除旧缓存
        logger.info("LimiterConfigChangeExec [post] old_channels: %s|| old_category: %s" % (
            old_channels, old_category))
        had_limiter_user = limiter_conf.find({"_id": ObjectId(conf_id)}, {'user': 1})
        user = ""
        for h in had_limiter_user:
            user = h['user']
        del_limiter_cache(old_channels, old_category)
        # 新添缓存
        add_limiter_cache(new_channels, category, {'rate': rate, '_id': str(
            conf_id), 'category': category, 'user': user, 'Bbase': Bbase, 'Balarm': Balarm, 'Bhard': Bhard, 'Bgrade': Bgrade, 'Bpolice': Bpolice})
        self.redirect('/limiter_conf')


class Receiver(tornado.web.RequestHandler):
    '''
    /接收任务
    '''

    def get(self):
        logger.info("Receiver[get] request: %s" % (self.request, ))

    def post(self):
        try:
            logger.info("Receiver[post] request: %s" % self.request)
            data = json.loads(self.request.body)
            # data: {'BGP-BJ-Mhttp://musicfile.baidu.com': 500}
            message = {}
            if not data:
                message['error_type'] = 'null data'
                message['code'] = 201
                return json.loads(message)
            # report_data(data) # ...
            response = report_data(data)
            logger.info('Receiver[post] response: %s' % (response, ))
            self.write(response)
        except Exception as e:
            logger.error("Receiver[error]: %s" % (traceback.format_exc(e), ))


class LimiterPublicConfig(tornado.web.RequestHandler):
    '''
    公共参数配置页面
    '''

    def get(self):
        res = get_all_conf(col=limiter_public_conf)
        logger.info('LimiterPublicConfig[get] res: %s' % res)
        self.render('limiter_public_conf.html', all_conf=res['all_conf'])
        # 这里缓存有问题，数据确实已经改了，但是页面没有显示出来,需要理解一下tornado中缓存的问题


class LimiterPublicConfigC(tornado.web.RequestHandler):

    def post(self):
        limiter_id = self.get_argument('limiter_id')
        limiter_c1 = self.get_argument('limiter_c1')
        limiter_c2 = self.get_argument('limiter_c2')
        limiter_ttl = self.get_argument('limiter_ttl')
        logger.info("LimiterPublicConfigC[post] limiter_c1: %s|| limiter_c2: %s|| limiter_ttl: %s" % (
            limiter_c1, limiter_c2, limiter_ttl))
        if not limiter_c1:
            return self.write(error_res('Please put C1'))
        if not limiter_c2:
            return self.write(error_res('Please put C2'))
        if not limiter_ttl:
            return self.write(error_res('Please put TTL'))
        limiter_public_conf.update({"_id": ObjectId(limiter_id)}, {
                                   '$set': {'C1': limiter_c1, 'C2': limiter_c2, 'TTL': limiter_ttl}})
        self.redirect('/limiter_conf/public_param')


def make_app():
    return tornado.web.Application([
        (r"/", Index),
        (r"/conf", ConfigTop),
        (r"/conf/add", ConfigAdd),
        (r"/conf/del/([a-zA-Z0-9]+)", ConfigDel),
        (r"/conf/change/([a-zA-Z0-9]+)", ConfigChange),
        (r"/conf/exec", ConfigChangeExec),
        (r"/check/user/rcms", CheckUserToRcms),
        (r"/log", LogQuery),
        (r"/log/excel", LogToExcel),
        (r"/limiter_conf", LimiterConfigTop),
        (r"/limiter_conf/add", LimiterConfigAdd),
        (r"/limiter_conf/del/([a-zA-Z0-9]+)", LimiterConfigDel),
        (r"/limiter_conf/change/([a-zA-Z0-9]+)", LimiterConfigChange),
        (r"/limiter_conf/exec", LimiterConfigChangeExec),
        (r"/limiter_conf/public_param", LimiterPublicConfig),
        (r"/limiter_public_conf/change", LimiterPublicConfigC),
        (r"/receiver", Receiver),
    ], **settings)


def run(port):
    app = make_app()
    app.listen(port)
    tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":

    define('port', default=9999, help='run on this port', type=int)
    tornado.options.parse_command_line()
    run(options.port)
