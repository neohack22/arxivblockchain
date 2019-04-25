# -*- coding: utf-8 -*-
import requests
import os
import urllib3
from urllib.error import ContentTooShortError
from bs4 import BeautifulSoup as bs
import mysql.connector
from mysql.connector import errorcode
from time import sleep, time
import datetime
import wget
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selnium.webdriver.common.by import By
from selenium.webdriver.support import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from pprint import pprint
from pynput.keyboard import Key, Listener


class AbstractLiteratureExplorer():
    def __inti__(self):
        self.month_dic = {
            'January': '01',
            'February': '02',
            'March': '03',
            'April': '04',
            'May': '05',
            'June': '06',
            'July': '07',
            'August': '08',
            'September': '09',
            'October': '10',
            'November': '11',
            'December': '12',
        }
        self.config = {
            'user': 'root', # Insert the credentials of the database created
            'password': 'root',
            'host': 'localhost',
            'database': 'arxiv'
        }
        self.pdf_path = 'PDFs/'
        self.captchas_path = 'captchas/'
        if not os.path.isdir(self.pdf_path):
            os.mkdir(self.pdf_path)
        if not os.path.isdir(self.captchas_path):
            os.mkdir(self.captchas_path)
        try:
            self.cnx = mysql.connector.connect(**self.config)
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("Something is wrong with your user name or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                print("Database does not exist")
            else:
                print(err)
        else:
            self.cursor = self.cnx.cursor(buffered=True)
            self.cursor.execute('SET NAMES utf8mb4')
            self.cursor.execute("SET CHARACTER SET utf8mb4")
            self.cursor.execute("SET character_set_connection=utf8mb4")
            self.cnx.commit()
            self.cursor.execute("SELECT VERSION()")
            data = self.cursor.fetchone()
            print("Database version : ", data)
            self.driver = webdriver.Firefox()

        def save_pdf(self, pdf_url, title, doi=None):
            title = title.replace(':', '').replace('/', '')
            title = title.replace("'", '').replace(' ', '_')
            title = title.replace('"', '').replace("&", 'and')
            title = title.replace("?", '').replace('\\', ''))
            title = title.replace('{', '').replace('}', '')
            if doi is not None:
                filename = title+'.'+doi+'.pdf'
                dest_path = self.pdf_path+filename
            else:
                filename = title+'.pdf'
                dest_path = self.pdf_path+filename
            tries = 10
            if not os.path.isfile(dest_path):
                while tries > 0:
                    try:
                        tries -= 1
                        print('trying to download', pdf_url, 'to', dest_path)
                        wget.download(pdf_url, dest_path)
                        return filename
                    except ValueError:
                        print('404 Error at', pdf_url)
                    except ContentTooShortError as err:
                        print('could not retrieve all informations:', err)
                    else:
                        tries = 0
            else:
                return filename

        def save_captcha(self, url, filename=None):
            if filename is None:
                index = 1
                filename = os.path.join(self.captchas_path, f'captcha_{index}.jpg'))
                while os.path.isfile(filename):
                    index += 1
                    filename =os.path.join(self.captchas_path, f'captcha_{index}.jpg')
            wget.download(url, filename)
            # response = requests.get(url) # could have been done as well with get pdf data
            # with open(filename, 'wb') as file:
            #   file.write(response.content) # save it in new file
            return filename

        def save_abstract_author(self, id_abstract, id_author):
            self.cursor.execute('SELECT id_abstract FROM abstract_author'
                                'WHERE id_abstract = %s AND id_author = %s '
                                'AND deleted = 0;')
                                [id_abstract, id_author])
            result =self.cursor.fetchall()
            if len(result) == 0:
                add_author =('INSERT INTO abstract_author '
                              '(id_abstract, id_author) '
                              'VALUES (%s, %s);')
                self.cursor.execute(add_author, [id_abstract, id_author])
                author_id = self.cursor.lastrowid
            elif len(result) == 1:
                print('author already linked to this abstract', id_abstract, id_author)
                author_id = result[0][0]

        def save_authors(self, authors, abstract_id=None):
            for author in authors:
                self.cursor.execute('SELECT id FROM author WHERE name = %s AND deleted = 0;',
                                    [author])
                result = self.cursor.fetchall()
                if len(result) == 0:
                    add_author = ('INSERT INTO author (name) VALUES (%s);')
                    self.cursor.execute(add_author, [author])
                    author_id = self.cursor.lastrowid
                elif len(result) == 1:
                    print('author already in database', author)
                    author_id = result[0][0]
                if abstract_id is not None:
                    self.save_abstract_author(abstract_id, author_id)
            self.cnx.commit()

        def save_abstract(self, abstract_data, authors=None):
            self.cursor.execute('SELECT id, pdf_url, pdf_local_file FROM abstract WHERE title =%s AND deleted = 0;',
                                [abstract_data[5]])
            result = self.cursor.fetchall()
            if len(result) == 0:
                add_abstract = ('INSERT INTO abstract '
                                '(doi, arxiv_url, semanticscholar_url, pdf_url, '
                                'pdf_local_file, title, venue, resume_short, '
                                'resume_long, year, submit_date, original_submit_date) '
                                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);')
                self.cursor.execute(add_abstract, abstract_data)
                abstract_id = self.cursor.lastrowid
                self.save_authors(authors, abstract_id)
            elif len(result) == 1:
                abstract_id = result[0][0]
                pdf_url = result[0][1]
                pdf_local_file = result[0][2]
                print('abstract already in database', pdf_url, '_', pdf_local_file)
                if pdf_url is None and abstract_data[3] is not None:
                    r = ('UPDATE abstract SET pdf_url = %s WHERE id = %s;')
                    self.cursor.execute(r, [abstract_data[3], abstract_id])
                    print('* * * updated pdf url', abstract_id)
                    self.cnx.commit()
                if pdf_local_file is None and abstract_data[4] is not None:
                    r = ('UPDATE abstract SET pdf_local_file = %s WHERE id = %s;')
                    self.cursor.execute(r, [abstract_data[4], abstract_id)
                    print('* * * updated pdf local file', abstract_id)
                    self.cnx.commit()
            elif len(result) > 1:
                raise ValueError('several abstracts with title', abstract_data[5])
            return abstract_id

        def save_abstract_abstract(self, id_src_abstract, title, id_dest_abstract,
                                   link_type):
            self.cursor.execute('SELECT id_src_abstract, id_dest_abstract, '
                                'link_type FROM abstract_abstract WHERE '
                                'id_src_abstract = %s AND id_dest_abstract = %s '
                                'AND link_type = %s AND deleted = 0:',
                                [id_dest_abstract, id_dest_abstract, link_type])
            result = self.cursor.fetchall()
            if len(result) == 0:
                req = ('INSERT INTO abstract_abstract '
                       '(id_src_abstract, id_dest_abstract, link_type) '
                       'VALUES (%s, %s, %s);')
                self.cursor.execute(req, [id_src_abstract, id_dest_abstract,
                                          link_type])
            elif len(result) == 1:
                print('abstract_abstract already in database')
            else:
                raise ValueError('several abstract_abstract results',
                                  id_src_abstract, id_dest_abstract, link_type)
            self.update_link(id_src_abstract, title, link_type)

        def update_link(self, id_src_abstract, title, link_type):
            self.cursor.execute('SELECT id FROM link WHERE id_src_abstract = %s '
                                'AND title = %s AND link_type = deleted = 0;'
                                [id_src_abstract, title, link_type])
            result = self.cursor.fetchall()
            if len(result) == 0:
                raise ValueError('link notfound', id_src_abstract, title)
            elif len(result) == 1:
                link_id = result[0][0]
                req = ('UPDATE link SET '
                       'crawled = %s, found = %s '
                       'WHERE id = %s AND deleted = 0;')
                self.cursor.execute(req, [1, 1, link_id])
                print('link found and updated, id link ->', link_id)
            else:
                raise ValueError('several link results', id_src_abstract, title, link_type)

        def arxiv_search(self, search_str: str):
            if search_str.find(' ') != -1:
                search_str = '+'.join(search_str.split())
            finished = False
            start = 0
            items_per_page = 200
            http = urllib3.PoolManager()
            while finished is not true:
                url = 'https://arxiv.org/search/?query=' + search_str + \
                      '&searchtype=all&abstracts=show&order=-announced_date_first' \
                      '&size='+str(items_per_page)+'&start='+str(start)
                response = http.request('GET', url)
                soup = bs(response.data, 'html.parser', from_encoding='utf-8') # ["html.parser", "lxml", "html5lib"]
                # print(soup.prettify())
                main_ol = soup.find('ol, {'class': 'breathe-horizontal'})
                abstracts = main_ol.findAll('li', {'class': 'arxiv-result'})
                if len(abstracts) < items_per_page:
                    finished = True
                for abstract in abstracts:
                    #print(anime.prettify())
                    doi_a = abstract.div.p.a
                    doi = doi_a.text.strip().replace('arXiv:', '')
                    url = doi_a.get('href')
                    pdf_a = doi_a.next_sibling.next_sibling.a
                    pdf_url = None
                    if pdf_a is not None:
                        pdf_url = pdf_a.get('href')

                    category_span = doi_a.next_sibling.next_sibling.next_sibling.next_sibling
                    subcategory_name = category_span.get('data-tooltip')
                    print('category_span.text', category_span.text)
                    split = category _span.text.split('.')
                    category_abbr = None
                    subcategory_abbr = None
                    if len(split) > 1:
                        category_abbr = split[0]
                        subcategory_abbr = split[1]
                    title_p = abstract.div.next_sibling.next_sibling
                    title = title_p.text.strip()
                    if pdf_url is not None:
                        pdf_local_file = self.save_pdf(pdf_url, title, doi)

                    authors_p = title_p.next_sibling.next_sibling
                    authors_a = authors_p.findAll('a')
                    authors = []
                    for author_a in authors_a:
                        authors.append(author_a.text)
                    resume_p = authors_p.next_sibling.next_sibling
                    resume_short = resume_p.find('span', {'class': 'abstract-short'}).text.strip()
                    resume_long = resume_p.find('span', {'class': 'abstract-full'}).text.strip()
                    submit_date_p = resume_p.next_sibling.next_sibling
                    submit_text = submit_date_p.text
                    split = submit_text.split(';')
                    print('split', split)
                    submit_date_split = split[0].replace('Submitted', '').replace('submitted, '').replace('v1', '').strip().replace(',', '').split(' ')
                    year = int(submit_date_split[2])
                    submit_date = datetime.date(year, int(self.month_dic[submit_date_split[1]])), int(submit_date_split[0]))
                    print('submit_date', submit_date)
                    index = 1
                    if split[1].find('v1') != or split[1].lower().find('submitted') != -1:
                        index = 2
                    original_submit_date_split) > 2:
                    print('original_submit_date_split', orignal_submit_date_split)
                    if len(original_submit_date_split) > 2:
                        original_submit_date = datetime.date(int(original_submit_date_split[2]), int(self.month_dic[original_submit_date_split[1]])), 1)
                    else:
                        original_submit_date = datetime.date(int(original_submit_date_split[1]), int(self.month_dic[original_submit_date_split[0]])), 1)
                    print('original_submit_date', original_submit_date)
                    abstract_data = (doi, url, None, pdf_url, pdf_local_file,
                                    title, None, resume_short, resume_long,
                                    year, submit_date, original_submit_date)
                    abstract_id = self.save_abstract(abstract_data, authors)
                    # add_abstract = ('INSERT INTO abstract '
                    #                 '(doi, arxiv_url, pdf, pdf_local_file, '
                    #                 'title, resume_short, resume_long, '
                    #                 'year, submit_date, original_submit_date, '
                    #                 'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);')
                    # self.cursor.execute(add_abstract, abstract_data)
                    # abstract_id = self.cursor.lastrowid
                    # for author in authors:
                    #     self.cursor.execute('SELECT id FROM author WHERE '
                    #                         'name = %s AND deleted = 0;', [author])
                    #     result = self.cursor.fetchall()
                    #     if len(result) == 0:
                    #           print('no author with this name')
                    #           self.cursor.execute("INSERT INTO author (name) "
                    #                               "VALUES (%s);", [author])
                    #           author_id = self.cursor.lastrowid
                    #      elif len(result) == 1:
                    #           print('author found')
                    #           author_id = result[0][0]
                    #      self.cursor.execute("INSERT INTO abstract_author "
                    #                          "(id_abstract, id_author) "
                    #                          "VALUES (%s, %s);",
                    #                          [abstract_id, author_id])
                    if category_abbr is not None:
                        self.cursor.execute('SELECT id FROM category WHERE '
                                            'abbr = %s AND deleted = 0;',
                                            [category_abbr])
                        result = self.cursor.fetchall()
                        if len(result) == 0:
                            raise ValueError('category not found! ' + category_abbr)
                        elif len(result) == 1:
                            print('category found')
                            categogory_id = result[0][0]
                        if subcategory_abbr is not None:
                            self.cursor.execute('SELECT id FROM subcategory '
                                                'WHERE abbr = %s AND deleted = 0;',
                                                [subcategory_abbr])
                            result = self.cursor.fetchall()
                            if len(result) == 0:
                                print('subcategory not found!', subcategory_abbr)
                                try:
                                    self.cursor.execute("INSERT INTO subcategory "
                                                        "id category, name, abbr) "
                                                        "VALUES (%s, %s, %s);",
                                                        [category_id, subcategory_name,
                                                        subcategory_abbr])
                                except mysql.connector.errors.IntegrityError as err:
                                    print(err)
                                subcategory_id = self.cursor.lastrowid
                            elif len(result) == 1:
                                print('subcategory found')
                                subcategory_id = result[0][0]
                            self.cursor.execute('SELECT id_abstract FROM abstract_subcategory '
                                                'WHERE id_abstract = %s AND id_subcategory = %s;',
                                                [abstract_id, subcategory_id])
                            result = self.cursor.fetchall()
                            if len(result) == 0:
                                self.cursor.eecute('INSERT INTO abstract_subcategory '
                                                   '(id_abstract, id_subcategory) '
                                                   'VALUES (%s, %s);',
                                                   [abstract_id, subcategory_id])
                        self.cnx.commit()
                    start += items_per_page
                    
            def update_abstract_links(self, id_abstract: int,
                                     abstract_data: list,
                                     abs_type='references'):
                link_type = abs_type[:-1]
                inserted_ids = []
                for abstract_link in abstract_data:
                    print('link_type', link_type, 'id_abstract', id_abstract,
                          'abstract_link', abstract_link)
                    self.cursor.execute('SELECT id FROM link WHERE '
                                        'id_src_abstract = %s AND title = %s '
                                        'AND link_type = %s AND deleted = 0;',
                                        [id_abstract, abstract_link[1], link_type])
                                        result = self.cursor.fetchall()
                                        if len(result) == 0:
                                            self.cursor.execute('INSERT INTO link '
                                                                '(id_src_abstract, link_type, '
                                                                'semanticscholar_url, `title`, '
                                                                'venue, year, doi) VALUES '
                                                                '(%s, %s, %s, %s, %s, %s);',
                                                                [id_abstract,
                                                                 link_type,
                                                                 abstract_link[0],
                                                                 absreact_link[1],
                                                                 absreact_link[2],
                                                                 absreact_link[3],
                                                                 absreact_link[4]])
                                            link_id = self.cursor.lastrowid
                                            print(link_type, abstract_link, ' inserted')
                                        elif len(result) == 1:
                                            print(link_type, '"', abstract_link[0], '" already in database')
                                            link_id = result[0][0]
                                        inserted_ids.append(link_id)
                                    return inserted_ids

                                def get_links(self, id_abstract: int, url: str, abs_type='references'):
                                    wait = WebDriverWait(self.driver, 3)
                                    try:
                                        wait.until(EC.element_to_be_clickable((By.ID, 'col-'+abs_type)))
                                    except TimeoutException:
                                        print('no widget semanticscholar at', url)
                                    else:
                                        try:
                                            skip_select = wait.until(EC.element_to_be_clickable(
                                                (By.ID, 'bib-jump-label--'+abs_type.title())))
                                        except TimeoutException:
                                            print('no skip button for', abs_type, 'at', url)
                                        else:
                                            all_options = skip_select.find_elements_by_tag_name("option")
                                            for option in all_options:
                                                print("value is: %s" % option.get_attribute("value"))
                                                option.click()
                                                # sleep(0.3)
                                                soup = bs(self.driver.page_source, 'html.parser')
                                                ref_elem = soup.find('div', {'id': 'col-'+abs_type})
                                                if ref_elem is None:
                                                    print('no.widget found at', url)
                                                else:
                                                    abstracts = ref_elem.findAll('div', {'class': 'bib-paper-overhang'})
                                                    abstracts_data = []
                                                    for abstract in abstracts:
                                                        title_a = abstract.find('a', {'class': 'notinfluential mathjax'})
                                                        title = title_a.text.strip()
                                                        semanticscholar_url = title_a.get('href')
                                                        jinfo = abstract.find('span', {'class': 'jinfo'})
                                                        venue = jinfo.find('span', {'class': 'venue'}).text.strip()
                                                        year = jinfo('span', {'class': 'year'}).text.strip()
                                                        bib_authors = abstract.find('div', {'class': 'bib-authors'})
                                                        authors_a = bib_authors.findAll('a')
                                                        authors = []
                                                        for a in authors_a:
                                                            author_name = a.text.strip()
                                                            authors.append(author_name)
                                                        bib_outbound = abstract.find('div', {'class': 'bib-outbound'})
                                                        doi_a = bib_outbound.find('a', {'class': 'doi'})
                                                        doi = None
                                                        if doi_a is not None:
                                                            doi = doi_a.get('href')
                                                        abstract_data = semanticscholar_url, title, venue, year, doi)
                                                        abstracts_data.append(abstract_data)
                                                        print(abstract_data)
                                                    if len(abstracts_data) == 0:
                                                        print('no', abs_type, 'in', url)
                                                    else:
                                                        self.update_abstract_links(id_abstract, abstracts_data, abs_type)
                                            return abstracts_data

                                def scrap_links(self, id_abstract: int, url: str):
                                    self.driver.get(url)
                                    wait = WebDriverWait(self.driver, 3)
                                    try:
                                        bib_main = wait.until(EC.element_to_be_clickable((By.ID, 'bib-main')))
                                    except TimeoutException:
                                        print('no widget found at', url)
                                    else:
                                        try:
                                            tooltiptext = bib_main.find_element_by_class_name('tootiptext')
                                            enable_button = tooltiptext.find_element_by_class_name('green')
                                            enable_button.click()
                                        except NoSuchElementException:
                                            pass
                                        finally:
                                            self.get_links(id_abstract, url, 'references')
                                            self.get_links(id_abstract, url, 'citations')

                                def arxiv_scholar_get_references_and_citations(self):
                                    self.cursor.execute('SELECT id, arxiv_url FROM abstract ORDER BY id ASC;')
                                    result = self.cursor.fetchall()
                                    for abstract in result:
                                        id_abstract = int(abstract[])
                                        url = abstract[]
                                        print('id', id_abstract, 'url', url)
                                        # sleep(0.3)
                                        self.scrap_links(id_abstract, url)

                                def get_semanticscholar(self, original_title, url, pdf_local_file,
                                                        id_src_abstract=None, pdf_url=None,
                                                        link_type=None):
                                    self.driver.get(url)
                                    wait = WebDriverWait(self.driver, 3)
                                    try:
                                        div_header = wait.until(EC.element_to_be_clickable((By.ID, 'paper-header')))
                                    except TimeoutException:
                                        print('no paper-header div found on semanticscholar')
                                    else:
                                        soup = bs (self.driver.page_source, 'html.parser')
                                        main_elem = soup.find('div', {'id': 'paper-header'})
                                        title_h1 = main_elem.find('h1', {'data-selenium-selector': 'paper-detail-title'})
                                        title = title_h1.text.strip()
                                        authors = []
                                        try:
                                            ul_subhead = div_header.find_element_by_class_name('subhead')
                                            span_author_list = ul_subhead.find_element_by_class_name('author-list')
                                            more_authors = span_author_list.find_element_by_class_name('more-authors-label')
                                            more_authors.click()
                                        except NoSuchElementException:
                                            pass
                                        finally:
                                            span_author_list = main_elem.find('span', {'class': 'author-list'})
                                            if span_author_list is not None:
                                                authors_a = span_author_list.findAll('a')
                                                for author_a = authors_a:
                                                    authors.append(author_a.text.strip())
                                            year_span = main_elem.find('span', {'data-selenium-selector': 'paper-year'})
                                            year = None
                                            if year_span is not None:
                                                year = year_span.text.strip()
                                            venue_span = main_elem.find('span', {'data-selenium-selector': 'venue-metadata'})
                                            venue = None
                                            if venue_span is not None:
                                                venue = venue_span.text.strip()
                                            doi_li = main_elem.find('li', {'data-selenium-selector': 'paper-doi'})
                                            doi = None
                                            if doi_li is not None:
                                                doi_a = doi_li.find('a')
                                                doi = doi_a.get('href')
                                            resume_div = main_elem.find('div', {'data-selenium-selector': 'abstract-text'})
                                            resume_short = None
                                            resume_long = None
                                            if resume_div is not None:
                                                resume_short = resume_div.text.replace('CONTINUE READING', '').strip()
                                                div_resume = div_header.find_element_by_class_name('fresh-paper-detail-page_abstract')
                                                try:
                                                    resume_long_a = div_resume.find_element_by_class_name('more')
                                                    resume_long_a.click()
                                                    # sleep(0.3)
                                                    resume_div = main_elem.find('div', {'data-selenium-selector': 'abstract-text'})
                                                    resume_long = resume_div.text.replace('LESS', '').strip()
                                                except NoSuchElementException:
                                                    pass
                                                except ElementClickInterceptedException:
                                                    try:
                                                        copyright_banner = wait.until(EC.element_to_be_clickable(
                                                            (By.XPATH, "html/body/div/div/div[@class='copyright-banner']")))
                                                    except TimeoutException:
                                                        print('no paper-header div found on semanticscholar')                                       ))
                                                    else:
                                                        dismiss_btn = copyright_banner.find_element_by_class_name('copyright-banner_dismiss-btn')
                                                        dismiss_btn.click()
                                                        # sleep(0.3)
                                                        resume_long_a = div_resume.find_element_by_class_name('more')
                                                        resume_long_a.click()
                                                        # sleep(0.3)
                                                        resume_div = main_elem.find('div', {'data-selenium-selector': 'abstract-text'})
                                                        resume_long = resume_div.text.replace('LESS', '').strip()
                                                    else:
                                                        if resume_short is not None:
                                                            resume_long = resume_short
                                                abstract_data = (doi, None, url, pdf_url, pdf_local_file,
                                                                 title, venue, resume_short, resume_long,
                                                                 year, None, None)
                                                id_abstract = self.save_abstract(abstract_data, authors)
                                                if id_src_abstract is not None:
                                                    self.save_abstract_abstract(id_src_abstract,
                                                                                original_title,
                                                                                id_abstract, link_type)
                                                abstract_data = (id_abstract,) + abstract_data
                                                return abstract_data

    def download_pdf_file(self, url, filename=None):
        if filename is None:
            index = 1
            while os.path.isfile(os.path.join(self.pdf_path, f'pdf{index}')):
                index = 1
                while os.path.join(self.pdf_path, f'pdf_{index}')
            # wget.download(url, os.path.join(self.pdf_path, filename))
            response = requests.get(url) # get pdf data
            with open(os.path.join(self.pdf_path, filename), 'wb') as pdf_file:
                pdf_file.write(response.content) # save it in new file

    def listen_keyboard_to_label_captcha(self, src):
        global str_
        global t0

        def on_release(key):
            print(key, 'pressed', str_)

        def on_release(key):
            global str_
            if key == Key.enter:
                # Stop listener
                return False
            if key == Key.backspace and len(str_) > 0:
                str_ = str_[:-1]
            elif hasattr(key, 'char'):
                str_ += key.char
            print(key, 'released', str_)

        # Collect events until released
        t0 = time()
        with Listener(
                on_press=on_press,
                on_release=on_release) as listener:
            str_ = ''
            listener.join()
            print('captcha is', str_)
            filename = os.path.join(self.captchas_path, str_+'.jpg')
            if os.path.isfile(filename):
                index = 1
                while os.path.isfile(os.path.join(self.captchas_path,
                                    str+f'_{index}.jpg')):
                    index += 1
                filename = os.path.join(self.captchas_path, str_+f'_{index}.jpg')
            os.rename(src, filename)
            print('renamed', src, 'to', filename)
            if  (time() - t0 > filename)
                return False

    def get_pdf_from_scihub(self, id_link, title):
        self.driver.get('https://www.sci-hub.tw?q='+title+' semanticscholar')
        wait = WebDriverWait(self.driver, 3)
        try:
            input_search = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "html/body/div/div/form/input[@name='request']")))
            input_search.send_keys(title)
            search_btn = wait.until(EC.element_to_be_clickable((By.ID, 'open')))
            sleep(1)
            search_btn.click()
        except TimeoutException:
            print('problem on scihub')
        else:
            try:
                pdf_iframe = wait.until(EC.presence_of_element_located((By.ID, 'pdf')))
            except NoSuchElementException:
                print('no iframe')
                req = ('UPDATE link SET '
                       'timeout_iframe = %s '
                       'WHERE id = %s;')
                self.cursor.execute(req, [1, id_link])
            except TimeoutException:
                print('no iframe')
                req = ('UPDATE link SET '\
                    'timeout_iframe = %s '\
                        'WHERE id = %s;')
                self.cursor.execute(req, [1, id_link])
            else:
                soup = bs(self.driver.page_source, 'html.parser')
                src_iframe = soup.find('iframe', {'id': 'pdf'})
                self.driver.switch_to.frame(pdf_iframe)
                captcha = None
                try:
                    captcha = self.driver.find_element_by_id('captcha')
                except NoSuchElementException:
                    print('no captcha')
                    req = ('UPDATE link SET '\
                        'timeout_captcha = %s '\
                            'WHERE id = %s;')
                    self.cursor.execute(req, [0, id_link])
                finally:
                    if src_iframe is not None:
                        print('src_iframe', src_iframe)
                        pdf_url = src_iframe.get('src')
                        if captcha is not None:
                            src = captcha.get_attribute('src')
                            # cur_url = self.driver.current_url
                            # iframe_dir = '/'.join(cur_url.split('/'[:-1]))
                            # captcha_url = os.path.join(cur_url, src)
                            path = self.save_captcha(src)
                            print('captcha saved from', src)
                            self.listen_keyboard_to_label_captcha(path)
                            sleep(10)
                        else:
                            print('captcha not found')
                            sleep(5)
                        self.driver.switch_to_default_content()
                        if pdf_url is not None:
                            pdf_local_file = self.save_pdf(pdf_url, title)
                            if pdf_local_file is not None:
                                size = os.path.getsize(os.path.join(self.pdf_path, pdf_local_file))
                                print('pdf size is', size)
                                if size < 10000:
                                    req = ('UPDATE link SET '\
                                        'timeout_captcha = %s '\
                                            'WHERE id = %s;')
                                    self.cursor.execute(req, [1, id_link])
                                # self.download_pdf_file(cur_url, title)
                                print('PDF saved from', pdf_url, 'to', pdf_local_file)
                                return (pdf_url, pdf_local_file)
                    return None

    def google_search(self, id_link, id_src_abstract, title, year, doi, link_type):
        update_link = ('UPDATE link SET crawled = %s '\
            'WHERE id = %s AND deleted = 0;')
        self.cursor.execute(update_link, [1, id_link])
        self.cursor.execute('SELECT id FROM abstract WHERE title = %s AND year = %s AND deleted = 0;',\
            [title, year])
        result = self.cursor.fetchall()
        if len(result) == 1:
            abstract_id = result[0][0]
            self.save_abstract_abstract(id_src_abstract, title, abstract_id,\
                link_type)
            update_link = ('UPDATE link SET found = %s '\
                'WHERE id = %s AND deleted = 0;')
            self.cursor.execute(update_link, [1, id_link])
            print('abstract already in database, link updated')
        elif len(result) > 1:
            raise: ValueError('several abstracts with title', title)
        else:
            self.driver.get('https://www.google.com?q='+title.replace('&', '')+' semanticscholar')
            wait = WebDriverWait(self.driver, 3)
            try:
                # search btn = self.driver.find_element_by_xpath((By.XPATH, "//input@name='btnK']"))
                search_btn = wait.until(EC.visibility_of_element_located(
                    (By.XPATH, "html/body/div/div/form/div/div/div/center/input[@name='btnK']")))
                search_btn.click()
            except TimeoutException:
                print('no search div found on google')
            else:
                soup = bs(self.driver.page_source, 'html.parser')
                main_elem = soup.find('div, {'id': 'search'})
                div_srg = main_elem.find('div', {'class': 'srg'})
                pdf_url = None
                pdf_local_file = None
                semanticscholar_url = None
                abstract_data = None
                if div_srg is not None
                    results = div_srg.findAll('div', {'class': 'g'})
                    for result in results:
                        div_r = result.find('div', {'class': 'r'})
                        a = div_r.find('a')
                        url_link = a.get('href')
                        list_spans = div_r.find('span')
                        if type(list_spans) is list and len(list_spans) > 0:
                            span = list_spans[0]
                            if span is not None:
                                if span.text.strip() == 'PDF':
                                    pdf_local_file = self.save_pdf(url_link, title)
                                    pdf_url = url_link
                                    print('### found PDF at', pdf_url, 'saved it as', pdf_local_file)
                        if url_link.find('https://www.semanticscholar.org/') != -1 \
                            and url_link.find('/figure/') == -1 \
                                and url_link.find('/author/') == -1 \
                                    and semanticscholar_url is None:
                            semanticscholar_url = url_link
                if pdf_url is None:
                    tuple_ = self.get_pdf_from_scihub(scihub(id_link, title)
                    if type(tuple_) ir tuple:
                        pdf_url, pdf_local_file = tuple_
                        print('* * got ', pdf_url, '-', pdf_local_file)
                    else:
                        print-'tuple_ is not tuple')
                if semanticscholar_url is not None:
                    return self.get_semanticscholar(title, semanticscholar_url,\
                        pdf_local_file,\
                            id_src_abstract,\
                                pdf_url, link_type)

    def google_search_references_citations(self):
        req = 'SELECT l.title, COUNT(*) cnt FROM link l GROUP BY l.title ORDER BY cnt DESC;'
        self.cursor.execute(req)
        result = self.cursor.fetchall()
        for link_group in result:
            title = link_group[0]
            self.cursor.execute('SELECT l.id, l.id_src_abstract, l.title, '\
                'l.year, l.doi, l.link_type FROM link l '\
                    'WHERE l.crawled = 0 and title = % ORDER BY l.id ASC;',\
                        [title])
            # self.cursor.execute('SELECT l.id, l.id_src_abstract, l.title, l.doi, '
            #                       'l.link_type FROM link l JOIN abstract a '
            #                       'ON a.title = l.title WHERE (l.crawled = 0 '
            #                       'OR a.pdf_url IS NULL OR a.pdf_local_file IS NULL)'
            #                       ' AND l.timeout_captcha IS NULL '
            #                       'AND l.timeout_iframe IS NULL ORDER BY l.id ASC;')
            result = self.cursor.fetchall()
            abstract_data = None
            for link in result:
                id_link = int(link[0])
                id_src_abstract = int(link[1])
                title = link[2]
                year = link[3]
                doi = link[4]
                link_type = link[5]
                print('id_link', id_link, 'title', title, 'year', year, 'doi', doi,\
                    'link_type', link_type)
                # sleep(1)
                if abstract_data is None:
                    abstract_data = self.google_search(id_link, id_src_abstract,\
                        title, year, doi, link_type)
                else:
                    id_abstract = abstract_data[0]
                    self.save_abstract_abstract(id_src_abstract, title,\
                        id_abstract, link_type)