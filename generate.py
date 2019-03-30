#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, shutil, ftplib, io, datetime
from backports import csv
from collections import defaultdict
from ConfigParser import ConfigParser
from jinja2 import Environment, FileSystemLoader
opj = os.path.join
ope = os.path.exists

#ROOT = os.split(os.path.realpath(__file__))[0]
ROOT = '/Users/roed/Documents/Marissa/diane-szczepaniak-website'
CONFIG = ConfigParser()
JINJA_ENV = Environment(loader=FileSystemLoader(os.path.join(ROOT,'templates')))

with open(opj(ROOT,'config.ini')) as F:
    CONFIG.readfp(F)
def load_from_sheets():
    drive_folder = opj(ROOT,'google_drive')
    data = {}
    header = {}
    keys = ['images','events','sections','press','resume','poems']
    for key in keys:
        data[key] = None
        header[key] = CONFIG.get('TSV',key)
    for filename in os.listdir(drive_folder):
        ext = os.path.splitext(filename)[1]
        if ext in ['.csv', '.xlsx', '.ods', '.pdf']:
            raise ValueError("You must download files as Tab-separated values")
        elif ext == '.tsv':
            with io.open(opj(drive_folder, filename), "r", encoding="utf-8") as F:
                contents = list(csv.reader(F,delimiter=u'\t'))
                #contents = [[col.replace(u'&',u'&amp;') for col in row] for row in contents]
            for key in keys:
                if u';'.join(contents[0]) == header[key]:
                    if data[key] is not None:
                        raise ValueError("Multiple files for %s"%key)
                    data[key] = contents[1:]
                    break
            else:
                raise ValueError("Unrecognized file %s (did the header row change?)"%filename)
    missing = [key for (key,val) in data.items() if val is None]
    if missing:
        raise ValueError("Missing data for %s"%(', '.join(missing)))
    return data

def render(page_name, **kwds):
    template = JINJA_ENV.get_template(page_name + u'.html')
    return template.render(**kwds)

def generate_index(data):
    with open(opj(ROOT,'generated','index.html'),'w') as F:
        F.write(render(u'index', page_title=u'').encode('utf-8'))

def generate_image_sections(data):
    sections_dict = defaultdict(list)
    for category, page, thumb, caption in data['sections']:
        sections_dict[category].append((page, thumb, caption))
    for category, images in sections_dict.items():
        if category.startswith('painting'):
            section = u'painting'
        else:
            section = category
        with open(opj(ROOT,'generated',category + '.html'),'w') as F:
            F.write(render(u'section_view',images=images, section=section, category=category, page_title=section.capitalize()).encode('utf-8'))

def process_event(tsv_line):
    header = CONFIG.get('TSV', 'events').split(';')
    def add_link(text, url):
        if url and not '</a>' in text:
            return u'<a href="%s">%s</a>'%(url, text)
        else:
            return text
    link_subs = {}
    for n in range(1,6):
        text = tsv_line[header.index('Link(%s) text'%n)]
        url = tsv_line[header.index('Link(%s) url'%n)]
        if text and url:
            link_subs[text] = add_link(text, url)
    def get(key, default=''):
        # if there is one instance of key, returns the corresponding value in tsv.
        # otherwise, returns a list of values
        # default is only used when one instance exists, and when the value would otherwise be empty
        values = []
        i = -1
        while True:
            try:
                i = header.index(key,i+1)
            except ValueError:
                break
            value = tsv_line[i]
            if 'url' not in key and 'Filename' not in key and 'link' not in key:
                for src, target in link_subs.items():
                    value = value.replace(src, target)
            values.append(value)
        if len(values) == 0:
            raise RuntimeError
        if len(values) == 1:
            value = values[0]
            return value if value else default
        else:
            return values
    def to_dt(date):
        month, day, year = date.split(u'/')
        return datetime.date(int(year), int(month), int(day))

    def display_date(date, day_of_week=True, show_year=True):
        if not date:
            return u''
        date = to_dt(date)
        fmt = u'{dt:%B} {dt.day}'
        if day_of_week:
            fmt = u'{dt:%A}, ' + fmt
        if show_year:
            fmt += u', {dt.year}'
        return fmt.format(dt=date)
    def display_date_range(start, end, show_year=True):
        if not end:
            return display_date(start)
        if not start:
            return u'Until ' + display_date(end)
        sm, sd, sy = start.split(u'/')
        em, ed, ey = end.split(u'/')
        # Note unicode en-dashes
        if ey != sy:
            return u'{0} – {1}'.format(display_date(start, day_of_week=False, show_year=True),
                                     display_date(end, day_of_week=False, show_year=True))
        if em == sm and ed == sd:
            return display_date(start, show_year=show_year)
        start = to_dt(start)
        end = to_dt(end)
        if em != sm:
            fmt = u'{start:%B} {start.day} – {end:%B} {end.day}'
        else:
            fmt = u'{start:%B} {start.day} – {end.day}'
        if show_year:
            fmt += u', {end.year}'
        return fmt.format(start=start, end=end)
    def display_time(time):
        time = time.replace(u':00',u'').replace(u' PM',u'pm').replace(u' AM',u'am')
        if time == '12am':
            return u'midnight'
        if time == '12pm':
            return u'noon'
        return time
    def display_time_range(start, end):
        if not end:
            return display_time(start)
        if not start:
            return u'Until ' + display_time(end)
        start = display_time(start)
        end = display_time(end)
        if start[-2:] == end[-2:]: # both am or both pm
            start = start[:-2]
        return u'{0} – {1}'.format(start, end)
    def display_datetime(date, start, end, day_of_week=True, show_year=False):
        return u'{0}, {1}'.format(display_date(date, day_of_week=day_of_week, show_year=show_year),
                                 display_time_range(start, end))
    subevents = zip(get('Title'), get('Link url'), get('Date'), get('Start time'), get('End time'), get('Description'))
    subevents = [{'title':add_link(title, url), 'time':display_datetime(date, start, end), 'desc':desc}
                 for (title, url, date, start, end, desc) in subevents if title]
    images = get('Filename(s), separated by semicolons')
    if images:
        images = [image_file.strip() for image_file in images.split(';')]
    else:
        images = []
    images_on_drive = get('Image(s)')
    if images_on_drive:
        images_on_drive = images_on_drive.split(',')
    else:
        images_on_drive = []
    if len(images) < len(images_on_drive):
        raise ValueError("You must provide a filename for every image")
    elif len(images) > len(images_on_drive):
        raise ValueError("More image filenames than images")
    title = get('Event title')
    img_title = get('Image title')
    if img_title:
        img_title = [one_title.strip() for one_title in img_title.split(';')]
        if len(img_title) > 1 and len(img_title) != len(images):
            raise ValueError("The number of image titles must be the same as the number of images")
    date = display_date_range(get('Event begin date'), get('Event end date'))
    eid = hex((389*hash(title) + 5077*hash(date))%(2**64))[2:]
    return {
        'id':eid,
        'template':int(get('Template (default 1)', 1)),
        'title':title,
        'headline':get('Event headline'),
        'date':date,
        'img_link':get('Image link'),
        'img_names':images,
        'img_title':img_title,
        'img_medium':get('Image medium'),
        'img_dims':get('Image size'),
        'img_desc':get('Image description'),
        'top_notes':get('Top notes'),
        'subevents':subevents,
        'artists':get('Participating artists'),
        'curators':get('Curator(s)'),
        'jurors':get('Juror(s)'),
        'bottom_notes':get('Bottom notes'),
        'video_link':get('Video url'),
        'video_desc':get('Video description'),
        'address_title':get('Location'),
        'address':get('Address'),
    }

def generate_about_section(data):
    about_dict = defaultdict(dict)
    about_dict['statement'] = {}
    about_dict['contact'] = {'facebook':CONFIG.get('LINKS','FACEBOOK'),
                             'instagram':CONFIG.get('LINKS','INSTAGRAM'),
                             'contact_id':CONFIG.get('LINKS','CONTACT_ID')}
    about_dict['events'] = {'events':[process_event(tsv_line) for tsv_line in reversed(data['events'])]}
    about_dict['press'] = {'articles':data['press']}
    resume = defaultdict(list)
    categories = []
    for category, years, line in data['resume']:
        if category not in categories:
            categories.append(category)
        resume[category].append((years, line))
    about_dict['resume'] = {'items':resume, 'categories':categories}
    for subsection, kwds in about_dict.items():
        name = 'about' if subsection=='statement' else subsection
        kwds['section'] = 'about'
        kwds['page_title'] = 'About'
        kwds['subsection'] = subsection
        with open(opj(ROOT,'generated',name+'.html'),'w') as F:
            F.write(render(subsection,**kwds).encode('utf-8'))

def generate_image_pages(data):
    image_list = []
    thumbnails = defaultdict(list)
    for url, section, series, thumb, images, title, medium, dimensions, popup, pwidth, pheight in data['images']:
        if popup:
            title = '<a href="{0}" target="popup" onclick="window.open(\'{0}\',\'popup\',\'width={2},height={3},menubar=no,toolbar=no\'); return false;">{1}</a>'.format(popup,title,pwidth,pheight)
        image_list.append((url, section, series, [image.strip() for image in images.split(';')], [title, medium, dimensions]))
        thumbnails[series].append((thumb, url))
    for url, section, series, images, caption in image_list:
        with open(opj(ROOT,'generated',url),'w') as F:
            thumbs = thumbnails[series]
            F.write(render('image_view',images=images, thumbs=thumbs, caption=caption, section=section, page_title=series).encode('utf-8'))

def generate_poem_pages(data):
    poems = defaultdict(list)
    for url, title, author, line in data['poems']:
        poems[(url, title, author)].append(line)
    for (url, title, author), lines in poems.items():
        with open(opj(ROOT,'generated',url),'w') as F:
            F.write(render('poem', poem_title=title, poem_author=author, lines=lines, page_title=title).encode('utf-8'))

def generate_website():
    data = load_from_sheets()
    generate_index(data)
    generate_image_sections(data)
    generate_about_section(data)
    generate_image_pages(data)
    generate_poem_pages(data)
