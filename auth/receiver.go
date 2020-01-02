// Copyright 2016
//Created by huan.ma on 5/19/2016
// 华数鉴权

package auth

import (
	"context"
	"encoding/json"
	"fmt"
	"html/template"
	"io/ioutil"
	// "reflect"
	// "log"
	ut "Greenland/utils"
	"net"
	"net/http"
	"strings"
	"time"

	// log "github.com/Sirupsen/logrus"
	// log "github.com/omidnikta/logrus"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	// "go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	// "gopkg.in/mgo.v2"
	// "gopkg.in/mgo.v2/bson"
	"strconv"
)

// var redisHost string = "172.16.21.198:6379" //223.202.52.82
var cacheDB int64

//是否发送结果 到边缘
var sendFlag = ut.SendFlag
var IsOldCompatible = ut.IsOldCompatible
var log = ut.Logger

// var uri = ut.URI
// var databaseName = ut.DatabaseName

var M = ut.Mongo
var redisClient = ut.RedisClient

//RequestReportBody 边缘实时汇报参数
type RequestReportBody struct {
	Key     string `json:"key"`
	Device  string `json:"device"`
	URL     string `json:"URL"`
	Channel string `json:"channel"`
	IP      string `json:"IP"`
}

type RWBody struct {
	CacheKey string `json:"cacheKey"`
	Data     string `json:"data"`
}

type ReportBodyMulti struct {
	Device  string            `json:"device"`
	URL     string            `json:"URL"`
	Channel string            `json:"channel"`
	IP      string            `json:"IP"`
	Key     map[string]string `json:"key"`
}

//ChannelConf from mongodb;db.control_conf.ensureIndex({"channel":1,"user":1,"category":1},{"unique":true})
type ChannelConf struct {
	ID             primitive.ObjectID `bson:"_id,omitempty"`
	Num            int                `bson:"num"`
	Category       string             `bson:"category"`
	CreatedTime    time.Time          `bson:"created_time"`
	Channel        string             `bson:"channel"`
	Cycle          int                `bson:"cycle"`
	User           string             `bson:"user"`
	Add_query_time int                `bson:"add_query_time"`
	All_query_time int                `bson:"all_query_time"`
}

//ChannelConf from mongodb;db.control_conf.ensureIndex({"channel":1,"user":1,"category":1},{"unique":true})
type ChannelConfMicro struct {
	ID             primitive.ObjectID       `bson:"_id,omitempty"`
	Num            int                      `bson:"num"`
	Category       string                   `bson:"category"`
	CreatedTime    time.Time                `bson:"created_time"`
	Channel        string                   `bson:"channel"`
	Cycle          int                      `bson:"cycle"`
	User           string                   `bson:"user"`
	Visit_cycle    int                      `bson:"visit_cycle"`
	Visit_num      int                      `bson:"visit_num"`
	Add_query_time int                      `bson:"add_query_time"`
	RulesMap       []map[string]interface{} `bson:"rules_map"`
	NamedMap       []map[string]interface{} `bson:"named_map"`
}

//DenyList is deny history;
//db.deny_list.ensureIndex({"key":1,"IPs":1},{"unique":true}) key的生成时间 可能会在5分钟内多次提交相同的KEY
//db.deny_list.ensureIndex({"channel":1})
//db.deny_list.ensureIndex( { "created_time": -1}, { expireAfterSeconds: 60*60*24*30 })
//db.deny_list.ensureIndex( { "created_time": -1,"channel":1})
type DenyList struct {
	ID              primitive.ObjectID `bson:"_id,omitempty"`
	Key             string             `bson:"key"`
	KeyType         string             `bson:"key_type"`
	URL             string             `bson:"URL"`
	IPs             []string           `bson:"IPs"`
	Channel         string             `bson:"channel"`
	CreateTime      time.Time          `bson:"created_time"`
	User            string             `bson:"user"`
	Visit_count     int                `bson:"visit_count"`
	NamedVisitCount string             `bson:"name_visit_count"`
	DevName         string             `bson:"dev_name"`
	IncrKey         string             `bson:"incr_key"`
}

//RequestChannelBody 获取频道deny key时的参数
type RequestChannelBody struct {
	Channels []string `json:"channels"`
	Device   string   `json:"device"`
}

//ProcessKeyData 获取redis内hash数据 {key IP num},取mongodb数据，判断是否超过限制，超限结果入库
func ProcessKeyData(body RequestReportBody) error {
	result := ChannelConf{}

	channelKey := fmt.Sprintf("%s_security", body.Channel)
	channelNum64, _ := redisClient.HGet(channelKey, "num").Int64()
	channelNum := int(channelNum64)
	cycle64, _ := redisClient.HGet(channelKey, "cycle").Int64()
	cycle := int(cycle64)
	channelPeriod64, _ := redisClient.HGet(channelKey, "add_query_time").Int64()
	channelPeriod := int(channelPeriod64)

	if channelNum == 0 {
		col := M.Collection("control_conf")
		filter := bson.D{{"channel", body.Channel}}
		err := col.FindOne(context.TODO(), filter).Decode(&result)
		if err != nil {
			log.Errorf("ProcessKeyData[mongoError.] err: %v", err)
			return err
		}

		channelNum = result.Num
		cycle = result.Cycle
		channelPeriod = result.Add_query_time
		log.Debugf("ProcessKeyData [fromMongodb] key: %s|| channel: %s|| num: %d|| channelPeriod: %d", body.Key, body.Channel, result.Num, channelPeriod)
	}

	if channelNum == 0 {
		log.Debugf("ProcessKeyData [afterMongodbNumStillZero!] key: %s|| channel: %s|| num: %d", body.Key, body.Channel, result.Num)
		return nil
	}

	ipKey := fmt.Sprintf("%s_%s_netizenIP", body.Channel, body.Key)
	pipe := redisClient.Pipeline()
	ipHIncrCmd := pipe.HIncrBy(ipKey, body.IP, 1)
	ipHLenCmd := pipe.HLen(ipKey)
	ipPTTLCmd := pipe.PTTL(ipKey)
	_, err := pipe.Exec()
	defer pipe.Close()
	if err != nil {
		log.Errorf("ProcessKeyData[pipelineError.] err: %s|| key: %+v|| channelNum: %+v", err, body.Key, channelNum)
		return nil
	}
	ipHIncr, ipHLen, ipPTTL := ipHIncrCmd.Val(), ipHLenCmd.Val(), ipPTTLCmd.Val()
	if ipPTTL == -1 && ipHLen == 1 && ipHIncr == 1 {
		redisClient.Expire(ipKey, time.Duration(cycle)*time.Second)
		log.Infof("ProcessKeyData[expireDone.] key: %+v|| channelNum: %+v|| cycle: %+v|| ipHIncr: %+v|| ipPTTL: %v|| ipHLen: %v", body.Key, channelNum, cycle, ipHIncr, ipPTTL, ipHLen)
	}
	ipCount := redisClient.HLen(ipKey).Val()
	ipPTTL = redisClient.PTTL(ipKey).Val()
	log.Infof("ProcessKeyData key: %v|| ipCount: %v|| channelNum: %v|| cycle: %v|| ipPTTL: %v|| ipHIncr: %v", body.Key, ipCount, channelNum, cycle, ipPTTL, ipHIncr)

	if int(ipCount) > channelNum {
		denyKey := denyAction("ProcessKeyData", body.Channel, body.Device, body.Key, channelPeriod, "deny")
		log.Infof("ProcessKeyData [ipCount$gt$num] denyKey: %s|| ipCount: %d|| num: %d", denyKey, ipCount, result.Num)
		denyNoMongoKey := fmt.Sprintf("%s_noMongo", denyKey)
		canMongo := redisClient.SetNX(denyNoMongoKey, 1, time.Duration(channelPeriod)*time.Second).Val()
		if canMongo {
			go denyToMongo(false, body.Channel, body.Key, 0, body.Device, body.URL, "", ipKey)
		}

		// for old compatibility
		if IsOldCompatible {
			denyKeyNoDev := denyActionNoDev("ProcessKeyData", body.Channel, body.Key, channelPeriod, "deny")
			log.Infof("ProcessKeyData [ipCount$gt$num] denyKeyNoDev: %s|| ipCount: %d|| num: %d", denyKeyNoDev, ipCount, result.Num)
			denyNoMongoKey := fmt.Sprintf("%s_noMongo", denyKeyNoDev)
			canMongo := redisClient.SetNX(denyNoMongoKey, 1, time.Duration(channelPeriod)*time.Second).Val()
			if canMongo {
				go denyToMongo(false, body.Channel, body.Key, 0, body.Device, body.URL, "", ipKey)
			}
		}
		return nil
	}
	return nil
}

type CachesOfLvs struct {
	LvsDeviceName string    `bson:"lvs_deviceName"`
	LvsIp         string    `bson:"lvs_ip"`
	Caches        []string  `bson:"caches"`
	CreatedTime   time.Time `bson:"created_time"`
}

func denyAction(funcName string, channel string, devName string, key string, period int, suffix string) string {
	var denyKey string
	// if suffix == "denyMulti" {
	// 	denyKey = fmt.Sprintf("%s_%s_%s", channel, devName, suffix)
	// } else {
	// 	denyKey = fmt.Sprintf("%s_%s", channel, suffix)
	// }
	if funcName == "ProcessNamedData" {
		denyKey = fmt.Sprintf("%s_%s_%s", channel, devName, suffix)
	} else {
		denyKey = fmt.Sprintf("%s_%s", channel, suffix)
	}
	pipe := redisClient.Pipeline()
	defer pipe.Close()
	valueHIncrCmd := pipe.HIncrBy(denyKey, key, 1)
	denyHLenCmd := pipe.HLen(denyKey)
	denyPTTLCmd := pipe.PTTL(denyKey)
	_, err := pipe.Exec()
	if err != nil {
		log.Errorf("%s[pipelineError: %v] denyKey: %+v", funcName, err, denyKey)
	}
	denyHIncr, denyHLen, denyPTTL := valueHIncrCmd.Val(), denyHLenCmd.Val(), denyPTTLCmd.Val()
	if denyPTTL == -1 && denyHLen == 1 && denyHIncr == 1 {
		redisClient.Expire(denyKey, time.Duration(period)*time.Second)
		log.Infof("%s[expireDone.] key: %s|| denyKey: %+v|| denyPTTL: %v|| denyHIncr: %v|| denyHLen: %v|| period: %v", funcName, key, denyKey, denyPTTL, denyHIncr, denyHLen, period)
	}
	denyPTTL = redisClient.PTTL(denyKey).Val()
	log.Infof("%s key: %s|| denyKey: %+v|| denyPTTL: %v|| denyHIncr: %v", funcName, key, denyKey, denyPTTL, denyHIncr)

	return denyKey
}

// for old compatibility
func denyActionNoDev(funcName string, channel string, key string, period int, suffix string) string {
	denyKeyNoDev := fmt.Sprintf("%s__%s", channel, suffix)

	pipe := redisClient.Pipeline()
	denyNoDevCmd := pipe.HIncrBy(denyKeyNoDev, key, 1)
	denyNoDevHLenCmd := pipe.HLen(denyKeyNoDev)
	denyNoDevPTTLCmd := pipe.PTTL(denyKeyNoDev)
	_, err := pipe.Exec()
	defer pipe.Close()
	if err != nil {
		log.Errorf("%s[pipelineError.] err: %v|| denyKeyNoDev: %+v", funcName, err, denyKeyNoDev)
		return denyKeyNoDev
	}
	denyNoDevHIncr, denyNoDevHLen, denyNoDevPTTL := denyNoDevCmd.Val(), denyNoDevHLenCmd.Val(), denyNoDevPTTLCmd.Val()
	if denyNoDevPTTL == -1 && denyNoDevHLen == 1 && denyNoDevHIncr == 1 {
		redisClient.Expire(denyKeyNoDev, time.Duration(period)*time.Second)
		log.Infof("%s[expireDone.] key: %s|| denyKeyNoDev: %+v|| denyNoDevHIncr: %v|| denyNoDevPTTL: %v|| denyNoDevHLen: %v|| period: %v", funcName, key, denyKeyNoDev, denyNoDevHIncr, denyNoDevPTTL, denyNoDevHLen, period)
	}
	denyNoDevPTTL = redisClient.PTTL(denyKeyNoDev).Val()
	log.Infof("%s key: %s|| denyKeyNoDev: %+v|| denyNoDevHIncr: %v|| denyNoDevPTTL: %v", funcName, key, denyKeyNoDev, denyNoDevHIncr, denyNoDevPTTL)

	return denyKeyNoDev
}

func denyToMongo(noIPs bool, fields ...interface{}) {
	// denyToMongo(noIPs bool, channel string, key string, visit_count int64, devName string, url string, keyType string, incrKey string)
	var ips []string
	if !noIPs {
		netizenIPKey := fmt.Sprintf("%s_%s_netizenIP", fields[0], fields[1])
		ips = redisClient.HKeys(netizenIPKey).Val()
	}
	tt := time.Now().Add(time.Hour * 8)

	dl := DenyList{Key: fields[1].(string), URL: fields[4].(string), CreateTime: tt, IPs: ips, Channel: fields[0].(string), Visit_count: int(fields[2].(int64)), DevName: fields[3].(string), KeyType: fields[5].(string), IncrKey: fields[6].(string)}
	col := M.Collection("deny_list")
	insertResult, err := col.InsertOne(context.TODO(), dl)
	if err != nil {
		log.Errorf("denyToMongo[insertError.] err: %v|| channel: %v|| key: %+v|| visit_count: %d|| devName: %s|| url: %s|| keyType: %+v|| incrKey: %+v", err, fields[0], fields[1], fields[2], fields[3], fields[4], fields[5], fields[6])
		return
	}
	log.Infof("denyToMongo[mongodbInsertDone.] channel: %s|| key: %s|| visit_count: %d|| devName: %s|| url: %s|| keyType: %+v|| incrKey: %+v|| insertID: %v", fields[0], fields[1], fields[2], fields[3], fields[4], fields[5], fields[6], insertResult.InsertedID)
	return
}

//ProcessKeyData_micro 获取redis内hash数据 {key IP num},取mongodb数据，判断是否超过限制，超限结果入库
func ProcessKeyData_micro(body RequestReportBody) error {
	channelKey := fmt.Sprintf("%s_security", body.Channel)
	channelConf := redisClient.HGetAll(channelKey).Val()
	log.Debugf("ProcessKeyData_micro channelConf: %+v|| channelKey: %v", channelConf, channelKey)
	visit_period, _ := strconv.Atoi(channelConf["add_query_time"])
	visit_cycle, _ := strconv.Atoi(channelConf["visit_cycle"])
	visit_num, _ := strconv.Atoi(channelConf["visit_num"])
	num, _ := strconv.Atoi(channelConf["num"])
	cycle, _ := strconv.Atoi(channelConf["cycle"])

	if visit_num == 0 && num == 0 {
		result := ChannelConfMicro{}
		col := M.Collection("control_conf")
		err := col.FindOne(context.TODO(), bson.D{{"channel", body.Channel}}).Decode(&result)
		if err != nil {
			log.Errorf("ProcessKeyData_micro[findError.] err: %s|| key: %s|| channel: %+v", err, body.Key, body.Channel)
		}
		// query := func(c *mgo.Collection) error {
		// 	errFind := c.Find(bson.M{"channel": body.Channel}).One(&result)
		// 	if errFind != nil {
		// 		log.Errorf("ProcessKeyData_micro[errFind: %s] key: %s|| channel: %+v", errFind, body.Key, body.Channel)
		// 	}
		// 	return errFind
		// }
		// withCollection("control_conf", query)
		visit_period = result.Add_query_time
		visit_cycle = result.Visit_cycle
		visit_num = result.Visit_num
		num = result.Num
		cycle = result.Cycle
		log.Infof("ProcessKeyData_micro[fromMongodb] key: %s|| channel: %+v|| visit_period: %+v|| visit_cycle: %+v|| visit_num: %+v", body.Key, body.Channel, visit_period, visit_cycle, visit_num)
	}
	if visit_num == 0 && num == 0 {
		log.Errorf("ProcessKeyData_micro[afterVisitNumStillZero key: %+v] channel: %+v|| visit_period: %+v|| visit_cycle: %+v|| visit_num: %+v", body.Key, body.Channel, visit_period, visit_cycle, visit_num)
		return nil
	}

	var visit_count int64
	// visit control
	if visit_cycle != 0 && visit_num != 0 {
		visit_key := fmt.Sprintf("%s_%s_visit", body.Channel, body.Key)

		pipe := redisClient.Pipeline()
		vCountCmd := pipe.Incr(visit_key)
		vPTTLCmd := pipe.PTTL(visit_key)
		_, err := pipe.Exec()
		defer pipe.Close()
		if err != nil {
			log.Errorf("ProcessKeyData_micro[pipelinedError: %s] visit_key: %+v", err, visit_key)
			return nil
		}
		visit_count, vPTTL := vCountCmd.Val(), vPTTLCmd.Val()
		if vPTTL == -1 && visit_count == 1 {
			redisClient.Expire(visit_key, time.Duration(visit_cycle)*time.Second)
			log.Infof("ProcessKeyData_micro[visitExpireDone.] expire: %vs|| visit_count: %v|| vPTTL: %v|| visit_key: %s", visit_cycle, visit_count, vPTTL, visit_key)
		}
		vPTTL = redisClient.PTTL(visit_key).Val()
		log.Infof("ProcessKeyData_micro visit_count: %v|| vPTTL: %v|| visit_key: %s|| visit_cycle: %v", visit_count, vPTTL, visit_key, visit_cycle)

		if int(visit_count) > visit_num {
			denyKey := denyAction("ProcessKeyData_micro", body.Channel, body.Device, body.Key, visit_period, "deny")
			log.Infof("ProcessKeyData_micro[visit_count$gt$visit_num] denyKey: %s|| visit_count: %d|| visit_num: %d", denyKey, visit_count, visit_num)
			denyNoMongoKey := fmt.Sprintf("%s_noMongo", denyKey)
			canMongo := redisClient.SetNX(denyNoMongoKey, 1, time.Duration(visit_period)*time.Second).Val()
			if canMongo {
				go denyToMongo(false, body.Channel, body.Key, visit_count, body.Device, body.URL, "", visit_key)
			}

			// for old compatibility
			if IsOldCompatible {
				denyKeyNoDev := denyActionNoDev("ProcessKeyData_micro", body.Channel, body.Key, visit_period, "deny")
				log.Infof("ProcessKeyData_micro[visit_count$gt$visit_num] denyKeyNoDev: %s|| visit_count: %d|| visit_num: %d", denyKeyNoDev, visit_count, visit_num)
				denyNoMongoKey := fmt.Sprintf("%s_noMongo", denyKeyNoDev)
				canMongo := redisClient.SetNX(denyNoMongoKey, 1, time.Duration(visit_period)*time.Second).Val()
				if canMongo {
					go denyToMongo(false, body.Channel, body.Key, visit_count, body.Device, body.URL, "", visit_key)
				}
			}
			return nil
		}
	}

	// skip the ip control
	if num == 0 && cycle == 0 {
		return nil
	}
	// ---netizenIP control
	ipKey := fmt.Sprintf("%s_%s_netizenIP", body.Channel, body.Key)

	pipe := redisClient.Pipeline()
	defer pipe.Close()
	valueIPCmd := pipe.HIncrBy(ipKey, body.IP, 1)
	ipCountCmd := pipe.HLen(ipKey)
	ipPTTLCmd := pipe.PTTL(ipKey)
	_, err := pipe.Exec()
	if err != nil {
		log.Errorf("ProcessKeyData_micro[pipelinedError: %s] ipKey: %+v", err, ipKey)
		return nil
	}
	valueIP, ipCount, ipPTTL := valueIPCmd.Val(), ipCountCmd.Val(), ipPTTLCmd.Val()

	// expire check...
	if ipPTTL == -1 && valueIP == 1 && ipCount == 1 {
		redisClient.Expire(ipKey, time.Duration(cycle)*time.Second)
		log.Infof("ProcessKeyData_micro[IPExpireDone.] valueIP: %v|| ipCount: %v|| ipPTTL: %v|| ipKey: %+v|| IP: %+v|| cycle: %v", valueIP, ipCount, ipPTTL, ipKey, body.IP, cycle)
	}
	ipPTTL = redisClient.PTTL(ipKey).Val()
	log.Infof("ProcessKeyData_micro ipPTTL: %v|| ipKey: %+v|| IP: %+v|| valueIP: %v|| ipCount: %v|| cycle: %v", ipPTTL, ipKey, body.IP, valueIP, ipCount, cycle)

	if int(ipCount) > num {
		denyKey := denyAction("ProcessKeyData_micro", body.Channel, body.Device, body.Key, visit_period, "deny")
		log.Infof("ProcessKeyData_micro[ipCount$gt$num] denyKey: %s|| ipCount: %d|| num: %d", denyKey, ipCount, num)
		denyNoMongoKey := fmt.Sprintf("%s_noMongo", denyKey)
		canMongo := redisClient.SetNX(denyNoMongoKey, 1, time.Duration(visit_period)*time.Second).Val()
		if canMongo {
			go denyToMongo(false, body.Channel, body.Key, visit_count, body.Device, body.URL, "", ipKey)
		}

		// for old compatibility
		if IsOldCompatible {
			denyKeyNoDev := denyActionNoDev("ProcessKeyData_micro", body.Channel, body.Key, visit_period, "deny")
			log.Infof("ProcessKeyData_micro[ipCount$gt$num] denyKeyNoDev: %s|| ipCount: %d|| num: %d", denyKeyNoDev, ipCount, num)
			denyNoMongoKey := fmt.Sprintf("%s_noMongo", denyKeyNoDev)
			canMongo := redisClient.SetNX(denyNoMongoKey, 1, time.Duration(visit_period)*time.Second).Val()
			if canMongo {
				go denyToMongo(false, body.Channel, body.Key, visit_count, body.Device, body.URL, "", ipKey)
			}
		}
		return nil
	}
	return nil
}

func ProcessNamedData(cnlConf string, body RequestReportBody) error {
	// result := ChannelConfMicro{}

	//--- for named_map
	named_map := map[string]interface{}{}
	json_err := json.Unmarshal([]byte(cnlConf), &named_map)
	if json_err != nil {
		log.Errorf("ProcessNamedData json_error: %s", json_err)
		return nil
	}
	if len(named_map) == 0 {
		log.Errorf("ProcessNamedData named_map is empty.")
		return nil
	}

	namedCycle64 := named_map["namedCycle"].(float64)
	namedCycle := int(namedCycle64)
	namedNum64 := named_map["namedNum"].(float64)
	namedNum := int(namedNum64)
	namedPeriod64 := named_map["namedPeriod"].(float64)
	namedPeriod := int(namedPeriod64)
	namedK := fmt.Sprintf("%s_%s_%s_%s_nVisit", body.Channel, named_map["named"], named_map["locationName"], body.Key)

	pipe := redisClient.Pipeline()
	nvCmd := pipe.Incr(namedK)
	nvPTTLCmd := pipe.PTTL(namedK)
	_, err := pipe.Exec()
	defer pipe.Close()
	if err != nil {
		log.Errorf("ProcessNamedData[pipelinedError: %s] channel: %+v|| key: %+v|| namedK: %+v|| named_map: %+v", err, body.Channel, body.Key, namedK, named_map)
		return nil
	}
	nVisitCount, nvPTTL := nvCmd.Val(), nvPTTLCmd.Val()
	if nvPTTL == -1 && nVisitCount == 1 {
		redisClient.Expire(namedK, time.Duration(namedCycle)*time.Second)
		log.Infof("ProcessNamedData[nVisitExpireDone.] expire: %vs|| nvPTTL: %s|| nVisitCount: %d|| namedK: %d", namedCycle, nvPTTL, nVisitCount, namedK)
	}
	nvPTTL = pipe.PTTL(namedK).Val()
	log.Infof("ProcessNamedData namedK: %s|| expire: %vs|| nvPTTL: %s|| nVisitCount: %d", namedK, namedCycle, nvPTTL, nVisitCount)

	if int(nVisitCount) > namedNum {
		denyKey := denyAction("ProcessNamedData", body.Channel, body.Device, body.Key, namedPeriod, "deny")
		log.Infof("ProcessNamedData[nVisitCount$GT$namedNum] denyKey: %s|| nVisitCount: %d|| namedNum: %d", denyKey, nVisitCount, namedNum)
		denyNoMongoKey := fmt.Sprintf("%s_noMongo", denyKey)
		canMongo := redisClient.SetNX(denyNoMongoKey, 1, time.Duration(namedPeriod)*time.Second).Val()
		if canMongo {
			go denyToMongo(true, body.Channel, body.Key, nVisitCount, body.Device, body.URL, "", namedK)
		}
		return nil
	}

	return nil
}

func (body *RequestReportBody) ReplaceDevice() {
	if (*body).Device == "" {
		return
	}
	devK := fmt.Sprintf("%s_cacheName", (*body).Device)
	newDevice := redisClient.Get(devK).Val()
	if newDevice != "" {
		log.Infof("ReplaceDevice[*RequestReportBody.] devK: %s|| newDevice: %s|| body: %+v", devK, newDevice, *body)
		(*body).Device = newDevice
	}
	log.Infof("ReplaceDevice[*RequestReportBody after.] devK: %s|| newDevice: %s|| body: %+v", devK, newDevice, *body)
	return
}

func (body *RequestChannelBody) ReplaceDevice() {
	if body.Device == "" {
		return
	}
	devK := fmt.Sprintf("%s_cacheName", body.Device)
	newDevice := redisClient.Get(devK).Val()
	if newDevice != "" {
		log.Infof("ReplaceDevice[*RequestChannelBody.] devK: %s|| newDevice: %s|| body: %+v", devK, newDevice, *body)
		body.Device = newDevice
	}
	log.Infof("ReplaceDevice[*RequestChannelBody after.] devK: %s|| newDevice: %s|| body: %+v", devK, newDevice, *body)
	return
}

func (body *ReportBodyMulti) ReplaceDevice() {
	if body.Device == "" {
		return
	}
	devK := fmt.Sprintf("%s_cacheName", body.Device)
	newDevice := redisClient.Get(devK).Val()
	if newDevice != "" {
		log.Infof("ReplaceDevice[*ReportBodyMulti.] devK: %s|| newDevice: %s|| body: %+v", devK, newDevice, *body)
		body.Device = newDevice
	}
	log.Infof("ReplaceDevice[*ReportBodyMulti after.] devK: %s|| newDevice: %s|| body: %+v", devK, newDevice, *body)
	return
}

// //IsIP 判断IP是否合法
// func IsIP(ip string) (b bool) {
//  if m, _ := regexp.MatchString("^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}$", ip); !m {
//      return false
//  }
//  return true
// }

/*TaskRequestPost 处理实时接收汇报的请求，并异步判断请求
post: {"key":"afee8371f4d79eca6e63d98bc290cd3b","device":"CNC-XX-1","URL":"http://cdn.chinacache.com/body.jpg","channel":"http://cdn.chinacache.com","IP":"192.168.1.1"}
return:{"msg":"ok"}
*/
func TaskRequestPost(writer http.ResponseWriter, r *http.Request) {
	var body RequestReportBody
	var err error
	result, _ := ioutil.ReadAll(r.Body)
	defer r.Body.Close()
	log.Debugf("TaskRequestPost result(%T): %s", result, result)

	err = json.Unmarshal(result, &body)

	if err != nil {
		log.Errorf("TaskRequestPost[error: %s]", err)
		return
	}
	log.Infof("TaskRequestPost remoteAddr: %+v|| path: %+v|| body: %+v", r.RemoteAddr, r.URL.Path, body)
	go func() {
		ip := net.ParseIP(body.IP)
		if ip == nil {
			log.Errorf("%s, IP Invalid!", body.IP)
			return
		} else {
			ProcessKeyData(body)
		}
		return
	}()

	writer.WriteHeader(200)
	var param = make(map[string]interface{})
	param["msg"] = "ok"
	msg, _ := json.Marshal(param)
	_, err = writer.Write([]byte(msg))
	if err != nil {
		http.Error(writer, "Interal ERROR\n", 500)
		return
	}

}

/*TaskRequestPost 处理实时接收汇报的请求，并异步判断请求
post: {"key":"afee8371f4d79eca6e63d98bc290cd3b","device":"CNC-XX-1","URL":"http://cdn.chinacache.com/body.jpg","channel":"http://cdn.chinacache.com","IP":"192.168.1.1"}
return:{"msg":"ok"}
*/
func TaskRequestPostMic(writer http.ResponseWriter, r *http.Request) {
	var body RequestReportBody
	result, _ := ioutil.ReadAll(r.Body)
	defer r.Body.Close()

	errResult := json.Unmarshal(result, &body)
	if errResult != nil {
		log.Errorf("TaskRequestPostMic errResult: %s|| body: %+v", errResult, body)
		return
	}
	if body.Channel == "" || body.Key == "" {
		log.Errorf("TaskRequestPostMic[ChannelOrKeyIsEmpty.] body: %+v", body)
		return
	}
	log.Debugf("TaskRequestPostMic remote_ip: %+v|| path: %+v|| body: %+v", r.RemoteAddr, r.URL.Path, body)
	body.ReplaceDevice()
	go func() {
		ip := net.ParseIP(body.IP)
		if ip == nil {
			log.Errorf("%s, IP Invalid!", body.IP)
			return
		} else {
			namedKey := fmt.Sprintf("%s_%s_named", body.Channel, body.Device)
			namedExist := redisClient.Exists(namedKey).Val()
			if namedExist == 1 {
				channelNamedLocationMap := redisClient.HGetAll(namedKey).Val()
				// log.Debugf("TaskRequestPostMic [namedType.] namedKey: %+v|| remote_ip: %+v|| path: %+v|| body: %+v|| channelNamedLocationMap: %+v", namedKey, r.RemoteAddr, r.URL.Path, body, channelNamedLocationMap)
				log.Infof("TaskRequestPostMic [namedType.] namedKey: %+v|| remote_ip: %+v|| path: %+v|| body: %+v", namedKey, r.RemoteAddr, r.URL.Path, body)
				for _, cnlConf := range channelNamedLocationMap {
					ProcessNamedData(cnlConf, body)
				}
			} else {
				ProcessKeyData_micro(body)
			}

		}
		return
	}()

	writer.WriteHeader(200)
	var param = make(map[string]interface{})
	param["msg"] = "ok"
	msg, _ := json.Marshal(param)
	_, errWrite := writer.Write([]byte(msg))
	if errWrite != nil {
		http.Error(writer, "Internal ERROR\n", 500)
		return
	}
	return
}

func TaskRequestPostMulti(writer http.ResponseWriter, r *http.Request) {
	var body ReportBodyMulti
	result, _ := ioutil.ReadAll(r.Body)
	defer r.Body.Close()

	json_err := json.Unmarshal(result, &body)
	if json_err != nil {
		log.Error(json_err)
	}
	log.Debugf("TaskRequestPostMulti remote_ip: %+v|| path: %+v|| body: %+v", r.RemoteAddr, r.URL.Path, body)
	body.ReplaceDevice()
	go func() {
		ip := net.ParseIP(body.IP)
		if ip == nil {
			log.Errorf("%s, IP Invalid!", body.IP)
			return
		} else {
			ProcessData_multi(body)
		}
	}()

	writer.WriteHeader(200)
	var param = make(map[string]interface{})
	param["msg"] = "ok"
	msg, _ := json.Marshal(param)
	_, writer_err := writer.Write([]byte(msg))
	if writer_err != nil {
		http.Error(writer, "Interal ERROR\n", 500)
		return
	}
	return
}

func ProcessData_multi(body ReportBodyMulti) error {
	// data receivered as follow
	// {"Channel":"http:\/\/own.cc","IP":"127.0.0.1","URL":"\/130.1","Device":"BGP-SM-3-3gB","Key":{"encrypt":"encrypt_value1","msisdn":"msisdn_value1","client_ip":"11.11.11.111"}}

	channelKey := fmt.Sprintf("%s_security", body.Channel)
	var rules_map []map[string]interface{}
	rules_map_r, _ := redisClient.HGet(channelKey, "rules_map").Bytes()
	json_err := json.Unmarshal(rules_map_r, &rules_map)
	if json_err != nil {
		log.Errorf("ProcessData_multi json_error: %s", json_err)
		return nil
	}
	log.Infof("ProcessData_multi body: %+v", body)

	// in case that data from redis failed
	if len(rules_map) == 0 {
		log.Infof("ProcessData_multi[fromMongo] body: %+v", body)

		result := ChannelConfMicro{}
		err := M.Collection("control_conf").FindOne(context.TODO(), bson.D{{"channel", body.Channel}}).Decode(&result)
		if err != nil {
			log.Errorf("ProcessData_multi[findError.] err: %s|| body: %+v", err, body)
			return err
		}

		rules_map = result.RulesMap
		log.Debugf("ProcessData_multi[fromMongo key: %+v] result: %+v", body.Key, result)
	}

	pipe := redisClient.Pipeline()
	defer pipe.Close()

	for i, rule_map := range rules_map {
		theKey := rule_map["theKey"].(string)
		// k := fmt.Sprintf("%s_%s_%s_%s_multi", body.Channel, body.Device, body.Key[theKey], theKey) // such as: http://own.cc_BGP-SM-3-3gB_1194ce5d0b89c47ff6b30bfb491f9dc26_msisdn_multi, http://own.cc_BGP-SM-3-3gB_94ce5d0b89c47ff6b30bfb491f9dc26_encrypt_multi
		k := fmt.Sprintf("%s_%s_%s_multi", body.Channel, body.Key[theKey], theKey) // such as: http://own.cc_1194ce5d0b89c47ff6b30bfb491f9dc26_msisdn_multi, http://own.cc_94ce5d0b89c47ff6b30bfb491f9dc26_encrypt_multi
		theCycle64 := int(rule_map["theCycle"].(float64))
		theCycle := int(theCycle64)
		theNum64 := int(rule_map["theNum"].(float64))
		theNum := int(theNum64)
		thePeriod64 := int(rule_map["thePeriod"].(float64))
		thePeriod := int(thePeriod64)
		log.Infof("ProcessData_multi k(%d): %s|| theCycle: %+v|| theNum: %+v|| thePeriod: %+v", i, k, theCycle, theNum, thePeriod)

		pipe.Discard()
		incrNumCmd := pipe.Incr(k)
		multiPTTLCmd := pipe.PTTL(k)
		_, err := pipe.Exec()
		if err != nil {
			log.Errorf("ProcessData_multi[pipelineError.] err: %s|| k(%d): %+v", err, i, k)
			return nil
		}
		incrNum, multiPTTL := incrNumCmd.Val(), multiPTTLCmd.Val()
		if multiPTTL == -1 && incrNum == 1 {
			redisClient.Expire(k, time.Duration(theCycle)*time.Second)
			log.Infof("ProcessData_multi[expireDone.] theCycle: %vs|| k(%d): %v|| incrNum: %v|| multiPTTL: %v", theCycle, i, k, incrNum, multiPTTL)
		}
		multiPTTL = redisClient.PTTL(k).Val()
		log.Infof("ProcessData_multi k(%d): %v|| incrNum: %v|| multiPTTL: %v", i, k, incrNum, multiPTTL)

		if int(incrNum) > theNum {
			k_denyMulti := denyAction("ProcessData_multi", body.Channel, body.Device, body.Key[theKey], thePeriod, "denyMulti")
			log.Infof("ProcessData_multi[denyMulti] KeyType: %+v|| Key(%d): %+v|| URL: %+v|| incrNum: %+v|| k_denyMulti: %+v", theKey, i, body.Key[theKey], body.URL, incrNum, k_denyMulti)
			denyMultiNoMongoKey := fmt.Sprintf("%s_noMongo", k_denyMulti)
			canMongo := redisClient.SetNX(denyMultiNoMongoKey, 1, time.Duration(thePeriod)*time.Second).Val()
			if canMongo {
				go denyToMongo(true, body.Channel, theKey, incrNum, body.Device, body.URL, body.Key[theKey], k)
			}

			// for old compatibility
			if IsOldCompatible {
				k_denyMultiNoDev := denyActionNoDev("ProcessData_multi", body.Channel, body.Key[theKey], thePeriod, "denyMulti")
				log.Infof("ProcessData_multi[denyMulti] KeyType: %+v|| Key(%d): %+v|| URL: %+v|| incrNum: %+v|| k_denyMultiNoDev: %+v", theKey, i, body.Key[theKey], body.URL, incrNum, k_denyMultiNoDev)
				denyMultiNoMongoKey := fmt.Sprintf("%s_noMongo", k_denyMultiNoDev)
				canMongo := redisClient.SetNX(denyMultiNoMongoKey, 1, time.Duration(thePeriod)*time.Second).Val()
				if canMongo {
					go denyToMongo(true, body.Channel, theKey, incrNum, body.Device, body.URL, body.Key[theKey], k)
				}
			}
			return nil
		}
	}
	return nil
}

//GetDenyFromMongo 获取Deny_list 集合数据
func GetDenyFromMongo(item string, t time.Time, key string) []string {
	result := ChannelConf{}
	keyList := []string{}
	// var objectList []DenyList

	var cycle int
	var add_query_time int

	channelKey := fmt.Sprintf("%s_security", item)
	cycle64, _ := redisClient.HGet(channelKey, "cycle").Int64()
	add_query_time64, _ := redisClient.HGet(channelKey, "add_query_time").Int64()

	cycle = int(cycle64)
	add_query_time = int(add_query_time64)
	log.Debugf("GetDenyFromMongo [fromRedis] add_query_time: %+v|| cycle: %+v", add_query_time, cycle)
	if add_query_time != 0 {
		cycle = add_query_time
	}
	log.Debugf("GetDenyFromMongo [add_query_time!=0 cycle=add_query_time] cycle1: %+v", cycle)
	if cycle == 0 {
		err := M.Collection("control_conf").FindOne(context.TODO(), bson.D{{"channel", item}}).Decode(&result)
		if err != nil {
			log.Errorf("GetDenyFromMongo[findError.] err: %v|| channel: %+v", err, item)
		}

		cycle = result.Cycle
		log.Debugf("GetDenyFromMongo [fromMongodb] channel: %s|| Cycle: %d", item, result.Cycle)
	}

	if cycle == 0 {
		log.Infof("GetDenyFromMongo channel: %s not config!!!", item)
		return keyList
	}
	rc := fmt.Sprintf("-%ds", cycle)
	log.Debugf("GetDenyFromMongo rc: %+v|| key: %+v", rc, key)
	d, _ := time.ParseDuration(rc)
	fromDate := t.Add(d + time.Hour*8) //入库时为UTC标准时间 ，。为了库内查询方便，直接 +8
	log.Debugf("GetDenyFromMongo fromDate: %+v|| item: %+v", fromDate, item)

	filter := bson.D{{"channel", item}, {"created_time", bson.D{{"$gte", fromDate}}}}
	objectListPtr := FindMany(0, filter)
	objectList := *objectListPtr

	// query := func(c *mgo.Collection) error {
	// 	fn := c.Find(bson.M{"channel": item, "created_time": bson.M{"$gte": fromDate}}).All(&objectList) //.Select(bson.M{"key": 1})
	// 	// log.Debugf("GetDenyFromMongo [query] fn: %+v", fn)
	// 	return fn
	// }
	// if errQuery := withCollection("deny_list", query); errQuery != nil {
	// 	log.Errorf("GetDenyFromMongo errQuery: %+v|| key: %+v", errQuery, key)
	// }
	log.Debugf("GetDenyFromMongo key: %+v|| len(objectList): %+v", key, len(objectList))
	var keysMap = map[string]int{}
	for _, t := range objectList {
		key := t["Key"].(string)
		_, ok := keysMap[key]
		if !ok {
			keyList = append(keyList, key)
			keysMap[key]++
		}

	}

	if len(keyList) > 0 {
		b := strings.Join(keyList, ",")
		if errSet := redisClient.Set(key, b, time.Duration(cycle)*time.Second).Err(); errSet != nil {
			log.Errorf("GetDenyFromMongo errSet: %+v|| key: %+v", errSet, key)
		}
		log.Debugf("GetDenyFromMongo [keyListExpireDone:%ds] key: %+v|| keyList: %+v", cycle, key, keyList)
	}
	return keyList
}

func IsNamed(channel, devName string) bool {
	theK := fmt.Sprintf("%s_%s_named", channel, devName)
	isNamed := false
	if redisClient.Exists(theK).Val() == 1 {
		isNamed = true
	}
	return isNamed
}

func TaskRequestGetList(writer http.ResponseWriter, request *http.Request) {
	var body RequestChannelBody
	responseData := make(map[string][]string)
	var err error

	result, _ := ioutil.ReadAll(request.Body)
	request.Body.Close()
	err = json.Unmarshal(result, &body)
	if err != nil {
		log.Errorf("TaskRequestGetList[errUnmarshal: %s]", err)
		return
	}
	body.ReplaceDevice()
	log.Infof("TaskRequestGetList remote_ip: %s|| URL: %s|| body: %+v", request.RemoteAddr, request.URL.Path, body)

	for _, channel := range body.Channels {
		// denyKey := fmt.Sprintf("%s_%s_deny", channel, body.Device)
		// responseData[channel] = redisClient.HKeys(denyKey).Val()

		var denyKey string
		if IsNamed(channel, body.Device) {
			denyKey = fmt.Sprintf("%s_%s_deny", channel, body.Device)
		} else {
			denyKey = fmt.Sprintf("%s_deny", channel)
		}
		log.Infof("TaskRequestGetList denyKey: %s|| URL: %s|| body: %+v", denyKey, request.URL.Path, body)
		responseData[channel] = redisClient.HKeys(denyKey).Val()
	}
	defer func() {
		writer.WriteHeader(200)
		msg, _ := json.Marshal(responseData)
		log.Infof("TaskRequestGetList [defer] responseData: %+v", responseData)
		if sendFlag == false {
			msg = []byte{}
		}
		_, err = writer.Write([]byte(msg))
		if err != nil {
			http.Error(writer, "Interal ERROR\n", 500)
		}
	}()

}

func DenyListMulti(writer http.ResponseWriter, request *http.Request) {
	var body RequestChannelBody
	responseData := make(map[string][]string)

	result, _ := ioutil.ReadAll(request.Body)
	request.Body.Close()
	json_err := json.Unmarshal(result, &body)
	if json_err != nil {
		log.Errorf("DenyListMulti json_err: %s", json_err)
		return
	}
	log.Infof("DenyListMulti remote_ip: %s|| URL: %s|| body: %+v", request.RemoteAddr, request.URL.Path, body)

	for _, channel := range body.Channels {
		// mK := fmt.Sprintf("%s_%s_denyMulti", channel, body.Device)
		mK := fmt.Sprintf("%s_denyMulti", channel)
		responseData[channel] = redisClient.HKeys(mK).Val()
	}
	defer func() {
		writer.WriteHeader(200)
		msg, _ := json.Marshal(responseData)
		log.Infof("DenyListMulti [defer] responseData: %+v", responseData)
		if sendFlag == false {
			msg = []byte{}
		}
		_, writer_err := writer.Write([]byte(msg))
		if writer_err != nil {
			http.Error(writer, "Interal ERROR\n", 500)
		}
	}()
}

//GetDenyFromMongoAll 获取Deny_list 集合数据
func GetDenyFromMongoAll(item string, t time.Time, key string) []string {
	result := ChannelConf{}
	keyList := []string{}
	// var objectList []DenyList

	var all_query_time int

	channelKey := fmt.Sprintf("%s_security", item)
	all_query_time64, _ := redisClient.HGet(channelKey, "all_query_time").Int64()
	all_query_time = int(all_query_time64)
	if all_query_time == 0 {
		err := M.Collection("control_conf").FindOne(context.TODO(), bson.D{{"channel", item}}).Decode(&result)
		if err != nil {
			log.Errorf("GetDenyFromMongoAll[findError.] err: %+v", err)
		}

		all_query_time = result.All_query_time
		log.Debugf("GetDenyFromMongoAll [fromMongodb] channel: %s|| all_query_time: %d", item, result.All_query_time)
	}

	rc := fmt.Sprintf("-%ds", all_query_time)
	if all_query_time == 0 {
		log.Infof("GetDenyFromMongoAll channel %s not config!", item)
		return keyList
	}
	d, _ := time.ParseDuration(rc)
	fromDate := t.Add(d + time.Hour*8) //入库时为UTC标准时间 ，。为了库内查询方便，直接 +8
	log.Debugf("GetDenyFromMongoAll rc: %+v|| fromDate: %+v|| channel: %+v", rc, fromDate, item)

	filter := bson.D{{"channel", item}, {"created_time", bson.D{{"$gte", fromDate}}}}
	objectListPtr := FindMany(0, filter)
	objectList := *objectListPtr

	log.Debugf("GetDenyFromMongoAll len(objectList): %+v", len(objectList))
	var keysMap = map[string]int{}
	for _, t := range objectList {
		// log.Debug(i, t)
		key := t["Key"].(string)
		_, ok := keysMap[key]
		if ok {
			// log.Debug(fmt.Sprintf("duplicate key: %s", t.Key))
			keysMap[key] = keysMap[key] + 1
		} else {
			keyList = append(keyList, key)
			keysMap[key] = 1
		}

	}
	log.Debugf("GetDenyFromMongoAll keyList: %+v", keyList)
	if len(keyList) > 0 {
		b := strings.Join(keyList, ",")
		if err3 := redisClient.Set(key, b, time.Duration(all_query_time)*time.Second).Err(); err3 != nil {
			log.Error(err3)
		}
		redisClient.Expire(key, time.Duration(all_query_time)*time.Second)
		if errExpire := redisClient.Expire(key, time.Duration(all_query_time)*time.Second).Err(); errExpire != nil {
			log.Error(errExpire)
		}
	}
	return keyList
}

//TaskRequestGetListAll 获取指定频道的deny key列表 all
//post:{"channels":["http://cdn.chinacache.com","http://cdn1.chinacache.com"]}
//return:{"http://cdn.chinacache.com":["afee8371f4d79eca6e63d98bc290cd3b","afee8371f4d79eca6e63d98bc290cd3a"],"http://cdn1.chinacache.com":[]}
func TaskRequestGetListAll(writer http.ResponseWriter, request *http.Request) {
	var body RequestChannelBody
	// body1, _ := ioutil.ReadAll(request.Body)
	// log.Debug(string(body1))
	reponseData := make(map[string][]string)
	var err error
	// buf := new(bytes.Buffer)
	// buf.ReadFrom(request.Body)
	// err = json.Unmarshal(buf.Bytes(), &body)

	result, _ := ioutil.ReadAll(request.Body)
	request.Body.Close()
	err = json.Unmarshal(result, &body)
	if err != nil {
		panic(err)
	}
	log.Infof("TaskRequestGetListAll remote_ip: %+v|| URL: %+v||request_body: %+v", request.RemoteAddr, request.URL.Path, body)
	t := time.Now()

	timestamp := fmt.Sprintf("%d-%02d-%02dT%02d:%02d",
		t.Year(), t.Month(), t.Day(),
		t.Hour(), t.Minute())
	log.Debugf("TaskRequestGetListAll timestamp: %+v|| body.Channels: %+v", timestamp, body.Channels)

	for _, item := range body.Channels {
		keyList := []string{}
		key := fmt.Sprintf("%s_%s_all", timestamp, item)
		val := redisClient.Get(key)
		if val.Val() != "" {
			log.Debugf("TaskRequestGetListAll[fromRedis] key: %s||val: %s|| item: %s", key, val.Val(), item)
			reponseData[item] = strings.Split(val.Val(), ",")
		} else {
			keyList = GetDenyFromMongoAll(item, t, key)
			reponseData[item] = keyList
		}
	}
	defer func() {
		writer.WriteHeader(200)
		msg, _ := json.Marshal(reponseData)
		log.Infof("TaskRequestGetListAll reponseData: %+v", reponseData)
		if sendFlag == false {
			msg = []byte{}
		}
		_, err = writer.Write([]byte(msg))
		if err != nil {
			http.Error(writer, "Interal ERROR\n", 500)
		}

	}()

}

//TaskRequestGet test use
//retrun {"deny":"false"}
func TaskRequestGet(writer http.ResponseWriter, request *http.Request) {

	log.Printf("%s, %s%s", request.Method, request.Host, request.URL.Path)
	// fmt.Println(request.Method, request.Host, request.URL.Path)
	// re := redisClient.Get("afee8371f4d79eca6e63d98bc290cd3a")
	// log.Print(re)
	// fmt.Println(re)
	writer.WriteHeader(200)
	var param = make(map[string]interface{})
	param["deny"] = "false"
	msg, _ := json.Marshal(param)
	_, err := writer.Write([]byte(msg))
	if err != nil {
		http.Error(writer, "Interal ERROR\n", 500)
	}

}

//getSession 连接mongo
// func getSession() *mgo.Session {
// 	if session == nil {
// 		var err error
// 		// session, err = mgo.DialWithTimeout(uri, 2*time.Minute)
// 		session, err = mgo.Dial(uri) //timeout default 10* time.Second
// 		if err != nil {
// 			panic(err)
// 		}
// 		// Optional. Switch the session to a monotonic behavior.
// 		session.SetMode(mgo.Monotonic, true)
// 		session.SetSocketTimeout(2 * time.Minute)
// 		//默认4096
// 	}

// 	return session.Clone()
// }

//withCollection 获取collection数据
// func getCollection(collection string, s func(*mgo.Collection) error) error {
// 	return M.Collection(collection)
// }

// func init() {
//  cfg, err := ini.Load("config.ini")
//  if err != nil {
//      panic(err)
//  }
//  SetRedis(cfg)
//  SetDB(cfg)
//  sendFlag, err = cfg.Section("server").Key("send").Bool()
//
// }

func FindMany(n int64, filter interface{}) *[]map[string]interface{} {
	// query many documents
	collection := M.Collection("control_conf")
	// Pass these options to the Find method
	findOptions := options.Find()
	if n != 0 {
		findOptions.SetLimit(n)
	}

	// Here's an array in which you can store the decoded documents
	var results []map[string]interface{}

	// Passing bson.D{{}} as the filter matches all documents in the collection
	cur, err := collection.Find(context.TODO(), filter, findOptions)
	defer cur.Close(context.TODO())
	if err != nil {
		log.Errorf("FindMany[mongoError.] err: %v", err)
	}

	// Finding multiple documents returns a cursor
	// Iterating through the cursor allows us to decode documents one at a time
	for cur.Next(context.TODO()) {
		result := map[string]interface{}{}
		// create a value into which the single document can be decoded
		err := cur.Decode(&result)
		if err != nil {
			log.Errorf("FindMany[mongoError.] err: %v", err)
		}

		results = append(results, result)
	}

	if err = cur.Err(); err != nil {
		log.Errorf("FindMany[mongoError.] err: %v", err)
	}

	// Close the cursor once finished
	return &results
}

// func main() {
//  router := mux.NewRouter()
//  router.HandleFunc("/authentication", TaskRequestPost).Methods("POST")
//  router.HandleFunc("/", TaskRequestGet).Methods("GET")
//  // router.HandleFunc("/keylist", TaskRequestGetList).Methods("GET")
//  router.HandleFunc("/keylist", TaskRequestGetList).Methods("POST")
//  log.Printf("Starting on port: %d", serverPort)
//  http.ListenAndServe(fmt.Sprintf(":%d", serverPort), router)
//
// }

func ForRW(writer http.ResponseWriter, request *http.Request) {
	log.Infof("ForRW Method: %+v|| Host: %+v|| Path: %+v|| Body: %+v", request.Method, request.Host, request.URL.Path, request.Body)
	// defer request.Body.Close()
	if request.Method == "GET" {
		vals := request.URL.Query()
		request.Body.Close()
		cacheKey := fmt.Sprintf("grey_black_%s", vals["cacheKey"][0])
		log.Debugf("ForRW[GET] vals: %+v|| cacheKey: %+v", vals, cacheKey)
		result := redisClient.Get(cacheKey)
		log.Debugf("ForRW[GET] result: %+v", result)
		writer.WriteHeader(200)
		_, err := writer.Write([]byte(result.Val()))
		if err != nil {
			http.Error(writer, "Interal ERROR\n", 500)
		}

	} else {
		// POST, put data to codis
		var body RWBody
		result, _ := ioutil.ReadAll(request.Body)
		request.Body.Close()

		json_err := json.Unmarshal(result, &body)
		if json_err != nil {
			log.Error(json_err)
		}
		cacheKey := fmt.Sprintf("grey_black_%s", body.CacheKey)
		log.Debugf("ForRW[POST] remote_ip: %+v|| path: %+v|| body: %+v|| cacheKey: %+v", request.RemoteAddr, request.URL.Path, body, cacheKey)

		if redisSetErr := redisClient.Set(cacheKey, body.Data, time.Duration(0)*time.Second).Err(); redisSetErr != nil {
			log.Error(redisSetErr)
			writer.WriteHeader(200)
			var param = make(map[string]interface{})
			param["msg"] = redisSetErr
			msg, _ := json.Marshal(param)
			_, writer_err := writer.Write([]byte(msg))
			if writer_err != nil {
				http.Error(writer, "Interal ERROR\n", 500)
			}
		}

		writer.WriteHeader(200)
		var param = make(map[string]interface{})
		param["msg"] = "ok"
		msg, _ := json.Marshal(param)
		_, writer_err := writer.Write([]byte(msg))
		if writer_err != nil {
			http.Error(writer, "Interal ERROR\n", 500)
		}

	}
	return
}

func ConfigedChannels(writer http.ResponseWriter, request *http.Request) {
	log.Infof("ConfigedChannels Method: %+v|| Host: %+v|| Path: %+v|| Body: %+v", request.Method, request.Host, request.URL.Path, request.Body)
	var body = make(map[string]string)
	result, _ := ioutil.ReadAll(request.Body)
	defer request.Body.Close()

	json_err := json.Unmarshal(result, &body)
	if json_err != nil {
		log.Error(json_err)
	}

	// infoList := []map[string]interface{}{}
	filter := bson.D{{"user", body["username"]}}
	infoListPtr := FindMany(0, filter)
	infoList := *infoListPtr

	// query := func(c *mgo.Collection) error {
	// 	err1 := c.Find(bson.M{"user": body["username"]}).All(&infoList)
	// 	if err1 != nil {
	// 		log.Error(err1)
	// 	}
	// 	return err1
	// }
	// withCollection("control_conf", query)
	cList := []string{}
	for _, info := range infoList {
		cList = append(cList, info["channel"].(string))
	}
	log.Debugf("ConfigedChannels[fromMongodb] username: %v|| channels: %v", body["username"], cList)

	writer.WriteHeader(200)
	// param := make(map[string]string{})
	// param["msg"] = "ok"
	msg, _ := json.Marshal(cList)
	_, writer_err := writer.Write([]byte(msg))
	if writer_err != nil {
		http.Error(writer, "Interal ERROR\n", 500)
	}

	return
}

func FlowDiagram(writer http.ResponseWriter, request *http.Request) {
	log.Infof("FlowDiagram Method: %+v|| Host: %+v|| Path: %+v|| Body: %+v", request.Method, request.Host, request.URL.Path, request.Body)
	request.Body.Close()

	tmpl, errTemplate := template.ParseFiles("templates/GreenlandFlowDiagram.html")
	if errTemplate != nil {
		log.Errorf("FlowDiagram error: %s", errTemplate)
	}

	tmpl.Execute(writer, "")
}
