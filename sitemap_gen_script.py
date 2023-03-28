# TODO завернуть все это в скрипт с парсером из командной строки
from itertools import islice
from pathlib import Path

from lxml import etree


try:
    # Парсим файл выгрузки, получаем ElementTree
    # TODO запрос расположения файла из командной строки - обязательный аргумент
    data_input = etree.parse('articles.xml.gz')
except IOError:  # TODO человеческий вывод ошибок
    print('File does not exist')
except etree.XMLSyntaxError:
    print('File contains invalid elements')
else:
    # Создадим целевую папку
    # TODO запрос расположения папки для сайтмапов из командной строки - обязательный аргумент
    output_dir_path = Path('zip77.ru/')
    output_dir_path.mkdir(exist_ok=True)

    # Создадим корневой элемент и дерево для возможного(!) сайтмап-индекса
    sitemap_index_root_elem = etree.Element('sitemapindex', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    sitemap_index_tree = etree.ElementTree(sitemap_index_root_elem)

    target_parent_elem = data_input.find('shop/offers')  # Находим offers, чтоб скипнуть первый тег url: это же не товар
    # Создадим итератор от 'offers' для дальнейших извлечений содержимого по тегу 'url'
    url_iter = target_parent_elem.iter('url')

    # Объявляем счетчик имен файлов сайтмапа. Идем циклом по всем элементам с тегом 'url' внутри тегов 'offers'
    file_number = 0
    while True:
        # Создаем корневой элемент сайтмапа и дерево с ним
        sitemap_root_element = etree.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        data_output = etree.ElementTree(sitemap_root_element)

        # От итератора по 'url' будем айслайсом откусывать по 50к. Вся эта карусель позволит не грузить в память данные
        # TODO запрос максимального количества ссылок в сайтмапе - необязательный аргумент (50к по дефолту)
        for i_child_elem in islice(url_iter, 50_000):
            if i_child_elem.text:
                # TODO по-хорошему бы чекнуть файл robots.txt, чтобы адрес из i_child_elem.text не был в 'disallow'
                # Добавим к родителю-корню обязательный элемент сайтмапа - 'url'
                sitemap_url_element = etree.SubElement(sitemap_root_element, 'url')
                # Добавим к родителю-url обязательный элемент 'loc' - собственно адрес страницы
                sitemap_loc_element = etree.SubElement(sitemap_url_element, 'loc')
                # Задаем ему атрибут 'text' - это будет содержимое тега 'loc'.
                # Контентом будет 'text' из каждого найденного элемента 'url' товара из файла выгрузки
                sitemap_loc_element.text = i_child_elem.text
                # Добавим к родителю-url необязательный элемент 'priority', установим ему значение '0.3'
                # TODO запрос значения приоритета - необязательный аргумент (0.3 по дефолту)
                sitemap_priority_element = etree.SubElement(sitemap_url_element, 'priority')
                sitemap_priority_element.text = '0.3'

        # Проверяем, не получили ли мы пустой корневой элемент, т.е. не закончился ли url-итератор. Если да, рвем цЫкл
        if not len(sitemap_root_element):
            break

        # Делаем новый путь к файлу с учетом номера, пишем его (вызываем метод 'write' на дереве)
        # TODO запрос префикса имени файла сайтмапа - необязательный аргумент ('sitemap' по дефолту)
        output_file_path = output_dir_path / f'sitemap{file_number}.xml'
        data_output.write(output_file_path, pretty_print=True, encoding='utf-8', xml_declaration=True)
        # TODO реализовать сжатие в gzip выходных файлов - необязательный аргумент ('False' по дефолту)

        # К корневому элементу сайтмап-индекса добавляем тег 'sitemap', а в него - 'loc'
        sitemap_index_sitemap_elem = etree.SubElement(sitemap_index_root_elem, 'sitemap')
        sitemap_index_loc_elem = etree.SubElement(sitemap_index_sitemap_elem, 'loc')
        # К тегу 'loc' добавляем содержимое - собственно путь к файлу сайтмапа
        sitemap_index_loc_elem.text = str(output_file_path)

        file_number += 1  # Инкрементим номер для имени файла сайтмапа

    # По завершении цЫкла смотрим длину корня дерева сайтмап-индекса. Если больше 1, записываем файл сайтмап-индекса
    if len(sitemap_index_root_elem) > 1:
        output_file_path = output_dir_path / 'sitemap-index.xml'
        sitemap_index_tree.write(output_file_path, pretty_print=True, encoding='utf-8', xml_declaration=True)

    # TODO реализовать добавление информации о расположении сайтмапа (или сайтмап-индекса) в robots.txt
