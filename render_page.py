import sqlite3
from sys import argv

from jinja2 import Environment, FileSystemLoader

db = sqlite3.connect('beer_db.sqlite')
c = db.cursor()
city = argv[1].title()


def get_beers():
    c.execute('''  SELECT beers.name, style.style, beers.abv, brewery.name, bars.bar, beers.rating, beers.description, beers.image_url
        FROM beers JOIN bars JOIN beer_location JOIN brewery JOIN style
        ON beer_location.beer_id = beers.id AND beer_location.bar_id = bars.id AND beers.brewery_id = brewery.id AND beers.style_id = style.id
        WHERE bars.bar = ?
        ORDER BY beers.rating DESC
    ''',
              (city, ))
    return c.fetchall()


def create_template(beers):
    ''' Creates a HTML document to present data returned from scraping '''
    template_vars = {'beers': beers}
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template("web_report/template.html")
    html_out = template.render(template_vars)
    with open(f'web_report/{city.lower()}_brewdog.html', 'w') as f:
        f.write(html_out)


if __name__ == '__main__':
    create_template(get_beers())
