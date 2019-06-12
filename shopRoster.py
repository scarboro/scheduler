import bisect
import datetime
import re
import time
import shopTech

class ShopRoster(object):
    def __init__(self, gsheets, gmail, sheet_id, anchor):

        self.gsheets = gsheets
        self.gmail = gmail

        self.anchor_date = datetime.datetime.strptime(anchor, '%Y-%m-%d')
        self.getTechs(sheet_id)

    def getSize(self, sheet_id):
        ''' Determines the size of a spreadsheet '''

        request = self.gsheets.spreadsheets().get(spreadsheetId=sheet_id)
        result = request.execute()

        properties = result['sheets'][0]['properties']['gridProperties']
        cols = properties['columnCount']
        rows = properties['rowCount']

        chars = []
        while cols > 0:
            cols, remainder = divmod(cols - 1, 26)
            chars.insert(0, chr(65 + remainder))

        width = ''.join(chars)
        height = rows

        return 'A1:{}{}'.format(width, height)

    def getTechs(self, sheet_id):
        ''' Loads techs from a spreadsheet '''

        size = self.getSize(sheet_id)
        request = self.gsheets.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=size)
        result = request.execute()

        params = {}

        # The first row of the results spreadsheet contains column titles
        params['col_names'] = result['values'][0]
        params['col_index'] = {n: i for i, n in enumerate(params['col_names'])}

        # Find columns that correspond to availability data
        re_week = re.compile(r'Conflicts by Quarter \[(.*)\]')
        re_hour = re.compile(r'Conflicts by Week \[(\d+):\d+\]')
        match_week = [re_week.match(name) for name in params['col_names']]
        match_hour = [re_hour.match(name) for name in params['col_names']]

        params['week_cols'] = [i for i, m in enumerate(match_week) if m]
        params['hour_cols'] = [i for i, m in enumerate(match_hour) if m]

        params['first_hour'] = int(match_hour[params['hour_cols'][0]].group(1))
        params['last_hour'] = int(match_hour[params['hour_cols'][-1]].group(1))
        params['week_names'] = [m.group(1) for m in match_week if m]
        params['day_names'] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                               'Friday', 'Saturday', 'Sunday']

        techs = [shopTech.Tech(row, params) for row in result['values'][1:]]

        self.techs = techs
        return self.techs

    def matchShifts(self, shifts):
        ''' Matches techs to shifts '''

        for t, tech in enumerate(self.techs):
            tech.matchShifts(t, shifts)

    def sendEmails(self):
        ''' Sends emails to techs '''

        requests = [tech.sendEmail(self.gmail) for tech in self.techs]
        #batch = self.gmail.new_batch_http_request()

        for r, request in enumerate(requests):
            if request:
                try:
                    time.sleep(0.01)
                    request.execute()
                except Exception:
                    print(self.techs[r])
                    continue
            #batch.add(request)
        #batch.execute()
