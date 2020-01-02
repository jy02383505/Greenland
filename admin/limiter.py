# -*- coding: utf-8 -*-
from settings import M_DB, REDIS_CONNECT_0
import tornado.ioloop
import tornado.web
import traceback
import json
from send_email import *
from mongo import find_group
from maths import variance, sum, sum_list, judge_direction, rate_param, delete_in_out
from logutil import logger

CHANNEL_DEV = '%s_%s'
C1 = 0.7
C2 = 0.3
CACHE_TTL = 2000


def update_statistics(group, channel, dev, rate, category):
    key = CHANNEL_DEV % (channel, dev)
    REDIS_CONNECT_0.sadd(group, key)

    data = REDIS_CONNECT_0.get(key)
    '''
    rate: {'e4': 0, 'e1': 0, 'e3': 0, 'e2': 0}
    key: 'http://download.52xuexi.net_CHN-JP-b'
    ---(2018-06-29 18:25:48.612896)data---
    b'{"current": {"e4": 0.0, "e1": 0.0, "e3": 0.0, "e2": 0.0}, "variance": {"e4": 0.0, "e1": 0.0, "e3": 0.0, "e2": 0.0}, "previous": {"e4": [0.0, 0.0], "e1": [0.0, 0.0], "e3": [0.0, 0.0], "e2": [0.0, 0.0]}}'
    '''
    logger.info("update_statistics [before data]: %s" % data)
    need_data = {}
    e_dict = {}
    count = 2
    category_list = delete_in_out(category)
    logger.info("update_statistics [directions category_list]: %s" % category_list)
    if data:
        data = json.loads(data)
        for k, v in data.items():
            if k == 'previous':
                for line in category_list:
                    v[line][1] = v[line][0]
                    v[line][0] = data["current"][line]
                    current_init = C1 * v[line][0] + C2 * v[line][1]
                    # 修改current的值
                    if line in rate.keys():
                        if rate[line] == '': # 什么时候是空字符串?初始化?
                            data["current"][line] = current_init # 0.7的当前带宽+0.3的上一次
                            e_dict[line] = current_init
                        else:
                            data["current"][line] = float(rate[line])
                            e_dict[line] = float(rate[line])
                    else:
                        data["current"][line] = current_init
    else:
        data = {}
        data["current"] = {}
        data["previous"] = {}
        index = 0
        # 计算current
        for i in range(1, 5):
            every_previous_dict = {}
            direction_index = "e%s" % i
            if direction_index in rate.keys():
                if rate[direction_index] == "":
                    data["current"][direction_index] = 0.0
                    data["previous"][direction_index] = [0.0, 0.0]
                else:
                    data["current"][direction_index] = float(rate[direction_index])
                    data["previous"][direction_index] = [float(rate[direction_index]), float(rate[direction_index])]
            else:
                data["current"][direction_index] = 0.0
                data["previous"][direction_index] = [0.0, 0.0]
            if direction_index in category_list:
                e_dict[direction_index] = data["current"][direction_index]
    logger.info("update_statistics [after] data: %s" % data)
    need_data["current"] = e_dict
    variance_data = variance(data["previous"], category_list)
    data["variance"] = variance_data
    need_data["variance"] = variance_data
    logger.info("update_statistics need_data: %s" % need_data)
    REDIS_CONNECT_0.set(key, json.dumps(data))
    REDIS_CONNECT_0.expire(key, CACHE_TTL)
    return need_data


def collect_dataset(group):
    # 首先判断限速方向，下层13方向为一组，24方向为一组，一组出现一个就比较大小取最大的为最终的和.最终sum计算出来都是一个值
    # 所有设备当前速率的集合
    current_set = []
    # 所有设备历史速率方差的集合
    variance_set = []
    for line_group in group:
        every_current_set = []
        every_variance_set = []
        group_data = REDIS_CONNECT_0.smembers(line_group)
        # logger.info("group_data: %s" % group_data)
        for line in group_data:
            node = REDIS_CONNECT_0.get(line)
            if node != None:
                every_current_set.append(json.loads(node)['current'])
                every_variance_set.append(json.loads(node)['variance'])
        current_set.append(every_current_set)
        variance_set.append(every_variance_set)
    # logger.info("current_set: %s, variance_set: %s" % (current_set, variance_set, ))
    return current_set, variance_set


# 校验频道的配置是否正确
def check_report_key(key):
    if 'http' in key:
        dev = key[0:key.index('http')]
        if not dev:
            return None, None, None, None, None, None, None, None, None, None, None,
    else:
        return None, None, None, None, None, None, None, None, None, None, None,
    channel = key[key.index('http'):]
    group, rate, category, user, Bbase, Balarm, Bhard, Bgrade, Bpolice = find_group(channel)
    logger.info("check_report_key group: %s|| rate: %s" % (group, rate))
    if not group or not rate or not category or not user:
        logger.info("check_report_key [channel not found.]: %s" % channel)
        return None, None, None, None, None, None, None, None, None, None, None,
    return channel, dev, group, rate, category, user, Bbase, Balarm, Bhard, Bgrade, Bpolice

    # 计算公式如下:
    #                                          x.current               x.variance
    # limit = (x_rate - sum(current)) x (C1 x --------------- + C2 x ------------------) + x.current
    #                                          sum(current)            sum(variance)
    # 其中C1+C2等于1，C1 > C2
    # threshold代表限定阈值，variance是各个节点历史数据的方差
    # x.current和x.variance分别代表当前节点正在使用的带宽和历史数据的方差


def calcute_limit(x_rate, x_current, x_variance, sum_current, sum_variance, x_channel, x_Bbase, x_Bgrade):
    limit_dict = {}
    x_current_len = len(x_current)
    for line in range(x_current_len):
        every_limit_dict = {}
        for k, v in x_current[line].items():
            logger.info("calcute_limit k: %s|| v: %s" % (k, v))
            limit = ''
            if v == 0:
                every_limit_dict[k] = 1
            elif sum_current[line] == 0:
                every_limit_dict[k] = v
            elif sum_variance[line] == 0:
                limit = (x_rate[line] - sum_current[line])
                logger.info("calcute_limit [step1 x_rate[line] - sum_current[line]] limit: %s" % limit)
                limit = limit * (C1 * v / sum_current[line])
                logger.info("calcute_limit [step2 limit * (C1 * x_current / sum_current[line])] limit: %s" % limit)
                limit = limit + v
                logger.info("calcute_limit [step3 limit + x_current] limit: %s" % limit)
                if limit <= 0:
                    limit = 1
                every_limit_dict[k] = limit
            else:
                limit = (x_rate[line] - sum_current[line])
                logger.info("calcute_limit [step1 x_rate - sum_current] limit: %s" % limit)
                logger.info("calcute_limit v: %s|| line: %s|| k: %s" % (v, line, k, ))
                limit = limit * \
                    (C1 * v / sum_current[line] + C2 *
                     x_variance[line][k] / sum_variance[line])
                logger.info("calcute_limit [step2 limit * (C1 * x_current / sum_current + C2 * x_variance / sum_variance)] limit: %s" % limit)
                limit = limit + v
                logger.info("calcute_limit [step3 limit + x_current] limit: %s" % limit)
                if limit <= 0:
                    limit = 1
                every_limit_dict[k] = limit
        every_limit_dict["Bbase"] = x_Bbase[line]
        every_limit_dict["Bgrade"] = x_Bgrade[line]
        limit_dict[x_channel[line]] = every_limit_dict

    logger.info("calcute_limit limit_dict: %s" % (limit_dict, ))
    return limit_dict


def report_data(report):
    logger.info('report_data report: %s' % (report, ))
    # 获取current的带宽和方差
    x_current = []
    x_variance = []
    x_group = []
    x_rate = []
    x_category = []
    x_user = []
    x_channel = []
    x_Bbase = []
    x_Balarm_param = []
    x_Bhard_param = []
    x_Bgrade = []
    x_Bpolice = []
    # report: {'CHN-JP-bhttp://download.52xuexi.net': {'e4': 0, 'e1': 0, 'e3': 0, 'e2': 0}, 'CHN-JP-bhttp://zwtdownload.kyd2002.cn': {'e4': 0, 'e1': 0, 'e3': 0, 'e2': 0}}
    for k, r in report.items():
        # logger.info("report_data key: %s|| value: %s" % (k, r))
        node = ''
        c, d, g, t, cg, u, Bbase, Balarm, Bhard, Bgrade, Bpolice = check_report_key(k)
        logger.info("report_data c: %s|| d: %s|| g: %s|| t: %s|| cg: %s|| u: %s" % (c, d, g, t, cg, u))
        '''
        ---(2018-06-29 16:15:31.964469)cache---
        b'{"category": "e1,e2,e3,e4", "rate": 800.0, "Bpolice": 1.2, "user": "hwapu", "Bhard": 1.0, "_id": "599ab249d101b441a84bb1a5", "Bbase": 170.0, "Bgrade": 3, "Balarm": 0.75}'
        '''
        if c and d and g and t and cg and u:
            # 是否要对边缘上报上来的数据进行判断，方向是否对应
            if g in x_group:
                # 当一个组内的多个频道指向同一个设备，需要将对应方向的带宽相加
                x_channel[x_group.index(g)] = x_channel[x_group.index(g)] + "," + c
                # logger.info("出现多个同一组多个频道对应同一个设备x_current: %s" %x_current)
                node = update_statistics(g, c, d, r, cg)
                if node:
                    # 将数据合并
                    for k1, v1 in node["current"].items():
                        x_current[x_group.index(g)][k1] = x_current[x_group.index(g)][k1] + v1
                    for k2, v2 in node["variance"].items():
                        x_variance[x_group.index(g)][k2] = x_variance[x_group.index(g)][k2] + v2
            else:
                x_channel.append(c)
                x_group.append(g)
                x_rate.append(t)
                x_category.append(cg)
                x_user.append(u)
                x_Bbase.append(Bbase)
                x_Balarm_param.append(Balarm)
                x_Bhard_param.append(Bhard)
                x_Bgrade.append(Bgrade)
                x_Bpolice.append(Bpolice)
                node = update_statistics(g, c, d, r, cg)
                logger.info('report_data node: %s' % (node, ))
                '''
                {'current': {'e4': 3.2799999999999998, 'e1': 0.0, 'e3': 0.0, 'e2': 0.0}, 'variance': {u'e4': 0.29702499999999993, u'e1': 0.0, u'e3': 0.0, u'e2': 0.0}} 
                '''
                if node:
                    x_current.append(node["current"])
                    x_variance.append(node["variance"])
    if len(x_group) == 0:
        return "all channels do not found group"
    logger.info("report_data x_current: %s|| x_variance: %s|| x_group: %s|| x_rate: %s|| x_category: %s|| x_user: %s|| x_Bbase: %s|| x_Balarm_param: %s|| x_Bhard_param: %s|| x_Bgrade: %s|| x_Bpolice: %s" % (x_current, x_variance, x_group, x_rate, x_category, x_user, x_Bbase, x_Balarm_param, x_Bhard_param, x_Bgrade, x_Bpolice))
    current_set, variance_set = collect_dataset(x_group)
    # 获取所有设备当前速率和历史速率方差
    # 在此处判断总带宽是否包含上层设备，是加入到总的带宽里面，否直接计算警戒值和阀值
    logger.info('report_data: current_set: %s|| variance_set: %s' % (current_set, variance_set))
    sum_current = sum_list(current_set, x_category, x_user, x_group)
    sum_variance = sum_list(variance_set, x_category, x_user, x_group)
    logger.info("report_data sum_current: %s|| sum_variance: %s" % (sum_current, sum_variance))
    # 在此处判断sum_current是否超过了x_rate，超过发告警邮件
    need_alarm_rate = []
    need_alarm_current = []
    need_alarm_user = []
    flag = False
    sum_current_len = len(sum_current)
    for line in range(sum_current_len):
        # 判断sum_current和x_rate的大小，如果超过了rate的1.2倍就发邮件告警,x_Police是参数列表
        if sum_current[line] > x_rate[line] * x_Bpolice[line]:
            flag = True
            need_alarm_rate.append(x_rate[line])
            need_alarm_current.append(sum_current[line])
            need_alarm_user.append(x_user[line])
    if flag:
        get_email_data(need_alarm_rate, need_alarm_current, need_alarm_user)
        # send_rate_email("hu.zhang@chinacache.com",["hu.zhang@chinacache.com"],["hu.zhang@chinacache.com"],["hu.zhang@chinacache.com"],"txt","测试")
    # 计算警戒值和阀值
    x_rate_balarm = rate_param(x_Balarm_param, x_rate)
    balarm = calcute_limit(x_rate_balarm, x_current, x_variance,
                           sum_current, sum_variance, x_channel, x_Bbase, x_Bgrade)
    x_rate_bhard = rate_param(x_Bhard_param, x_rate)
    bhard = calcute_limit(x_rate_bhard, x_current, x_variance,
                          sum_current, sum_variance, x_channel, x_Bbase, x_Bgrade)
    logger.info("report_data x_rate_balarm: %s|| x_rate_bhard: %s|| balarm: %s|| bhard: %s" % (x_rate_balarm, x_rate_bhard, balarm, bhard, ))
    response = {}
    response["balarm"] = balarm
    response["bhard"] = bhard
    response = json.dumps(response)
    logger.info("report_data response: %s" % response)
    '''    
    response: {"bhard": {"http://download.52xuexi.net": {"e1": 1, "Bgrade": 3, "e4": 6.0992844639327783, "Bbase": 170.0, "e3": 6.2007536391723361, "e2": 1}}, "balarm": {"http://download.52xuexi.net": {"e1": 1, "Bgrade": 3, "e4": 4.5999796346288209, "Bbase": 170.0, "e3": 4.6901015372248089, "e2": 1}}}
    '''
    return response
    # 返回数据需要重新思考
