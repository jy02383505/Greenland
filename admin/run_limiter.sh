#!/bin/sh

HOME=/home/refresh/Greenland/admin
PORT=8008

case "$1" in
    start)
        nohup python -u $HOME/app.py --port=$PORT &
        echo 'Limit center start at 8008 !!'
        # for j in $(seq 1 8)
        # do 
        #     PORT=$(( $PORT + 1 ))
        #     nohup python -u $HOME/app.py --port=$PORT > $HOME/logs/nohup_center_$PORT.out 2>&1 &
        # done
        # echo 'center start !! 8001-8008'

    ;;
    stop)
        ps aux|grep python|grep app.py|grep Greenland|grep -v grep|awk '{print "kill -9 "$2}'|sh
        echo 'center stop !!'
    ;;
    *)
        echo 'use start|stop'
    ;;
esac

