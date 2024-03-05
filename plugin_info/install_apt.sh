PROGRESS_FILE=/tmp/jeedom/tvremote/dependency
if [ ! -z $1 ]; then
	PROGRESS_FILE=$1
fi

BASE_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
VENV_DIR=$BASE_DIR/venv

function log(){
	if [ -n "$1" ]
	then
		echo "$(date +'[%F %T]') $1";
	else
		while read IN               # If it is output from command then loop it
		do
			echo "$(date +'[%F %T]') $IN";
		done
	fi
}

cd $BASE_DIR

touch ${PROGRESS_FILE}
echo 0 > ${PROGRESS_FILE}
log "*************************************"
log "*   Launch install of dependencies  *"
log "*************************************"
echo 5 > ${PROGRESS_FILE}
apt-get clean | log
echo 10 > ${PROGRESS_FILE}
apt-get update | log
echo 20 > ${PROGRESS_FILE}

log "*****************************"
log "Install modules using apt-get"
log "*****************************"
apt-get install -y python3 python3-requests python3-pip python3-setuptools python3-dev python3-venv | log
echo 50 > ${PROGRESS_FILE}

log "*************************************"
log "Creating python 3 virtual environment"
log "*************************************"
python3 -m venv $VENV_DIR | log
echo 60 > ${PROGRESS_FILE}
log "Done"

log "*************************************"
log "Install the required python libraries"
log "*************************************"
$VENV_DIR/bin/python3 -m pip install --no-warn-script-location --upgrade pip wheel | log
echo 70 > ${PROGRESS_FILE}
$VENV_DIR/bin/python3 -m pip install --no-warn-script-location -r requirements.txt | log

echo 100 > ${PROGRESS_FILE}
log "***************************"
log "*      Install ended      *"
log "***************************"
rm ${PROGRESS_FILE}
