#!/usr/bin/env bash

while :; do
    echo "$(date --utc +'%Y/%m/%d %T') **** STARTING **** "
    $*
    echo "$(date --utc +'%Y/%m/%d %T') ****TERM**** Restarting in 5 seconds ...."
    sleep 5
done
