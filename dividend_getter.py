from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from dividend_info import DividendInfo, DividendRecord
import logging
import traceback
import urllib
import urllib.request

import asyncio
from playwright.async_api import async_playwright

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
        page = urllib.request.urlopen(req)
        return page

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


    def parse_div_data(self, soup):
        tables = soup.find_all('table')
        for table in tables:
            if table.find('th', string='除息'):
                break
        else:
            self.log.error('cannot find ex-dividend table')

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


    def get_dividend_info(self, stock_id: str) -> DividendInfo:
        try:
            soup = self.get_web_soup(self.query_url % stock_id)
            div_data = self.parse_div_data(soup)
        except Exception as err:
            self.log.error('Failed to parse moneylink page for %s:' % stock_id)
            self.log.error(err)
            traceback.print_exc()
            return None
        else:
            info = DividendInfo(stock_id, self.parse_stockname(soup, stock_id))
            info.div_record = div_data
            return info


all_dividend_getters = {
    'moneylink': DividendMoneylink(),
    'goodinfo': DividendGoodinfo(),
}
