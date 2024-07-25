#!/usr/bin/env python3
import argparse

import io
import json
from datetime import datetime, date, timedelta
from dividend_info import DividendInfo, DividendRecord
import dividend_getter
import logging
import time
import os
import traceback


default_sleep_interval = dividend_getter.default_sleep_interval
default_watch_list_file = '~/.local/share/stock-robot/ex_dividend_watch_list.txt'
log = logging.getLogger(os.path.basename(__file__))

# TODO: parameterize this
prefer_getters = [dividend_getter.DividendMoneylink()]

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
    div_info = dividend_getter.get_many_dividend_info(stocks,
                                                      prefer_getters,
                                                      max_nr_record=1,
                                                      sleep_interval=args.sleep_interval)

    if args.output is None:
        print('None of output file')
    else:
        write_to_file(args.output, div_info)


if __name__ == '__main__':
    main()
