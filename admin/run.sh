#!/bin/sh

HOME=/home/refresh/Greenland/admin
PORT=8000

case "$1" in
    start)
        nohup python -u $HOME/app.py --port=$PORT > $HOME/greenland_admin.out 2>&1 &
        echo $PORT 'GreenlandAdmin start !!'
    ;;
    stop)
        ps aux|grep python|grep app.py|grep Greenland|grep -v grep|awk '{print "kill -9 "$2}'|sh
        echo 'GreenlandAdmin stop !!'
    ;;
    *)
        echo 'use start|stop'
    ;;
esac

