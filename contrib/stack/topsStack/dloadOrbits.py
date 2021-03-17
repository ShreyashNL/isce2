#!/usr/bin/env python3

import os
import datetime
import argparse
import glob
import requests
from html.parser import HTMLParser

from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

fmt = '%Y%m%d'
today = datetime.datetime.now().strftime(fmt)

server = 'https://aux.sentinel1.eo.esa.int/'
queryfmt = '%Y-%m-%d'
datefmt = '%Y%m%dT%H%M%S'

S1Astart = '20140901'
S1Astart_dt = datetime.datetime.strptime(S1Astart, '%Y%m%d')

S1Bstart = '20160501'
S1Bstart_dt = datetime.datetime.strptime(S1Bstart, '%Y%m%d')


def cmdLineParse():
    '''
    Automated download of orbits.
    '''
    parser = argparse.ArgumentParser('S1A orbit downloader')
    parser.add_argument('--start', '-b', dest='start', type=str, default=S1Astart, help='Start date')
    parser.add_argument('--end', '-e', dest='end', type=str, default=today, help='Stop date')
    parser.add_argument('--dir', '-d', dest='dirname', type=str, default='.', help='Directory with precise orbits')
    return parser.parse_args()


def fileToRange(fname):
    '''
    Derive datetime range from orbit file name.
    '''

    fields = os.path.basename(fname).split('_')
    start = datetime.datetime.strptime(fields[-2][1:16], datefmt)
    stop = datetime.datetime.strptime(fields[-1][:15], datefmt)
    mission = fields[0]

    return (start, stop, mission)


def gatherExistingOrbits(dirname):
    '''
    Gather existing orbits.
    '''

    fnames = glob.glob(os.path.join(dirname, 'S1?_OPER_AUX_POEORB*'))
    rangeList = []

    for name in fnames:
        rangeList.append(fileToRange(name))

    print(rangeList)

    return rangeList


def ifAlreadyExists(indate, mission, rangeList):
    '''
    Check if given time spanned by current list.
    '''
    found = False

    if mission == 'S1B':
        if not validS1BDate(indate):
            print('Valid: ', indate)
            return True

    for pair in rangeList:
        if (indate > pair[0]) and (indate < pair[1]) and (mission == pair[2]):
            found = True
            break

    return found


def validS1BDate(indate):
    if indate < S1Bstart_dt:
        return False
    else:
        return True


def download_file(url, outdir='.', session=None):
    '''
    Download file to specified directory.
    '''

    if session is None:
        session = requests.session()

    path = os.path.join(outdir, os.path.basename(url))
    print('Downloading URL: ', url)
    request = session.get(url, stream=True, verify=False)

    try:
        request.raise_for_status()
        success = True
    except:
        success = False

    if success:
        with open(path, 'wb') as f:
            for chunk in request.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()

    return success


class MyHTMLParser(HTMLParser):

    def __init__(self, url):
        HTMLParser.__init__(self)
        self.fileList = []
        self.in_td = False
        self.in_a = False
        self.in_table = False
        self._url = url

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_td = True
        elif tag == 'a':
            self.in_a = True
            for name, val in attrs:
                if name == "href":
                    if val.startswith("http"):
                        self._url = val.strip()

    def handle_data(self, data):
        if self.in_td and self.in_a:
            if ('S1A_OPER' in data) or ('S1B_OPER' in data):
                # print(data.strip())
                self.fileList.append((self._url, data.strip()))
                print(self._url, data.strip())

    def handle_tag(self, tag):
        if tag == 'td':
            self.in_td = False
            self.in_a = False
        elif tag == 'a':
            self.in_a = False
            self._url = None


if __name__ == '__main__':
    '''
    Main driver.
    '''

    # Parse command line
    inps = cmdLineParse()

    ###Compute interval
    tstart = datetime.datetime.strptime(inps.start, fmt)
    tend = datetime.datetime.strptime(inps.end, fmt)

    days = (tend - tstart).days
    print('Number of days to check: ', days)

    ranges = gatherExistingOrbits(inps.dirname)

    for dd in range(days):
        indate = tstart + datetime.timedelta(days=dd + 19, hours=12)

        url = server + 'POEORB/' + str(indate.year).zfill(2) + '/' + str(indate.month).zfill(2) + '/' + str(
            indate.day).zfill(2) + '/'

        session = requests.session()
        match = None

        for mission in ['S1A', 'S1B']:
            if not ifAlreadyExists(indate, mission, ranges):

                try:
                    r = session.get(url, verify=False)
                    r.raise_for_status()

                    parser = MyHTMLParser(url)
                    parser.feed(r.text)

                    for resulturl, result in parser.fileList:
                        match = os.path.join(resulturl, result)
                        if match is not None:
                            success = True
                except:
                    pass

                if match is not None:
                    download_file(match, inps.dirname, session)
                else:
                    print('Failed to find {1} orbits for tref {0}'.format(indate, mission))

            else:
                print('Already exists: ', mission, indate)

    print('Exit dloadOrbits Successfully')
