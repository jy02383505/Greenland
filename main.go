// Copyright 2016
//Created by huan.ma on 5/19/2016
// 华数鉴权

package main

import (
	"Greenland/auth"
	// "Greenland/limiter"
	ut "Greenland/utils"
	"fmt"
	"net/http"
	_ "net/http/pprof"

	// "gopkg.in/ini.v1"
	// log "github.com/Sirupsen/logrus"
	"github.com/gorilla/mux"
)

var serverPort = ut.ServerPort
var log = ut.Logger

// func init() {
// 	cfg, err := ini.Load("config.ini")
// 	if err != nil {
// 		panic(err)
// 	}
// 	// loglevel := cfg.Section("log").Key("level").String()
// 	// logfile := cfg.Section("log").Key("filename").String()
// 	// SetLog(loglevel, logfile)
// 	//
// 	// SetRedis(cfg)
// 	// SetDB(cfg)
// 	serverPort, err = cfg.Section("server").Key("port").Int()
// 	// sendFlag, err = cfg.Section("server").Key("send").Bool()
//
// }

func main() {
	go func() {
		log.Println(http.ListenAndServe(":7070", nil))
	}()
	router := mux.NewRouter()
	//--- deal with static files.
	router.PathPrefix("/images/").Handler(http.StripPrefix("/images/", http.FileServer(http.Dir("templates/images"))))

	router.HandleFunc("/authentication", auth.TaskRequestPost).Methods("POST")
	router.HandleFunc("/authenticationmic", auth.TaskRequestPostMic).Methods("POST")
	router.HandleFunc("/auth_multi", auth.TaskRequestPostMulti).Methods("POST")
	router.HandleFunc("/forRW", auth.ForRW).Methods("GET")
	router.HandleFunc("/forRW", auth.ForRW).Methods("POST")
	router.HandleFunc("/channels", auth.ConfigedChannels).Methods("POST")
	router.HandleFunc("/", auth.TaskRequestGet).Methods("GET")
	// router.HandleFunc("/keylist", TaskRequestGetList).Methods("GET")
	router.HandleFunc("/keylist", auth.TaskRequestGetList).Methods("POST")
	router.HandleFunc("/keylist_multi", auth.DenyListMulti).Methods("POST")
	router.HandleFunc("/all_keylist", auth.TaskRequestGetListAll).Methods("POST")
	router.HandleFunc("/flow_diagram", auth.FlowDiagram).Methods("GET")
	// router.HandleFunc("/limiter", limit.BandLimit).Methods("POST")
	log.Printf("Starting on port: %d", serverPort)
	if errServer := http.ListenAndServe(fmt.Sprintf(":%d", serverPort), router); errServer != nil {
		log.Errorf("main [server error.] %s", errServer)
	}
}
