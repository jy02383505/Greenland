package auth

/*
go test -v
go test -cover
go test -test.bench=".*"
go test -race

➜  auth git:(master) ✗ go test -test.bench=".*"
PASS
BenchmarkProcessKeyData-8        	     200	   7520378 ns/op
BenchmarkProcessKeyDataParallel-8	    1000	   1164824 ns/op
ok  	Greenland/auth	3.649s

*/
import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestProcessKeyData(t *testing.T) {
	var rb RequestReportBody
	rb.Key = "afee8371f4d79eca6e63d98bc290cd3b"
	rb.Device = "CNC-XX-1"
	rb.Channel = "http://cdn.chinacache.com"
	rb.URL = "http://cdn.chinacache.com/body.jpg"
	rb.IP = "192.168.1.1"
	err := ProcessKeyData(rb)
	if err != nil {
		t.Fail()
	}
}

func TestTaskRequestPost(t *testing.T) {
	var rb RequestReportBody
	rb.Key = "afee8371f4d79eca6e63d98bc290cd3b"
	rb.Device = "CNC-XX-1"
	rb.Channel = "http://cdn.chinacache.com"
	rb.URL = "http://cdn.chinacache.com/body.jpg"
	rb.IP = "192.168.1.1"
	b, err := json.Marshal(rb)
	if err != nil {
		fmt.Println("json err:", err)
	}

	// fmt.Println(string(b))
	body := bytes.NewBuffer([]byte(b))
	// resp := httptest.NewRecorder()
	req, err := http.NewRequest("Post", "/authentication", body) //io.Reader
	if err != nil {
		t.Fatal(err)
	}
	// We create a ResponseRecorder (which satisfies http.ResponseWriter) to record the response.
	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(TaskRequestPost)
	handler.ServeHTTP(rr, req)
	// Check the status code is what we expect.
	if status := rr.Code; status != http.StatusOK {
		t.Errorf("handler returned wrong status code: got %v want %v",
			status, http.StatusOK)
	}
	// Check the response body is what we expect.
	expected := `{"msg":"ok"}`
	if rr.Body.String() != expected {
		t.Errorf("handler returned unexpected body: got %v want %v",
			rr.Body.String(), expected)
	}

}

func TestTaskRequestGetList(t *testing.T) {
	var pc RequestChannelBody
	pc.Channels = []string{"http://cdn.chinacache.com", "http://cdn1.chinacache.com"}
	b, err := json.Marshal(pc)
	if err != nil {
		fmt.Println("json err:", err)
	}

	body := bytes.NewBuffer([]byte(b))
	// resp := httptest.NewRecorder()
	req, err := http.NewRequest("Post", "/keylist", body) //io.Reader
	if err != nil {
		t.Fatal(err)
	}
	// We create a ResponseRecorder (which satisfies http.ResponseWriter) to record the response.
	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(TaskRequestGetList)
	handler.ServeHTTP(rr, req)
	// Check the status code is what we expect.
	if status := rr.Code; status != http.StatusOK {
		t.Errorf("handler returned wrong status code: got %v want %v",
			status, http.StatusOK)
	}
	// Check the response body is what we expect.
	expected := `{"http://cdn.chinacache.com":[],"http://cdn1.chinacache.com":[]}`
	if rr.Body.String() != expected {
		t.Errorf("handler returned unexpected body: got %v want %v",
			rr.Body.String(), expected)
	}
}

func BenchmarkProcessKeyData(b *testing.B) {
	var rb RequestReportBody
	rb.Key = "afee8371f4d79eca6e63d98bc290cd3b"
	rb.Device = "CNC-XX-1"
	rb.Channel = "http://cdn.chinacache.com"
	rb.URL = "http://cdn.chinacache.com/body.jpg"
	rb.IP = "192.168.1.1"
	for i := 0; i < b.N; i++ {
		err := ProcessKeyData(rb)
		if err != nil {
			b.Fail()
		}
	}
}

// 测试并发效率
func BenchmarkProcessKeyDataParallel(b *testing.B) {
	var rb RequestReportBody
	rb.Key = "afee8371f4d79eca6e63d98bc290cd3b"
	rb.Device = "CNC-XX-1"
	rb.Channel = "http://cdn.chinacache.com"
	rb.URL = "http://cdn.chinacache.com/body.jpg"
	rb.IP = "192.168.1.1"
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			err := ProcessKeyData(rb)
			if err != nil {
				b.Fail()
			}
		}
	})
}
