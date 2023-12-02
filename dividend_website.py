from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from dividend_info import DividendInfo, DividendRecord
import logging
import traceback
import urllib
import urllib.request

class DividendWebsite:
    def __init__(self):
        # use derived class name to create logger
        self.log = logging.getLogger(self.__class__.__name__)
        self.name = self.__class__.__name__

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
        super().__init__()
        self.query_url = 'https://goodinfo.tw/StockInfo/StockDividendSchedule.asp?STOCK_ID=%s'

    def parse_div_data(self, soup: BeautifulSoup) -> list[DividendRecord]:
        div_table = soup.find('div', attrs={'id': 'divDetail'})
        div_table = div_table.find('table')
        rows = div_table.find_all('tr', attrs={'align': 'center'})
        data = []
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            div_date = datetime.strptime(cols[3][0:8], '%y\'%m/%d').date() if len(cols[3]) > 0 else None
            payable_date = datetime.strptime(cols[7][0:8], '%y\'%m/%d').date() if len(cols[7]) > 0 else None
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
            soup = self.get_web_soup(self.query_url % stock_id)
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
        super().__init__()
        self.query_url = 'https://ww2.money-link.com.tw/TWStock/StockBasic.aspx?SymId=%s'


    def parse_stockname(self, soup: BeautifulSoup) -> str:
        try:
            name = soup.find('meta')['content'].split(',')[1]
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
            info = DividendInfo(stock_id, self.parse_stockname(soup))
            info.div_record = div_data
            return info

