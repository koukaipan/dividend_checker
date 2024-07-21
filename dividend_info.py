from datetime import datetime, date, timedelta
from typing import Dict

class DividendRecord:
    def __init__(self):
        self.div_date = None
        self.payable_date = None
        self.cash = 0.0
        self.stock = 0.0

    def __init__(self, div_date:datetime.date, payable_date:datetime.date,
                 cash:float, stock:float):
        self.div_date = div_date
        self.payable_date = payable_date
        self.cash = cash
        self.stock = stock

    def __str__(self) -> str:
        return 'div_date:%s payable_date:%s cash:%.2f stock:%.2f' % \
               (str(self.div_date), str(self.payable_date),
                self.cash, self.stock)


class DividendInfo:
    def __init__(self):
        self.stock_id = 0
        self.stock_name = ''
        self.div_record = []
        self.error = None

    def __init__(self, stock_id: str, stock_name: str):
        self.stock_id = stock_id
        self.stock_name = stock_name
        self.div_record = []
        self.error = None

    def filter_future_event(self):
        future_div_record = []
        for d in self.div_record:
            # skip old events
            if not d.payable_date is None and d.payable_date < date.today():
                break

            if d.div_date is None or d.payable_date is None:
                continue

            future_div_record.append(d)

        self.div_record = future_div_record

    def __str__(self) -> str:
        return 'id:%s name:%s record:%s' % (self.stock_id, self.stock_name, str(self.div_record[0]))

    def __repr__(self) -> str:
        records = '\n'.join([str(_r) for _r in self.div_record])
        return 'id:%s\n name:%s\n record:%s' % (self.stock_id, self.stock_name, records)

    def to_dict(self) -> Dict[str, str]:
        d = {}
        d['stock_id'] = self.stock_id
        d['stock_name'] = self.stock_name
        d['error'] = 'None' if self.error is None else self.error
        d['div_record'] = []

        for r in self.div_record:
            record = {}
            record['div_date'] = str(r.div_date)
            record['payable_date'] = str(r.payable_date)
            record['cash'] = "%.4f" % r.cash
            record['stock'] = "%.4f" % r.stock
            d['div_record'].append(record)

        return d
