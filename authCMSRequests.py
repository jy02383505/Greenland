#!/usr/bin/env python
# coding: utf-8
# version: 0.0.2
# Date: 2019-04-26

import time
import traceback
from datetime import datetime, timedelta


def get_time():
    return datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S") + ".%s" % datetime.now().microsecond


import json
import redis
import requests
from pymongo import MongoClient, ASCENDING, IndexModel, DESCENDING


# R = redis.Redis(host="223.202.211.239", port=19000, db=0, password="")
R = redis.Redis(host="10.10.225.90", port=19000, db=0, password="")
# M_CONNECT = MongoClient("mongodb://bermuda:bermuda_refresh@223.202.211.233:27017/cc")
M_CONNECT = MongoClient("mongodb://bermuda:bermuda_refresh@10.10.225.13:27017,10.10.225.14:27017/cc?replicaSet=bermuda_auth")
M = M_CONNECT["cc"]
#--- run at 31 for test
EXPIRE_SECONDS = 3600
ALL_CACHE_EXPIRE = 3600 * 24
allNamedDevs = {}
interfaceNum = {}


class GetDevs:

    cList = []

    def __init__(self, url, channel, nMap):
        self.aMap = {}
        self.url = url
        self.nMap = nMap
        self.named = nMap.get('named')
        self.locationName = nMap.get('locationName')
        self.channel = channel
        self.data = self.makeData(nMap.get('named'))
        self.firstHas = False

    def postData(self, data=None):
        if not data:
            data = self.data
        h = {"Content-Type": "application/json"}
        print("(%s)postData data: %s" % (get_time(), data, ))
        countInterfaceUseNum(self.url)
        r = requests.post(self.url, json.dumps(data), headers=h)
        return r.text

    def parseLocations(self, result_str=""):
        if not result_str:
            result_str = self.postData()
        r = json.loads(result_str)
        rCode = r["ROOT"]["BODY"]["RETURN_CODE"]
        if rCode == "0":
            r = r["ROOT"]["BODY"]["OUT_DATA"]
        else:
            print("(%s)parseLocations[CMSinterfaceError.] RETURN_CODE: %s|| r: %s" % (get_time(), rCode, r))

        locations = r.get("locations")
        if not locations:
            print("(%s)parseLocations[error] locations: %s|| data: %s" % (get_time(), locations, self.data, ))
            return
        return locations

    def getDevs(self):
        result_str = self.postData()
        locations = self.parseLocations(result_str)

        if locations is None:
            print("(%s)getDevs[error] locations is None." % (get_time(), ))
            return

        locationList = [i for i in locations if i.get("name") == self.locationName]
        if locationList:
            self.firstHas = True

        if self.firstHas:
            theLocation = locationList[0]

            self.filterA(theLocation)
        else:
            locationList = [i for i in locations if i.get("name") == "default"]
            locationList = [j for j in locationList if j.get("name") == self.locationName]
            if locationList:
                theLocation = locationList[0]
                self.filterA(theLocation)
            else:
                print("(%s)getDevs[error] firstHasNothing and defaultLayerHasNothingToo." % (get_time(), ))
                return

        print("(%s)getDevs Finished." % (get_time(), ))

    def filterA(self, location):
        if location.get("type") == "cname":
            self.cList.extend([i.get("name") for i in location.get("cname")])
        elif location.get("type") == "a":
            self.aMap.update({i.get("devName"): json.dumps({"address": i.get("address"), "devName": i.get("devName"), "channel": self.channel, "nMap": self.nMap}) for i in location.get("vs") if location.get("vs")})
        if self.cList:
            print("(%s)filterA cList: %s" % (get_time(), self.cList, ))
            data = self.makeData(self.cList.pop())
            r_str = self.postData(data)
            locations = self.parseLocations(r_str)
            for l in locations:
                self.filterA(l)

    def makeData(self, named):
        """
        "name": "www.fmprc.gov.cn"
        "name": "wjb.foreign"
        "name": "www.fmprc.gov.cn.ipv6"
        """
        return {
            "ROOT": {
                "BODY": {
                    "BUSI_INFO": {
                        "name": named
                    }
                },
                "HEADER": {}
            }
        }

    def output(self):
        return {"%s_%s_%s" % (self.channel, self.named, self.locationName): self.aMap}


class queryM:

    def __init__(self):
        self.M = M

    def getNamedMap(self):
        r = self.M.control_conf.find({"named_map": {"$exists": True}}, {"user": 1, "named_map": 1, "channel": 1, "_id": 0})
        return [i for i in r if i.get("named_map")]


def main(url):
    result = {}
    q = queryM()
    namedConfList = q.getNamedMap()
    if not namedConfList:
        print("(%s)main namedConfListHasNothing: %s" % (get_time(), namedConfList, ))
        return
    for namedConf in namedConfList:
        named_map_list = namedConf.get("named_map")
        for nMap in named_map_list:
            #--- get device info from CMS.
            d = GetDevs(url, namedConf.get("channel"), nMap)
            d.getDevs()
            result.update(d.output())
    print("(%s)main result: %s" % (get_time(), result, ))
    if result:
        for k, v in result.items():
            if len(v):
                r_hmset = R.hmset(k, v)
                r_expire = R.expire(k, EXPIRE_SECONDS)
                print("(%s)main key: %s|| r_hmset: %s|| r_expireDone(%ss): %s" % (get_time(), k, r_hmset, EXPIRE_SECONDS, r_expire, ))

        # ---gather all devicesInfo
        getAllNamedDevs(result)
    # ---在codis中写入cache到lvs的映射。【先假定cache不重复的情况】
    if allNamedDevs:
        devAll = devInfoAll()

        for devName in allNamedDevs:
            devDict = cachesFromOneLvs(devName, devAll)
            if devDict:
                setCacheInfo(devDict)

    #--- generate channel_devName_"named"
    channelDevMap = {}
    if r_hmset:
        for cnlk, devMap in result.items():
            for kDev, vDev in devMap.items():
                vDev = json.loads(vDev)
                cdk = "%s_%s_named" % (vDev.get("channel"), kDev, )
                vDev["nMap"].update({"devIP": vDev.get("address"), "devName": vDev.get("devName")})
                if channelDevMap.get(cdk) is None:
                    channelDevMap[cdk] = {cnlk: vDev.get("nMap")}
                else:
                    channelDevMap[cdk].update({cnlk: vDev.get("nMap")})
    print("(%s)channelDevMap(len: %s): %s" % (get_time(), len(channelDevMap), channelDevMap, ))
    for tempV in channelDevMap.values():
        for tK, tV in tempV.items():
            tempV[tK] = json.dumps(tV)

    if channelDevMap:
        for kk, vv in channelDevMap.items():
            rr_hmset = R.hmset(kk, vv)
            rr_expire = R.expire(kk, EXPIRE_SECONDS)
            print("(%s)main key: %s|| rr_hmset: %s|| rr_expireDone(%ss): %s" % (get_time(), kk, rr_hmset, EXPIRE_SECONDS, rr_expire, ))
    print("(%s)main finished." % (get_time(), ))


def getAllNamedDevs(result):
    for cnl, devMap in result.items():
        for devName, devInfo in devMap.items():
            devInfo = json.loads(devInfo)
            allNamedDevs[devName] = {}
            allNamedDevs[devName]['devName'] = devName
            allNamedDevs[devName]['address'] = devInfo['address']


def cachesFromOneLvs(lvsName, devAll):
    '''
    [{"lvs_deviceName":"CNC-HQ-b-3S6","lvs_ip":"119.188.140.54","hpc":[{"ipAddr":"119.188.140.51","deviceName":"CNC-HQ-b-3gB"},{"ipAddr":"119.188.140.52","deviceName":"CNC-HQ-b-3gC"},{"ipAddr":"119.188.140.29","deviceName":"CNC-HQ-b-3WM"},{"ipAddr":"119.188.140.28","deviceName":"CNC-HQ-b-3WL"},{"ipAddr":"119.188.140.50","deviceName":"CNC-HQ-b-3gA"}]}]
    '''
    if not devAll:
        print(f'({get_time()})cachesFromOneLvs[interfaceError.] devAll: {devAll}')
        return
    for devInfo in devAll:
        if devInfo['lvs_deviceName'] == lvsName:
            isLvs = False if len(devInfo['hpc']) == 1 else True
            print(f'({get_time()})cachesFromOneLvs[found.] lvsName: {lvsName}|| isLvs: {isLvs}')
            return devInfo
    print(f'({get_time()})cachesFromOneLvs[lvsName({lvsName}) notInDevAll.]')

    return


def devInfoAll():
    url = 'http://cms3-apir.chinacache.com/apir/9160/platForm/qryVipHpcDevs'
    countInterfaceUseNum(url)
    r = requests.get(url)
    dev_all = r.json()
    return dev_all


def setCacheInfo(devDict):
    cachesMap = {}
    if devDict.get('hpc'):
        cachesMap[devDict['lvs_deviceName']] = [cache['deviceName'] for cache in devDict['hpc']]

    # ---set into redis: cache -> lvs
    for lvsName, caches in cachesMap.items():
        for cache in caches:
            cacheName = '%s_cacheName' % cache
            rSet = R.setnx(cacheName, lvsName)
            rExpire = R.expire(cacheName, ALL_CACHE_EXPIRE)
            print('(%s)setCacheInfo[%ssExpireSetDone.] cacheName: %s|| lvsName: %s' % (get_time(), ALL_CACHE_EXPIRE, cacheName, lvsName, ))


def countInterfaceUseNum(url):
    if url not in interfaceNum:
        interfaceNum[url] = 1
    else:
        interfaceNum[url] += 1


if __name__ == "__main__":
    st = time.time()
    # ---------test block begin---------
    # ---准备全量的lvs下对应所有cache数据
    # d = 'HGC-HK-2-D27'
    # d = 'CHN-DU-b-3S3'
    # d = 'NED-AM-1-D14'
    # d = 'XCU-YD-1-3S3'
    # r = cachesFromOneLvs(d)
    # print('\n---(%s)r[type: %s]---\n%s' % (get_time(), type(r), r, ))
    # ---------test block end---------

    # devAll = devInfoAll()
    # print(f'\n---len(devAll)---\n{len(devAll)}')
    # print(f'\n---type(devAll)---\n{type(devAll)}')

    #--- get devicesInfo.
    # url = "http://223.202.75.136:32000/bm-app/apir/9120/rsl/ips" # forTest
    url = "http://cms3-apir.chinacache.com/apir/9120/rsl/ips"
    main(url)

    #---test locations
    # nMap = {'named': 'www.mfa.gov', 'locationName': 'foreign'}
    # gd = GetDevs(url, 'http://www.mfa.gov.cn', nMap)
    # r = gd.postData()
    # print(f'\n---r---\n{r}')

    print("(%s)It takes %s seconds.|| [accessNum for every interface.] interfaceNum: %s" % (get_time(), time.time() - st, interfaceNum, ))
