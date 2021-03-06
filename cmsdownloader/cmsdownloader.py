# utf-8
import os
import sys
import requests
from bs4 import BeautifulSoup
import argparse
import json
import tenacity
import logging
import time
from tqdm import tqdm
import io

def delete_last_lines(n=1):
    CURSOR_UP_ONE = '\x1b[1A'
    ERASE_LINE = '\x1b[2K'
    
    for _ in range(n):
        sys.stdout.write(CURSOR_UP_ONE)
        sys.stdout.write(ERASE_LINE)


class TqdmToLogger(io.StringIO):
    """
        Output stream for TQDM which will output to logger module instead of
        the StdOut.
    """    
    logger = None
    level = None
    buf = ''
    def __init__(self,logger,level=None):
        super(TqdmToLogger, self).__init__()
        self.logger = logger
        self.level = level or logging.INFO
        
    def write(self,buf):
        self.buf = buf.strip('\r\n\t ')
    def flush(self):
        self.logger.log(self.level, self.buf)




def logger():
    """
    Setup basic logging for console.

    Usage:
        Initialize the logger by adding the code at the top of your script:
        ``logger = logger()``

    TODO: add log file export
    """
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S'
                        )
    logger = logging.getLogger(__name__)
    return logger


logger = logger()

tqdm_out = TqdmToLogger(logger,level=logging.INFO)

assert os.environ['BAMMENS_API_USERNAME']
assert os.environ['BAMMENS_API_PASSWORD']

def get_login_cookies(session, baseUrl):
    """
        Get PHPSESSID cookie to use the API
    """
    logger.info("start login")
    loginPage = session.get(baseUrl + '/login')
    soup = BeautifulSoup(loginPage.text, "html.parser")
    csrf = soup.find("input", type="hidden")

    payload = {'_username': os.environ['BAMMENS_API_USERNAME'],
               '_password': os.environ['BAMMENS_API_PASSWORD'],
               '_csrf_token': csrf['value'],
               }

    # Fake browser header
    headers = {'user-agent': "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.98 Safari/537.36"}
    loginCheck = session.post(baseUrl + '/login_check',
                              data=payload,
                              headers=headers,
                              cookies=loginPage.cookies)
    # Response ok or not?
    if loginCheck.status_code == 200:
        soup = BeautifulSoup(loginCheck.text, "html.parser")
        # Check for name in html page which is only visible after login
        if 'dashboard' in soup.title.string.lower():
            logger.info("login succeeded!")
            return loginCheck.cookies
    if loginCheck.status_code == 401 or loginCheck == 403:
        logger.info('login failed!')


@tenacity.retry(wait=tenacity.wait_fixed(1),
                retry=tenacity.retry_if_exception_type(IOError))
def getContainer(session, cookies, endpoint, containerId):
    """
        Get The container data
    """
    url = baseUrl + '/api/' + endpoint + '/' + str(containerId) + '.json'
    #logger.info(url)
    containerURI = session.get(url, cookies=cookies)
    #logger.info(containerURI.headers)
    #logger.info(containerURI.text)
    if 'application/json' not in containerURI.headers["Content-Type"]:
        # DOES NOT WORK YET
        cookies = get_login_cookies(session, baseUrl)
        containerURI = session.get(url, cookies=cookies)
        containerData = containerURI.json()
        logger.info("get login?")
    else:
        containerData = containerURI.json()
    return containerData


def main(baseUrl, endpoints, folder):
    """Get Containers."""
    with requests.Session() as session:
        cookies = get_login_cookies(session, baseUrl)
        for endpoint in endpoints:
            data = []
            url = baseUrl + '/api/' + endpoint + '.json'

            ListURI = session.get(url, cookies=cookies)
            logger.info('Retrieving all objects from '.format(endpoint))
            List = ListURI.json()
            #logger.info(containerList['containers'][0])
            arrayName = list(List.keys())[0]

            IdList = [item['id'] for item in List[arrayName]]
            #logger.info(len(IdList), ' ', endpoint)
            for Id in tqdm(IdList, file=tqdm_out):
                item = getContainer(session, cookies, endpoint, Id)

                # status = '{} of {}'.format(str(n), str(len(IdList)))
                # logger.info(status)
                data.append(item)
                delete_last_lines()
            with open(folder + '/' + endpoint + '.json', 'w') as outFile:
                json.dump(data, outFile, indent=2)
        logger.info('Done with downloading!')


if __name__ == '__main__':
    desc = "download all containers from Bammens Api, for more info: https://bammensservice.nl/api/doc"
    parser = argparse.ArgumentParser(desc)
    parser.add_argument('datadir', type=str,
                        help='Local data directory.')
    args = parser.parse_args()

    baseUrl = 'https://bammensservice.nl'
    endpoints = ['containertypes','containers', 'wells']

    main(baseUrl, endpoints, args.datadir)
