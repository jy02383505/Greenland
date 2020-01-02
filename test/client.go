package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

type PostBody struct {
	Key     string `json:"key"`
	Device  string `json:"device"`
	URL     string `json:"URL"`
	Channel string `json:"channel"`
	IP      string `json:"IP"`
}
type PostChannelBody struct {
	Channels []string `json:"channels"`
}

// {
// “key”:” afee8371f4d79eca6e63d98bc290cd3a”,
// “IP”:”192.168.1.1”,
// “device”:”CNC-XX-1”,
// “channel”:”http://cdn.chinacache.com”
// }

func PostRealBody() {
	var rb PostBody
	rb.Key = "afee8371f4d79eca6e63d98bc290cd2z1"
	rb.Device = "CNC-XX-1"
	rb.Channel = "http://cdn.chinacache.com"
	rb.URL = "http://cdn.chinacache.com/body.jpg"

	for i := 0; i < 6; i++ {
		rb.IP = fmt.Sprintf("100.168.1.%d", i)
		// rb.IP = fmt.Sprintf("192.168.1.%d", i)
		b, err := json.Marshal(rb)
		if err != nil {
			fmt.Println("json err:", err)
		}
		fmt.Println(string(b))
		body := bytes.NewBuffer([]byte(b))
		// resp, err := http.Post("http://hcen.ccgslb.net/authentication", "APPLICATION/x-www-form-urlencoded", body)
		resp, err := http.Post("http://223.202.203.53:8888/authentication", "APPLICATION/x-www-form-urlencoded", body)
		// resp, err := http.Post("http://127.0.0.1:8888/authentication", "APPLICATION/x-www-form-urlencoded", body)
		if err != nil {
			fmt.Println(err)
		}

		defer resp.Body.Close()
		r_body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			// handle error
		}
		fmt.Println(string(r_body))
	}

}

func PostRealBodyMic() {
	var rb PostBody
	rb.Key = "afee8371f4d79eca6e63d98bc290cd2z1"
	rb.Device = "CNC-XX-1"
	rb.Channel = "http://187.com"
	rb.URL = "http://187.com/body.jpg"

	for i := 0; i < 16; i++ {
		// rb.IP = fmt.Sprintf("100.168.1.%d", i)
		// rb.IP = fmt.Sprintf("192.168.1.%d", i)
		// the same ip  visit times
		rb.IP = fmt.Sprintf("100.168.1.1")
		b, err := json.Marshal(rb)
		if err != nil {
			fmt.Println("json err:", err)
		}
		fmt.Println(string(b))
		body := bytes.NewBuffer([]byte(b))
		// resp, err := http.Post("http://hcen.ccgslb.net/authentication", "APPLICATION/x-www-form-urlencoded", body)
		resp, err := http.Post("http://223.202.203.53:8888/authenticationmic", "APPLICATION/x-www-form-urlencoded", body)
		// resp, err := http.Post("http://127.0.0.1:8888/authentication", "APPLICATION/x-www-form-urlencoded", body)
		if err != nil {
			fmt.Println(err)
		}

		defer resp.Body.Close()
		r_body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			// handle error
		}
		fmt.Println(string(r_body))
	}

}

func GetReportData() {
	var pc PostChannelBody
	pc.Channels = []string{"http://187.com", "http://cdn1.chinacache.com"}
	b, err := json.Marshal(pc)
	if err != nil {
		fmt.Println("json err:", err)
	}

	fmt.Println(string(b))
	body := bytes.NewBuffer([]byte(b))
	// resp, err := http.Post("http://127.0.0.1:8888/keylist", "APPLICATION/x-www-form-urlencoded", body)
	resp, err := http.Post("http://223.202.203.53:8888/keylist", "APPLICATION/x-www-form-urlencoded", body)
	// resp, err := http.Post("http://hcen.ccgslb.net/keylist", "APPLICATION/x-www-form-urlencoded", body)
	if err != nil {
		fmt.Println(err)
	}

	defer resp.Body.Close()
	r_body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		// handle error
	}
	fmt.Println(string(r_body))

}

func main() {
	PostRealBody()
	// PostRealBodyMic()
	GetReportData()

}
