#!/usr/bin/env python3
import argparse

import io
import json
from datetime import datetime, date, timedelta
from dividend_info import DividendInfo, DividendRecord
from dividend_getter import DividendGoodinfo, DividendMoneylink, get_dividend_info
import logging
import time
import os
import traceback


default_sleep_interval = 5
default_watch_list_file = '~/.local/share/stock-robot/ex_dividend_watch_list.txt'
log = logging.getLogger(os.path.basename(__file__))

goodinfo = DividendGoodinfo()
moneylink = DividendMoneylink()
dividend_getters = [moneylink, goodinfo]


def read_watch_list_file(stock_list_file):
    # watch_list_path = os.path.expanduser(default_watch_list_file)
    # watch_list = []
    watch_list = stock_list_file.read().splitlines()
    return watch_list


def write_to_file(outfile: io.TextIOWrapper, div_info: dict[str, DividendInfo]):
    log.debug('There are total %d div_info, written to %s' % (len(div_info), outfile.name))
    result = {}
    for __key, __info in div_info.items():
        result[__key] = __info.to_dict()

    json.dump(result, outfile, indent=2, ensure_ascii=False)


def get_arguments():
    parser = argparse.ArgumentParser(description='Ex-dividend notifier.')

    stock_arg = parser.add_mutually_exclusive_group(required=True)
    stock_arg.add_argument('-s', '--stocks', nargs='+',
                           help='Specify watching stock id. If not specified read the watch list file')
    stock_arg.add_argument('-l', '--stock-list-file',
                           type=argparse.FileType('r'),
                           help='Specify watch list file of interesting stock list')

    parser.add_argument('-a', '--all-record', action="store_true", default=False,
                        help='Store all record, do not filter out past record')
    parser.add_argument('-o', '--output', type=argparse.FileType('w', encoding='utf8'),
                        help='Specify output file, if None output to stdout')
    parser.add_argument('-v', '--verbosity', action="count", default=0,
                        help='increase output verbosity')
    parser.add_argument('-i', '--sleep-interval', type=int, default=default_sleep_interval,
                        help='Sleep interval in seconds, default value is %(default)s (seconds)')

    return parser.parse_args()


def main():
    args = get_arguments()

    log_format = '[%(levelname)7s] %(asctime)s %(name)s %(message)s'
    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    elif args.verbosity >= 1:
        logging.basicConfig(level=logging.INFO, format=log_format)
    else:
        logging.basicConfig(level=logging.ERROR, format=log_format)

    if args.stocks is None:
        stocks = read_watch_list_file(args.stock_list_file)
    else:
        stocks = args.stocks

    log.info('Today is %s' % date.today())
    div_info = {}
    for stock_id in stocks:
        log.info('Obtaining %s...' % stock_id)
        __div_info = get_dividend_info(stock_id)

        if __div_info is None:
            info = DividendInfo(stock_id=stock_id, stock_name="NA")
            info.error = '找不到 %s 的任何資料，可能網頁分析失敗' % stock_id
            log.error(info.error)
            div_info[stock_id] = info
        elif len(__div_info.div_record) == 0:
            log.info('%s(%s) 最近沒有除權息資料，可能真的缺乏除權息資料' % (__div_info.stock_name, __div_info.stock_name))
        else:
            log.info('%s(%s) %s' % (__div_info.stock_id, __div_info.stock_name, __div_info.div_record[0]))
            div_info[stock_id] = __div_info

        log.debug("Sleep %d seconds to avoid DOS detecting.." % args.sleep_interval)
        time.sleep(args.sleep_interval)

    if args.output is None:
        print('None of output file')
    else:
        write_to_file(args.output, div_info)


if __name__ == '__main__':
    main()
