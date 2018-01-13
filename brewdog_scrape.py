import re
import sys
from operator import itemgetter

import requests
from bs4 import BeautifulSoup as bs
from jinja2 import Environment, FileSystemLoader


BASE_BREWDOG_URL = 'https://www.brewdog.com/bars/uk/'
UNTAPPD = 'https://untappd.com/'
SEARCH = 'search?q={}&type=beer&sort=all'
SESSION = requests.Session()
SESSION.headers[
    'User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.131 Safari/537.36'


def get_beers(city):
    ''' Collects the taplist listed on brewdogs bar sites. '''
    print(f'{BASE_BREWDOG_URL}{city}')
    r = SESSION.get(f'{BASE_BREWDOG_URL}{city}')
    soup = bs(r.text, 'html.parser')
    tap_list = soup.find('div', id='tap-list')
    return tap_list.find_all('ul', class_='beer')


def beer_details(beer_soup):
    ''' takes a beer search result BS object as an argument and returns a list of all details '''
    return beer_soup.find_all('span')


def brewdog_beer_name(beer_details):
    return beer_details[0].text.strip()


def brewdog_abv(beer_details):
    return beer_details[4].text.strip(r'% ABV')


def brewdog_style(beer_details):
    return beer_details[1].text.strip()


def brewdog_measure(beer_details):
    return beer_details[2].text.strip()


def brewdog_brewery(beer_details):
    return beer_details[3].text.strip()


def search_untappd(beer):
    ''' Uses the beer from brewdog taplist to complete a search query returning a BS object of results'''
    search_beer = remove_char(beer).replace(' ', '+')
    r = SESSION.get(UNTAPPD + SEARCH.format(beer))
    soup = bs(r.text, 'html.parser')
    return soup.find_all('div', class_=re.compile('beer-item\s?'))


def untappd_rating(result):
    rating = float(result.find('span', class_='num').text.strip('()'))
    return round(rating, 2)


def untappd_beer_page(result):
    url = result.find('p', class_='name').a['href']
    return f'{UNTAPPD}{url}'.lstrip('/')


def untappd_desc(untappd_beer_url):
    r = SESSION.get(untappd_beer_url)
    soup = bs(r.text, 'html.parser')
    desc = soup.find('div', class_='beer-descrption-read-less').text.strip()
    return desc.strip('Show Less')


def untappd_label(result):
    return result.find('a', class_="label").img['src']


def remove_char(text):
    temp_list = []
    text_split = text.strip().split()
    for i in text_split:
        temp_list.append(re.sub(r'\W+', '', i))
    return ' '.join(temp_list).lower()


def create_template():
    ''' Creates a HTML document to present data returned from scraping '''
    template_vars = {'beers': beers}
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template("web_report/template.html")
    html_out = template.render(template_vars)
    with open(f'web_report/{city}_brewdog.html', 'w') as f:
        f.write(html_out)


if __name__ == '__main__':
    beers_on_tap = []
    city = sys.argv[1]
    for beer in get_beers(city):
        beer_dict = {}
        detail_list = beer_details(beer)
        beer_dict['name'] = brewdog_beer_name(detail_list)
        beer_dict['brewery'] = brewdog_brewery(detail_list)
        beer_dict['style'] = brewdog_style(detail_list)
        beer_dict['abv'] = brewdog_abv(detail_list)
        beer_dict['measure'] = brewdog_measure(detail_list)
        beer_dict['rating'], beer_dict['desc'] = 0, None
        search = search_untappd(beer_dict['name'])
        if len(search) > 0:
            for item in search:
                untappd_brewery = item.find('p', class_='brewery').a.text.lower()
                if beer_dict['brewery'].lower().split(' ')[0] in untappd_brewery.split(' ')[0]:
                    beer_dict['rating'] = untappd_rating(item)
                    untappd_url = untappd_beer_page(item)
                    beer_dict['desc'] = untappd_desc(untappd_url)
                    beer_dict['label'] = untappd_label(item)
                    break
        beers_on_tap.append(beer_dict)
    beers = sorted(beers_on_tap, key=itemgetter('rating'), reverse=True)
    create_template()
