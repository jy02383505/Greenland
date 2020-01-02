#!/usr/bin/env python
# coding: utf-8

import traceback
from datetime import datetime, timedelta


def get_time():
    return datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S') + '.%s' % datetime.now().microsecond


import time
import subprocess
import redis


now = datetime.strftime(datetime.now(), '%Y-%m-%dT%H%M%S')

fname = '/home/refresh/forAuthPY3/scripts/keys-%s.txt' % now # for 230

logname = '/home/refresh/greenland/logs/receive.log'

ip_filter = "grep 'ProcessKeyData_micro'|grep 'ipKey'|awk '{print $5}'|awk -F '|' '{print $1}'|sort|uniq"
ip_deny_filter = "grep 'ProcessKeyData_micro \[ipCount\$gt\$num\]'|awk '{print $4}'|awk -F '|' '{print $1}'|sort|uniq"
visit_filter = "grep 'ProcessKeyData_micro'|grep 'visit_key'|awk '{print $7}'|awk -F '|' '{print $1}'|sort|uniq"
visit_deny_filter = "grep 'ProcessKeyData_micro\[visit_count\$gt\$visit_num\]'|awk '{print $3}'|awk -F '|' '{print $1}'|sort|uniq"
named_filter = "grep 'ProcessNamedData'|grep 'namedK'|awk '{print $3}'|awk -F '|' '{print $1}'|sort|uniq"
named_deny_filter = "grep 'ProcessNamedData \[nVisitCount\$GT\$namedNum\] denyKey:'|awk '{print $4}'|awk -F '|' '{print $1}'|sort|uniq"
multi_filter = "grep 'ProcessData_multi\[SetNXDone' | awk '{print $5}' | awk -F '|' '{print $1}' | sort | uniq"
multi_deny_filter = "grep 'ProcessData_multi\[denyMulti\]' | awk '{print $11}' | awk -F '\",\"' '{print $1}' | sort | uniq"

R = redis.Redis(host='223.202.211.239', port=19000, db=0, password='', decode_responses=True)


def scanKeys(theFilter, line_num=1000000):
    '''
    ip访问键：
        cat receive.log|grep 'ProcessKeyData_micro ipKey'|awk '{print $3}'|awk -F '|' '{print $1}'|sort|uniq
    ip拒绝键：
        cat receive.log|grep 'ProcessKeyData_micro \[ipCount\$gt\$num\]'|awk '{print $4}'|awk -F '|' '{print $1}'|sort|uniq
    频次访问键：
        cat receive.log|grep 'ProcessKeyData_micro'|grep 'visit_key'|awk '{print $5}'|awk -F '|' '{print $1}'|sort|uniq
    频次拒绝键：
        cat receive.log|grep 'ProcessKeyData_micro\[visit_count\$gt\$visit_num\]'|awk '{print $3}'|awk -F '|' '{print $1}'|sort|uniq
    named访问键：
        cat receive.log|grep 'ProcessNamedData'|grep 'namedK'|awk '{print $15}'|awk -F '|' '{print $1}'|sort|uniq
    named拒绝键：
        cat receive.log|grep 'ProcessNamedData \[nVisitCount\$GT\$namedNum\] denyKey:'|awk '{print $4}'|awk -F '|' '{print $1}'|sort|uniq
    多规则访问键：
        cat receive.log|grep 'ProcessData_multi\[SetNXDone' | awk '{print $5}' | awk -F '|' '{print $1}' | sort | uniq
    多规则拒绝键：
        cat receive.log|grep 'ProcessData_multi\[denyMulti\]' | awk '{print $11}' | awk -F '\",\"' '{print $1}' | sort | uniq
    '''

    cmd = "tail -%s %s | %s" % (line_num, logname, theFilter)
    result = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, encoding='utf-8').stdout.readlines()
    return result


def delKeys(filename):
    print('\n---(%s)delKeys[begin...]---\n%s' % (get_time(), filename))
    deletedNum = 0
    with open(filename) as f:
        line_num = 0
        while True:
            line_num += 1
            line = f.readline()
            line = line.strip()
            theKey = line

            if line == '':
                print(f'\n---({get_time()})line({deletedNum}/{line_num})---\n{line}')
                return 'end...'

            ttl = R.ttl(theKey)

            if ttl != -1:
                continue

            try:

                v = R.get(theKey)
                #---Has no expire time for PY2: ttl is None; PY3: ttl == -1
                # if v and (ttl is None):
                if v:
                    if int(v) > 0:
                        deletedNum += 1
                        print('\n---(%s)deleteProblemOccured---\n%s|| v: %s' % (get_time(), theKey, v, ))
                        r = R.delete(theKey)
                        print('deleteDone(%s): %s' % (theKey, r))

            except redis.ResponseError:
                v = R.hlen(theKey)
                #---Has no expire time for PY2: ttl is None; PY3: ttl == -1
                # "http://atestsc.mot.gov.cn_CNC-GI-3-3W2_deny"
                if v:
                    if int(v) > 0:
                        deletedNum += 1
                        print('\n---(%s)deleteProblemOccured---\n%s|| len: %s' % (get_time(), theKey, v, ))
                        r = R.delete(theKey)
                        print('deleteDone(%s)[_deny]: %s' % (theKey, r))

            except Exception:
                print('\n---(%s)[Error.]theKey(type: %s)---\n%s\n%s' % (get_time(), R.type(theKey), theKey, traceback.format_exc()))
                continue


def main():
    total = {}

    total['ip_keys'] = scanKeys(ip_filter)
    total['ip_deny_keys'] = scanKeys(ip_deny_filter)
    total['visit_keys'] = scanKeys(visit_filter)
    total['visit_deny_keys'] = scanKeys(visit_deny_filter)
    total['named_keys'] = scanKeys(named_filter)
    total['named_deny_keys'] = scanKeys(named_deny_filter)
    total['multi_keys'] = scanKeys(multi_filter)
    total['multi_deny_keys'] = scanKeys(multi_deny_filter)
    # print(f'\n---total---\n{total}')
    with open(fname, 'a') as f:
        for k, v_list in total.items():
            print(f'\n---len({k})---\n{len(v_list)}')
            if v_list:
                f.writelines(v_list)
    print(f'\n{get_time()}main[fileWriteDone.]{fname}\n')
    delKeys(fname)


if __name__ == '__main__':
    st = time.time()
    main()
    print(f"It takes {time.time()-st} seconds.")