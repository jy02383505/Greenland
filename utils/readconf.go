package utils

import (
	"context"
	"fmt"
	// "strings"
	"time"

	r "gopkg.in/ini.v1"
	// "gopkg.in/mgo.v2"
	// "gopkg.in/redis.v3"
	"github.com/go-redis/redis"
	// "go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

var SendFlag = true
var URI = ""
var DatabaseName = ""
var ServerPort = 8000
var IsOldCompatible = false
var (
	Mongo       *mongo.Database
	RedisClient *redis.Client
)

//RedisServer redis
type RedisServer struct {
	Host          string
	Passwd        string
	MasterName    string
	SentinelAddrs []string
	DBnum         int
	ActiveConnNum int
}

//DBServer mongodb
type DBServer struct {
	Host     string
	User     string
	Password string
	DBname   string
}

//SetRedis is connect redis
func SetRedis(cfg *r.File) error {
	rs := new(RedisServer)
	if err := cfg.Section("redis").MapTo(rs); err != nil {
		panic(err)
	}

	RedisClient = redis.NewFailoverClient(&redis.FailoverOptions{
		MasterName:    rs.MasterName,
		SentinelAddrs: rs.SentinelAddrs,
		Password:      rs.Passwd,
		DB:            rs.DBnum,
		PoolSize:      rs.ActiveConnNum, //default is 100 connections
		PoolTimeout:   time.Duration(300) * time.Second,
		IdleTimeout:   time.Duration(240) * time.Second, //240s
		DialTimeout:   time.Duration(60) * time.Second,  //60s
		ReadTimeout:   time.Duration(30) * time.Second,  //30s
		WriteTimeout:  time.Duration(30) * time.Second,  //30s
	})
	_, err1 := RedisClient.Ping().Result()
	// fmt.Println(pong, err)
	if err1 != nil {
		panic(err1)
	}
	// r := RedisClient.HGetAll("http://m.chinacache.com_security").Val()
	// fmt.Printf("#SetRedis ---\nr(%T): %+v\n", r, r)
	return nil
}

func toUint64(v int) *uint64 {
	vv := uint64(v)
	return &vv
}

//SetDB 数据库连接设置
func SetDB(cfg *r.File) error {
	ds := new(DBServer)
	err := cfg.Section("db").MapTo(ds)
	if err != nil {
		panic(err)
	}

	// URI = fmt.Sprintf("mongodb://%s:%s@%s/%s", ds.User, ds.Password, ds.Host, ds.DBname)
	// DatabaseName = ds.DBname
	// testSession, err1 := mgo.Dial(URI)
	// err1 = testSession.Ping()

	// defer func() {
	// 	testSession.Close()
	// 	if x := recover(); x != nil {
	// 		panic(x)
	// 	}
	// }()

	// return err1

	URI = fmt.Sprintf("mongodb://%s:%s@%s/%s", ds.User, ds.Password, ds.Host, ds.DBname)
	ct := 10 * time.Second
	clientOptions := options.Client().ApplyURI(URI)
	clientOptions.MaxConnIdleTime = &ct
	clientOptions.MaxPoolSize = toUint64(100)
	clientOptions.MinPoolSize = toUint64(3)
	clientOptions.ConnectTimeout = &ct
	client, err := mongo.Connect(context.TODO(), clientOptions)
	if err != nil {
		panic(err)
	}
	Mongo = client.Database("cc")
	return err
}

func init() {
	cfg, err := r.Load("config.ini")
	if err != nil {
		panic(err)
	}
	loglevel := cfg.Section("log").Key("level").String()
	logfile := cfg.Section("log").Key("filename").String()
	// logfile = fmt.Sprintf("%s/%s", "logs", logfile)
	SetLog(loglevel, logfile)

	SetRedis(cfg)
	SetDB(cfg)
	ServerPort, err = cfg.Section("server").Key("port").Int()
	SendFlag, err = cfg.Section("server").Key("send").Bool()
	IsOldCompatible, err = cfg.Section("server").Key("isOldCompatible").Bool()
}
