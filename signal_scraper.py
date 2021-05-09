from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import re, json, requests, time
from pprint import pprint
import pandas as pd
import numpy as np

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


base_url = 'https://signal.nfx.com'


# Makes tasty soup
def soup_maker(url):
    request = Request(url=url, headers={'user-agent': 'web-parser'})
    response = urlopen(request)
    soup = BeautifulSoup(response, 'html.parser')
    return soup


# Grabs a list of companies and their urls
def firm_parser(base_url):

    # This grabs a list of firms from the website
    firm_page_url = f'{base_url}/investor-lists/top-marketplaces-seed-investors'

    soup = soup_maker(firm_page_url)
    firm_dict = {}
    # finds links for different companies and their name, places it into a dictionary
    pattern = re.compile(r'^/firms/')
    firm_html = soup.find_all('a', href=pattern)
    for firm_item in firm_html:
        firm_name = firm_item.text
        firm_url = f'{base_url}{firm_item["href"]}'
        firm_dict.setdefault(firm_name, firm_url)
    '''firm_list_url = [firm_url['href'] for firm_url in firm_list_html]
    # turns html results into list.
    firm_list = list(set([firm_name.text for firm_name in firm_list_html]))
    print(firm_list in firm_list_url)'''

    return firm_dict


# Grabs the names of all the persons associated with a particular company
def firm_personnel_parser(base_url, firm_dict):
    personnel_dict = {}
    for firm_name, firm_url in firm_dict.items():
        personnel_dict.setdefault(firm_name, {})

        soup = soup_maker(firm_url)
        card_grid = soup.find('div', attrs={'class': 'vc-search-card-grid'})
        card_name = card_grid.find_all('a', attrs={'class': 'vc-search-card-name'})
        for card_name_item in card_name:
            personnel_dict[firm_name].setdefault(card_name_item.text, {'link': f"{base_url}{card_name_item['href']}"})
        break
    return personnel_dict


# Uses selenium to click the "See all investments on record" button
def personnel_past_investment_clicker(url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    browser = webdriver.Chrome(executable_path='chromedriver.exe', options=chrome_options)
    browser.get(url)
    time.sleep(3)
    all_investments_button = browser.find_element_by_css_selector('#vc-profile > div > div.col-sm-6.col-xs-12 > div:nth-child(4) > div > div > button')
    all_investments_button.click()
    time.sleep(3)
    page_html = browser.page_source
    time.sleep(3)
    browser.quit()
    return page_html


# Builds a summary of an investor
def personnel_summary_parser(html_page, name, detail):
    details_dict = {}
    soup = BeautifulSoup(html_page, 'html.parser')
    summary = soup.find_all('div', attrs={'class': 'col-xs-7'})
    id = soup.find('span', attrs={'class': 'white-50 ml2 f4'}).text
    role = soup.find('h3', attrs={'class': 'subheader lower-subheader pb2'}).text
    investment_range = summary[1].text
    sweet_spot = summary[2].text
    investments_on_record = summary[3].text
    current_fund_size = summary[4].text
    details_dict.setdefault('summary',
                            {'id': id.lstrip('(').rstrip(')'),
                             'name': name,
                             'link': detail['link'],
                             'role': role,
                             'investment_range': investment_range,
                             'sweet_spot': sweet_spot,
                             'investments_on_record': investments_on_record,
                             'current_fund_size': current_fund_size})
    summary_df = pd.DataFrame.from_dict(details_dict)
    return summary_df


# Scrapes selected investors recorded investments.
def personnel_info_parser(html_page):
    soup = BeautifulSoup(html_page, 'html.parser')

    table_head = soup.table.find_all('thead', attrs={'class': 'past-investments-table-head'})
    table_body = soup.table.find_all('tbody', attrs={'class': 'past-investments-table-body'})

    headers_list = [head for head in table_head[0].find('tr')]
    sublist = [str(i) for i in headers_list[1] if str(i) not in ('<i class="gray-dot-separator"></i>')]
    cleaned_headers_list = [headers_list[0].text]
    cleaned_headers_list.extend(sublist)
    cleaned_headers_list.append(headers_list[2].text)
    cleaned_headers_list.append('Co-Investors')
    table_rows = table_body[0].find_all('tr')
    investment_record = []

    for row in table_rows:
        intermediary_list = []
        row = row.find_all('td')
        if len(row) <= 1:
            investment_record[-1].append(row[0].text.replace('Co-investors: ', ''))
        else:
            intermediary_list.append(row[0].text)
            stage_list = []
            date_list = []
            round_list = []
            decompressor = row[1].find_all('div')
            if len(decompressor) > 1:
                for decom_index in range(len(decompressor)):
                    decompressed_list = decompressor[decom_index].prettify().split('<i class="white-dot-separator"></i>')[0].split('\n')
                    try:
                        decompressed_list = [decompressed_list[sec_index].strip(' ') for sec_index in [1, 4, 7]]

                    except:
                        decompressed_list = [decompressed_list[sec_index].strip(' ') for sec_index in [1, 4]]
                try:
                    stage_list.append(decompressed_list[0].strip())
                    date_list.append(decompressed_list[1].strip())
                    round_list.append(decompressed_list[2].strip())
                except:
                    stage_list.append(decompressed_list[0].strip())
                    date_list.append(decompressed_list[1].strip())
                    round_list.append('')

                intermediary_list.append(stage_list)
                intermediary_list.append(date_list)
                intermediary_list.append(round_list)

            else:

                decompressed_list = decompressor[0].prettify().split('<i class="white-dot-separator"></i>')[0].split('\n')
                try:
                    decompressed_list = [decompressed_list[thir_index].strip(' ') for thir_index in [1, 4, 7]]
                except:
                    decompressed_list = [decompressed_list[thir_index].strip(' ') for thir_index in [1, 4]]

                intermediary_list.extend(decompressed_list)

            intermediary_list.append(row[2].text)
            investment_record.append(intermediary_list)

    investment_df = pd.DataFrame(investment_record, columns=cleaned_headers_list)
    return investment_df


# Mergers multiple dataframes into one.
def dataframe_merger(df_list):
    result = pd.concat(df_list)
    return result


def run(base_url):
    firm_dict = firm_parser(base_url)
    personal_dict = firm_personnel_parser(base_url, firm_dict)
    for firm, personnel in personal_dict.items():
        for name, details in personnel.items():
            personnel_link = details['link']
            investor_page = personnel_past_investment_clicker(personnel_link)
            result = dataframe_merger([personnel_summary_parser(investor_page, name, details), personnel_info_parser(investor_page)])
            print(result.info())
            print(result.head(8))


run(base_url)
