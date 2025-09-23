from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from dividend_info import DividendInfo, DividendRecord
import logging
import os
import time
import traceback
from typing import Dict, List
import urllib
import urllib.request
from urllib.error import HTTPError, URLError

import asyncio
from playwright.async_api import async_playwright

log = logging.getLogger(os.path.basename(__file__))

# To prevent DOS protection, in seconds
default_sleep_interval = 2
default_max_nr_record = 1

class DividendWebsite:
    def __init__(self, name: str = None):
        # use derived class name to create logger
        self.log = logging.getLogger(self.__class__.__name__)
        if name == None:
            self.name = self.__class__.__name__
        else:
            self.name = name

    def get_web_page(self, url: str):
        self.log.debug('fetch web page from %s' % url)
        req = urllib.request.Request(
                url,
                data=None,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) '
                                  'Chrome/35.0.1916.47 Safari/537.36 '
                })

        retry_cnt = 0
        max_retry = 2
        retry_interval_sec = 2
        while retry_cnt < max_retry:
            try:
                response = urllib.request.urlopen(url)
                encoding = response.info().get_content_charset() or 'utf-8'
                html_bytes = response.read()
                html_string = html_bytes.decode(encoding, 'ignore')
                return html_string
            except Exception as err:
                self.log.warning("Exception occured: %s" % err)
                self.log.debug("Retry (%d) after %d second.." % (retry_cnt, retry_interval_sec))
                time.sleep(retry_interval_sec)
                retry_cnt += 1
        return None


    def get_web_soup(self, url: str) -> BeautifulSoup:
        page = self.get_web_page(url)
        soup = BeautifulSoup(page, 'html.parser')
        return soup

    def get_dividend_info(self, stock_id: str) -> DividendInfo:
        self.log.critical('To be implemented by derived class')
        pass


class DividendGoodinfo(DividendWebsite):
    def __init__(self) -> None:
        super().__init__(name='goodinfo')
        self.query_url = 'https://goodinfo.tw/tw/StockDividendSchedule.asp?STOCK_ID=%s'
        self.page_redirect_timeout_ms = 2000


    async def fetch_page(self, url):
        self.log.debug('fetch web page from %s' % url)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url)
            await page.wait_for_timeout(self.page_redirect_timeout_ms)  # Wait for JavaScript redirect
            content = await page.content()
            await browser.close()
            return content

        return None


    def get_html_content(self, url):
        html_content = asyncio.run(self.fetch_page(url))
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup


    def parse_div_data(self, soup: BeautifulSoup) -> list[DividendRecord]:
        div_table = soup.find('div', attrs={'id': 'divDetail'}).find('table')
        rows = div_table.find_all('tr', attrs={'align': 'center'})
        data = []
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            div_date = datetime.strptime(cols[3][0:9], '\'%y/%m/%d').date() if len(cols[3]) > 0 else None
            payable_date = datetime.strptime(cols[7][0:9], '\'%y/%m/%d').date() if len(cols[7]) > 0 else None
            cash = float(cols[14])
            stock = float(cols[17])
            if cash == 0.0 and stock == 0.0:
                continue

            d = DividendRecord(div_date, payable_date, cash, stock)
            self.log.debug(d)
            data.append(d)

        return data


    def parse_stockname(self, soup: BeautifulSoup) -> str:
        top = soup.find('table', attrs={'class': 'b1 r10_0 box_shadow'}).find_all('td')
        return top[2].text.split()[1]

    def get_dividend_info(self, stock_id: str) -> DividendInfo:
        try:
            soup = self.get_html_content(self.query_url % stock_id)
            div_data = self.parse_div_data(soup)
        except Exception as err:
            self.log.error('Failed to parse goodinfo for %s:' % stock_id)
            self.log.error(err)
            traceback.print_exc()
            return None
        else:
            info = DividendInfo(stock_id, self.parse_stockname(soup))
            info.div_record = div_data
            return info



class DividendMoneylink(DividendWebsite):
    def __init__(self) -> None:
        super().__init__(name='moneylink')
        self.query_url = 'https://ww2.money-link.com.tw/TWStock/StockBasic.aspx?SymId=%s'


    def parse_stockname(self, soup: BeautifulSoup, stock_id: str) -> str:
        try:
            name = soup.find('meta')['content'].split(',')[1]
            # stockname in moneylink are name+stock_id, try to remove the stock_id
            # which is concated after name
            if name.endswith(stock_id):
                return name[:-len(stock_id)]
            return name
        except Exception as err:
            return 'Unknown'


    def chinese_date_to_ad_date(self, date_str: str):
        _date_str = date_str.split('/')
        _date_str[0] = str(int(_date_str[0]) + 1911)
        return '/'.join(_date_str)


    def parse_div_table_etf(self, table) -> list[DividendRecord]:
        rows = table.find_all('tr')
        data = []
        for row in rows[2:]:  # skip row0 and row1 (title)
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            div_date = datetime.strptime(self.chinese_date_to_ad_date(cols[3]), '%Y/%m/%d').date() if len(cols[4]) > 0 else None
            payable_date = datetime.strptime(self.chinese_date_to_ad_date(cols[5]), '%Y/%m/%d').date() if len(
                cols[4]) > 0 else None
            cash = float(cols[4])
            stock = 0
            d = DividendRecord(div_date, payable_date, cash, stock)
            self.log.debug(d)
            data.append(d)
        return data


    def parse_div_table_normal(self, table) -> list[DividendRecord]:
        # Normal stock in moneylink has only one ex-dividend record
        try:
            text = table.find_all('tr')[4].find_all('td')[0].text
            if text == '-':
                stock = 0
            else:
                stock = float(text)
        except ValueError:
            self.log.error("分析除權股息失敗:%s" % text)
            return None

        try:
            text = table.find_all('tr')[3].find_all('td')[0].text
            if text == '-':
                cash = 0.0
            else:
                cash = float(text)
        except ValueError:
            self.log.error("分析除息股利失敗:%s" % text)
            return None

        td = table.find_all('tr')[1].find_all('td')[2]
        for span in td.find_all('span', class_='mg'):
            span.decompose()
        try:
            div_date = datetime.strptime(td.text, '%Y/%m/%d').date()
        except ValueError:
            self.log.error("分析除權息日期失敗:%s" % td.text)
            return None

        td = table.find_all('tr')[2].find_all('td')[2]
        for span in td.find_all('span', class_='mg'):
            span.decompose()
        try:
            payable_date = datetime.strptime(td.text, '%Y/%m/%d').date()
        except ValueError:
            self.log.error("分析除權息日期失敗:%s" % td.text)
            return None

        d = DividendRecord(div_date, payable_date, cash, stock)
        self.log.debug(d)

        return [d]


    def parse_div_data(self, stock_id, soup) -> list[DividendRecord]:
        tables = soup.find_all('table')
        for table in tables:
            if table.find('th', string='除息'):
                break
        else:
            self.log.error('cannot find ex-dividend table')
            return None

        nr_th = len(table.find_all('th', id='HEAD1'))
        if (nr_th == 1):
            self.log.debug('%s is probably ETF.' % stock_id)
            return self.parse_div_table_etf(table)
        elif (nr_th == 3):
            self.log.debug('%s is probably normal stock.' % stock_id)
            return self.parse_div_table_normal(table)
        else:
            self.log.warning('%s is unknown stock type. Try normal one' % stock_id)
            return self.parse_div_table_normal(table)


    def get_dividend_info(self, stock_id: str) -> DividendInfo:
        try:
            soup = self.get_web_soup(self.query_url % stock_id)
            div_data = self.parse_div_data(stock_id, soup)
        except Exception as err:
            self.log.error('Failed to parse moneylink page for %s:' % stock_id)
            self.log.error(err)
            traceback.print_exc()
            return None
        else:
            info = DividendInfo(stock_id, self.parse_stockname(soup, stock_id))
            info.div_record = div_data
            return info


class DividendMoneydj(DividendWebsite):
    '''
    Use the overall table to get recent div data in one shot to avoid DOS detection
    '''
    def __init__(self) -> None:
        super().__init__(name='moneydj')
        self.query_url = 'https://www.moneydj.com/Z/ZE/ZEB/ZEB.djhtm'
        self.soup = self.get_web_soup(self.query_url)
        self.soup_string = str(self.soup)

    def get_stockname(self, found_script) -> str:
        try:
            text = found_script.string.strip().split("'")
            stockname = text[3]
            return stockname
        except Exception as err:
            self.log.error('Failed to parse stockname from %s:' % found_script)
            self.log.error(err)
            traceback.print_exc()
            return 'None'


    def parse_div_info(self, found_tr) -> list[DividendRecord]:
        div_data = []
        td_list = found_tr.find_all('td')
        try:
            date_string = td_list[1].get_text(strip=True)
            div_date = datetime.strptime(date_string, '%Y/%m/%d').date()
        except ValueError:
            self.log.error("分析除息日期失敗:%s" % td_list)
            div_date = 0

        try:
            cash = float(td_list[4].get_text(strip=True))
        except ValueError:
            self.log.error("分析現金股利失敗:%s" % td_list)
            cash = 0.0

        try:
            date_string = td_list[5].get_text(strip=True)
            payable_date = datetime.strptime(date_string, '%Y/%m/%d').date()
        except ValueError:
            self.log.error("分析股利發放日期失敗:%s" % td_list)
            payable_date = 0

        d = DividendRecord(div_date, payable_date, cash, 0.0)
        self.log.debug(d)
        div_data.append(d)

        return div_data

    def get_dividend_info(self, stock_id: str) -> DividendInfo:
        found_script = None
        found_tr = None
        try:
            all_scripts = self.soup.find_all('script')
            for script in all_scripts:
                found_content = script.string
                if found_content and stock_id in found_content:
                    found_script = script
                    break
            else:
                self.log.debug('Not found record for %s' % stock_id)

            if found_script:
                found_tr = found_script.find_parent('tr')
                if not found_tr:
                    self.log.error("Found script, but cannot found parent <tr>")
        except Exception as err:
            self.log.error('Failed to parse moneylink page for %s:' % stock_id)
            self.log.error(err)
            traceback.print_exc()
            return None
        else:
            info = None
            if found_script:    # Case: found one
                stock_name = self.get_stockname(found_script)
                info = DividendInfo(stock_id, stock_name=stock_name)
                if found_tr:
                    info.div_record = self.parse_div_info(found_tr)
                else:           # Case: probably web paging paring error
                    info.div_record = []
            else:               # Case: Not found any, make an empty one to avoid error
                info = DividendInfo(stock_id, 'NA')
                div_data = DividendRecord(0, 0, 0, 0)
                info.div_record = [div_data]

            return info


all_dividend_getters = {
    'moneylink': DividendMoneylink(),
    'moneydj': DividendMoneydj(),
    'goodinfo': DividendGoodinfo(),
}


def get_dividend_info(stock_id: str,
                      dividend_getters=all_dividend_getters.values(),
                      max_nr_record: int=default_max_nr_record) \
                     -> DividendInfo:
    for getter in dividend_getters:
        log.debug('Using %s to get %s info' % (getter.name, stock_id))
        info = getter.get_dividend_info(stock_id)
        if info is not None:
            if len(info.div_record) > 0:
                if info.div_record[0].cash > 0.0 and \
                   info.div_record[0].payable_date is None:  # probably ETF
                    # Probably not yet decide payble_date
                    log.warning("The latest record has cash=%.2f but payble_date is None." %
                                info.div_record[0].cash)

                if len(info.div_record) > max_nr_record:
                    info.div_record = info.div_record[0:max_nr_record]

            return info
    else:
        log.error('Failed to get ex dividend data for %s:' % stock_id)
        return None


def get_many_dividend_info(stocks: list,
                           dividend_getters=all_dividend_getters.values(),
                           max_nr_record: int=default_max_nr_record,
                           sleep_interval: int=default_sleep_interval) -> Dict[str, DividendInfo]:
    div_info = {}
    for stock_id in stocks:
        log.info('Obtaining %s...' % stock_id)
        __div_info = get_dividend_info(stock_id, dividend_getters)

        if __div_info is None:
            __div_info = DividendInfo(stock_id=stock_id, stock_name="NA")
            __div_info.error = '找不到 %s 的任何資料，可能網頁分析失敗' % stock_id
            log.error(__div_info.error)
        elif len(__div_info.div_record) == 0:
            __div_info.error = '%s(%s) 最近沒有除權息資料，可能真的缺乏除權息資料' % \
                                (__div_info.stock_name, __div_info.stock_name)
            log.warning(__div_info.error)
        else:
            log.info('%s(%s) %s' % (__div_info.stock_id, __div_info.stock_name, __div_info.div_record[0]))

        div_info[stock_id] = __div_info

        log.debug("Sleep %d seconds to avoid DOS detecting.." % sleep_interval)
        time.sleep(sleep_interval)

    return div_info


if __name__ == '__main__':
    log_format = '[%(levelname)7s] %(asctime)s %(name)s %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    prefer_getters = [DividendMoneydj()]
    # prefer_getters = all_dividend_getters.values()

    stocks = ['1784']
    sleep_interval = 1

    div_info = get_many_dividend_info(stocks,
                                      prefer_getters,
                                      max_nr_record=1,
                                      sleep_interval=sleep_interval)

    print(div_info)
