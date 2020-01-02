#!/bin/bash
cd /home/refresh/cc/greenland/
green_process="greenland-1.4.11"
green_id=`ps aux |grep greenland-1.4 |grep -v grep |awk '{print $2}'`
green_mem=`cat /proc/${green_id}/status |grep VmRSS |awk '{print int($2/1000/1000)}'`

if [ ${green_mem} -gt 20 ]
  then
      kill -9 ${green_id}
      sleep 5
      nohup ./${green_process} &
fi


if ps -ef | grep "greenland-1" | grep -v grep; then
    pid1=`ps -ef | grep "greenland-1" | grep -v grep | head -1 | awk '{print $2}'`
    echo "greenland is running!  main process id = $pid1"
else
    echo "greenland is running ..."
    nohup ./${green_process} > /dev/null 2>&1 &
fi