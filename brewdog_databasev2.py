import re
import sqlite3
import time
import datetime
from random import randint

import requests
from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BREWDOG_BARS = 'https://www.brewdog.com'
db = sqlite3.connect('beer_db.sqlite')
c = db.cursor()
UNTAPPD = 'https://untappd.com/'
SEARCH = 'search?q={}&type=beer&sort=all'
SESSION = requests.Session()
SESSION.headers[
    'User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.131 Safari/537.36'


def open_chrome():
    path = r'/home/levo/Documents/projects/ChromeDriver/chromedriver'
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    browser = webdriver.Chrome(path, chrome_options=chrome_options)
    browser.set_page_load_timeout(60)
    browser.implicitly_wait(20)
    return browser


def add_bars_to_db():
    bars_list = []
    browser.get(f'{BREWDOG_BARS}/bars/uk/')
    soup = bs(browser.page_source, 'html.parser')
    bars = soup.find_all('div', class_='bar')
    bars_list = [(bar.find('div', class_='title').text, bar.a['href']) for bar in bars]
    for bar in bars:
        bars_list.append((bar.find('div', class_='title').text.strip(), bar.a['href']))
    c.executemany(''' INSERT OR IGNORE INTO bars (bar, url) VALUES (?, ?)''',
                  (bars_list))
    db.commit()


def tap_list(soup):
    beer_data = []
    tap_list = soup.find_all('ul', class_='beer')
    print(f'{len(tap_list)} beers on tap')
    for beer in tap_list:
        beer_dict = {}
        beer_dict['date'] = datetime.datetime.today().strftime('%d%m%Y')
        beer_dict['bar_location'] = soup.find('span', class_='title').text.strip()
        beer_details = beer.find_all('span')
        beer_dict['beer_name'] = beer_details[0].text.strip()
        beer_dict['brewery'] = beer_details[3].text.strip()
        beer_dict['abv'] = beer_details[4].text.strip(r'% ABV')
        beer_dict['style'] = beer_details[1].text.strip()
        beer_id = check_beer_in_db(beer_dict)
        if not beer_id:
            beer_dict['untappd'] = untappd_search(beer_dict['beer_name'], beer_dict['brewery'])
        else:
            c.execute(
                ''' SELECT rating, image_url, description FROM beers WHERE id = ? ''', (beer_id,))
            beer_from_db = c.fetchone()
            beer_dict['untappd'] = {'rating': beer_from_db[0],
                                    'img': beer_from_db[1], 'desc': beer_from_db[2]}
        beer_data.append(beer_dict)
    return beer_data


def check_beer_in_db(beer_dict):
    c.execute(''' SELECT id, date_added, name FROM beers WHERE name = ? ''',
              (beer_dict['beer_name'],))
    beer = c.fetchone()
    if beer is not None:
        if beer[1] == datetime.datetime.today().strftime('%d%m%Y'):
            return beer[0]
        else:
            return False
    return False


def insert_to_database(beers):
    for beer in beers:
        c.execute(''' INSERT OR IGNORE INTO brewery (name) VALUES (?) ''', (beer['brewery'], ))
        c.execute(''' INSERT OR IGNORE INTO style (style) VALUES (?) ''', (beer['style'], ))
        c.execute(''' SELECT id FROM brewery WHERE name = ? ''', (beer['brewery'], ))
        brewery_id = c.fetchone()[0]
        c.execute(''' SELECT id FROM style WHERE style = ? ''', (beer['style'], ))
        style_id = c.fetchone()[0]
        c.execute(''' INSERT OR IGNORE INTO
        beers (date_added, name, brewery_id, style_id, abv, rating, image_url, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (beer['date'], beer['beer_name'], brewery_id, style_id, beer['abv'],
                   beer['untappd']['rating'], beer['untappd']['img'], beer['untappd']['desc']))
        c.execute(' SELECT id FROM bars WHERE bar=? ', (beer['bar_location'],))
        location_id = c.fetchone()[0]
        c.execute(' SELECT id FROM beers WHERE name = ? ', (beer['beer_name'],))
        beer_id = c.fetchone()[0]
        try:
            c.execute(' INSERT OR IGNORE INTO beer_location VALUES (?, ?) ', (beer_id, location_id))
        except TypeError:
            print(
                f'couldnt add {beer["beer_name"]} {"beer_id"} to {beer["bar_location"]} {location_id}')
            continue
    db.commit()


def untappd_search(beer, brewery):
    untappd_data = {}
    r = SESSION.get(UNTAPPD + SEARCH.format(beer))
    soup = bs(r.text, 'html.parser')
    search = soup.find_all('div', class_=re.compile('beer-item\s?'))
    if len(search) > 0:
        for beer in search:
            untappd_brewery = beer.find('p', class_='brewery').a.text.lower()
            if brewery.lower().split(' ')[0] in untappd_brewery.split(' ')[0]:
                rating = float(beer.find('span', class_='num').text.strip('()'))
                beer_page = beer.find('p', class_='name').a['href'].lstrip('/')
                untappd_data['rating'] = round(rating, 2)
                untappd_data['img'] = beer.find('a', class_="label").img['src']
                time.sleep(randint(1, 5))
                untappd_data['desc'] = untappd_desc(beer_page)
                time.sleep(randint(1, 5))
                break
            else:
                untappd_data['rating'] = 0
                untappd_data['desc'] = ''
                untappd_data['img'] = 'https://untappd.akamaized.net/site/assets/images/temp/badge-beer-default.png'
    else:
        untappd_data['rating'] = 0
        untappd_data['desc'] = ''
        untappd_data['img'] = 'https://untappd.akamaized.net/site/assets/images/temp/badge-beer-default.png'
    return untappd_data


def untappd_desc(untappd_beer_url):
    r = SESSION.get(f'{UNTAPPD}{untappd_beer_url}')
    soup = bs(r.text, 'html.parser')
    try:
        desc = soup.find('div', class_='beer-descrption-read-less').text.strip()
    except AttributeError:
        return 'None'
    return desc.strip('Show Less')


if __name__ == '__main__':
    c.executescript('''
    DROP TABLE IF EXISTS bars;
    DROP TABLE IF EXISTS beer_location;

    CREATE TABLE bars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bar TEXT NOT NULL UNIQUE,
        url TEXT );

    CREATE TABLE beer_location (
        beer_id INTEGER NOT NULL,
        bar_id INTEGER,
        PRIMARY KEY (beer_id, bar_id));

    CREATE TABLE IF NOT EXISTS beers (
        id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
        date_added TEXT,
        name TEXT UNIQUE,
        brewery_id INTEGER,
        style_id INTEGER,
        abv REAL,
        rating REAL,
        "image_url" TEXT,
        description TEXT );

        CREATE TABLE IF NOT EXISTS "brewery" (
            id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            name TEXT UNIQUE );

        CREATE TABLE IF NOT EXISTS style (
            id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            style TEXT UNIQUE );

        ''')

    browser = open_chrome()
    add_bars_to_db()
    fetch_urls = c.execute(' SELECT url FROM bars ')
    city_urls = fetch_urls.fetchall()
    for city in city_urls:
        print(f'Fetching {city[0]}')
        browser.get(f'{BREWDOG_BARS}{city[0]}')
        city_soup = bs(browser.page_source, 'html.parser')
        insert_to_database(tap_list(city_soup))
    db.close()
    browser.close()
