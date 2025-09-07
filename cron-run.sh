#!/bin/sh
# for easy use in crontab
# crontab example:
# 00 08 * * * /path/to/ex_dividend_notifier.sh
LOG_PATH=$HOME/.local/share/stock-robot/log
LOG_FILE=$LOG_PATH/get_ex_dividend_info-`date +%Y%m%d`.log
OUTPUT_FILE=$LOG_PATH/ex_dividend_info-`date +%Y%m%d`.json
STOCK_LIST=interest_stock_list.txt
SELF_DIR=`dirname "$0"`
PY_BIN=$SELF_DIR/get_ex_dividend_info.py

mkdir -p $LOG_PATH
cd $SELF_DIR && $SELF_DIR/venv/bin/python3 $PY_BIN -i 1 -vv --stock-list-file $SELF_DIR/$STOCK_LIST -o $OUTPUT_FILE 2>&1 | tee $LOG_FILE
