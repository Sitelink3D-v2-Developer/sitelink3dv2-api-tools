#!/usr/bin/env bash
export SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export SCRIPT_NAME=$(basename -- "${BASH_SOURCE[0]}" .sh)

## >>> Mandatory Settings
export DC=us
export DEPLOY_ENV=qa
export REGION=medium
export SITE=""
export AUTH_TOKEN=""
default_files="${SCRIPT_DIR}/trucks.json ${SCRIPT_DIR}/excavator.json"
## <<< Mandatory Settings

declare -A HOSTS
HOSTS=([qa]="qa-api.code.topcon.com" [prod]="api.code.topcon.com")
logname=${SCRIPT_NAME}
logpath=${SCRIPT_DIR}/logs
# >> option processing
while case $1 in
  --dc) #DC#set the DC (us,eu,...)
    shift; export DC=$1;;
  --deploy-env) #DEPLOY_ENV#set the deployment environment (qa, prod)
    shift; export DEPLOY_ENV=$1;;
  --logname) #LOGNAME#set the name used to log things under
    shift; logname=$1 ;;
  --logpath) #LOGPATH#set the root directory to write logging to
    shift; logpath=$1 ;;
  --trace) #LOG_TRACE#set tracing on or off (on,off)
    shift; case $1 in
        1|t*|T*|on|ON) export LOG_TRACE=true;;
        *) export LOG_TRACE=false;;
    esac;;
  --region) #REGION#set the region size (small,medium,large)
    shift; export REGION=$1;;
  --site) #SITE#set the site identifier
    shift; export SITE=$1;;
  --token) #AUTH_TOKEN#set the JWT
    shift; export AUTH_TOKEN=$1;;
  --) shift; false;;
  *) false;;
esac; do shift; done
# << option processing

logdir=${logpath}/${logname}
mkdir -p ${logdir}

: ${API_HOST:="${DC}-${HOSTS[$DEPLOY_ENV]}"}

export DL_AGGREGATOR_HOST="${API_HOST}"
export DL_AGGREGATOR_PORT="443"
export DL_AGGREGATOR_SCHEME="wss"

export SITELINK_RDM_HOST="${API_HOST}"
export SITELINK_RDM_PORT="443"
export SITELINK_RDM_SCHEME="https"
: ${LOG_TRACE:=false}
export LOG_TRACE
pfile=${logdir}/.processes
current_logs=${logdir}/.logs

helptext="$(tr '\n ' '|@' <<HELPXX
 $(basename $0) [options] action [files] - run pathinator simulation

 This file runs a simulation for the following settings:
   DC         : $DC
   DEPLOY_ENV : $DEPLOY_ENV
   SITE       : $SITE

 The files should be appropriate json files and default to
     $(sed "s@$(pwd -P)/@@g" <<< $default_files)
HELPXX
)"

function help() {
    tr '|@' '\n ' <<< $helptext
    echo " The following options are understood:"; echo
    sed -n '/^\s*# >> option processing/,/^\s*# << option processing/'p $SCRIPT_DIR/${SCRIPT_NAME}.sh |
        sed -n -e 's/ *# */#/g' -e 's/^\s*\(-*\)\([a-z-]*\)) *# *\(.*\)/\1\2#\3/p' |
        sort|
        awk -F'#' '{ printf "    %12s %-10s %s [dflt: %s%s]\n", $1, $2, $3, substr(ENVIRON[$2],1,10), (length(ENVIRON[$2])>10?"...":"")}'

    echo; echo " The following actions are understood:"; echo
    sed -n '/^\s*# >> arg processing/,/^\s# << arg processing/'p $SCRIPT_DIR/${SCRIPT_NAME}.sh |
        sed -n -e 's/ *# */#/g' -e 's/^\s*\(-*\)\([a-z]*\)) *# *\(.*\)/\1\2#\3/p' |
        sort |
        awk -F'#' '{ printf "    %12s %-6s %s\n", $1, $2, $3}'
}

function pidtree() {
    # also kill off child processes
    local ps
    for ps; do
        while [ "$ps" ]; do
            echo $ps
            ps=$(for p in $ps; do cat /proc/$p/task/$p/children; done)
        done
    done
}

function kill_processes() {
    # also kill off child processes
    set -- $(pidtree $*)

    echo killing $* ...
    for flag in 15 9; do
        for p; do
            [[ -d /proc/$p ]] || continue
            kill -$flag $p
        done
        sleep 0.1
    done
}

function events() {
    local clazz=$1
    shift
    [[ $# -eq 0 ]] || cat "$@" | sed -n \
        -e 's@ *[(]distribution/[a-zA-Z0-9.]*:[0-9]*[)]$@@' \
        -e "s/.*TRACE : EVENT: $clazz: *//p" | sort -u
}

function runActionFiles() {
    local action=$1 f d=$(date +%Y%m%d-%H%M) p logfiles="" basefiles=""
    shift

    for file; do
        basefiles="$basefiles $(basename $file .json)"
    done
    [[ -f $current_logs ]] && for f in $basefiles; do
        logfiles="$logfiles $(grep $f $current_logs)"
    done

    # >> arg processing
    case $action in
    help) ## print this message
        help "$@"
        exit 0
        ;;
    start) ## start a simulation
        if [[ -f $pfile ]] ; then
            echo "checking to see if processes running ..."
            runActionFiles status "$@" | cat -n
            if [[ -f $pfile ]]; then
                for f in $basefiles; do
                    if grep $f $pfile >/dev/null; then
                        echo process $f still running!
                        exit 1
                    fi
                done
            fi
        fi
        if [[ -z $AUTH_TOKEN ]] ; then
            echo "You have not set the AUTH_TOKEN variable. It needs to be a JWT valid for your site."
            exit 1
        fi
        if [[ ! -x ${SCRIPT_DIR}/distribution ]]; then
            exe=$(which distribution)
            if [[ ! -x $exe ]]; then
                echp "Cannot find executable!!"
                exit 1
            fi
            ln -s $exe ${SCRIPT_DIR}/distribution
        fi
        rm -f $current_logs
        for file; do
            if [[ ! -f $file ]] ; then
                file=${SCRIPT_DIR}/$file
            fi
            if [[ ! -f $file ]] ; then
                echo cannot find file $file; exit 1
            fi
            f=$(basename $file .json)
            local lf=${logdir}/${f}.${d}.log
            nohup ${SCRIPT_DIR}/minder.sh ${SCRIPT_DIR}/distribution ${file} >${lf} 2>&1 &
            p=$!
            echo $lf >> $current_logs
            echo "${f}=$p" >> $pfile
            echo 1>&2 "running file $f as process $p"
        done
        echo $SCRIPT_DIR/$(basename $0) >> $SCRIPT_DIR/.running
        ;;
    status) ## shows relevant processes if running
        [[ -f $pfile ]] || { echo Not running; return; }
        for f in $basefiles; do
            for line in $(grep $f $pfile); do
                local key=${line%=*} pid=${line#*=}
                if [[ -d /proc/$pid ]]; then
                    echo "$key: status: running/running"
                    for pid in $(pidtree $pid); do
                        ppid=$(ps -o ppid= $pid)
                        echo "    pid: $pid ppid: $ppid cmd: $(tr '\0' ' ' </proc/$pid/cmdline)" | sed "s@$SCRIPT_DIR/@@g"
                    done
                else
                    echo "$key: status: running/stopped pid: $pid"
                    sed -i -e /"$line"/d $pfile
                fi
            done
            [[ -s $pfile ]] || rm -f $pfile
        done
        ;;
    stop) ## stop the simulation
        [[ -f $pfile ]] || { echo Not running; exit 1; }
        for file; do
            f=$(basename $file .json)
            for line in $(grep $f $pfile); do
                local key=${line%=*} pid=${line#*=}
                kill_processes $pid
                sed -i -e /"$line"/d $pfile
            done
            [[ -s $pfile ]] || rm -f $pfile
        done
        [[ -f ${SCRIPT_DIR}/.running ]] && sed -i -e /"$(basename $0)"/d ${SCRIPT_DIR}/.running
        ;;
    restart) ## stop if running, then start
        [[ -f $pfile ]] && runActionFiles stop "$@"
        runActionFiles start "$@"
        ;;
    purge) ## remove old log files
        echo "Purging old log files in $logdir"
        for file in $logdir/*.log; do
            f=$(basename $file)
            case "$logfiles" in
                *$file*) echo "- keep $f" ;;
                *) echo "-   rm $f"; rm $file ;;
            esac
        done
        ;;
    tail) ## tail log files
        [[ -z $logfiles ]] || tail -f $logfiles
        ;;
    resources) ## list all resource events if LOG_TRACE is true
        events RESOURCE $logfiles
        ;;
    updates) ## list all update events if LOG_TRACE is true
        events UPDATE $logfiles
        ;;
    events) ## list all events if LOG_TRACE is true
        events '[A-Z]*' $logfiles
        ;;
    *)
        echo; echo "ERROR: action $action not understood"
        echo "Try '$0 help' for help."
        exit 1
        ;;
    esac
    # << arg processing
}

case $# in
    0) help ; exit 1 ;;
    1) runActionFiles "$1" $default_files ;;
    *) runActionFiles "$@" ;;
esac
