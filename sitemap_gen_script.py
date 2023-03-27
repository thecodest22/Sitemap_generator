from lxml import etree


data_input = etree.parse('articles-test.xml')  # Парсим файл выгрузки, получаем ElementTree
target_parent_elem = data_input.find('shop/offers')  # Находим offers, чтобы скипнуть первый тег url - это же не товар

# Создаем корневой элемент сайтмапа с указанием протокола
sitemap_root_element = etree.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
# Создаем дерево с корневым элементом
data_output = etree.ElementTree(sitemap_root_element)

# Идем циклом по всем элементам с тегом 'url' внутри тегов 'offers'
for i_child_elem in target_parent_elem.iter('url'):  # TODO ограничить количество элементов 'url' в сайтмапе 50 тысячами
    # Добавим к родителю-корню обязательный элемент сайтмапа - 'url'
    sitemap_url_element = etree.SubElement(sitemap_root_element, 'url')
    # Добавим к родителю-url обязательный элемент 'loc' - собственно адрес страницы
    sitemap_loc_element = etree.SubElement(sitemap_url_element, 'loc')
    # Задаем ему атрибут 'text' - это будет содержимое тега 'loc'.
    # Контентом будет 'text' из каждого найденного элемента 'url' товара из файла выгрузки
    sitemap_loc_element.text = i_child_elem.text
    # Добавим к родителю-url необязательный элемент 'priority', установим ему значение '0.3'
    sitemap_priority_element = etree.SubElement(sitemap_url_element, 'priority')
    sitemap_priority_element.text = '0.3'

# На экземпляре ElementTree вызываем метод записи в файл
data_output.write('result-test.xml', pretty_print=True, encoding='utf-8', xml_declaration=True)
# TODO разбить общее количество записей 'url' по сайтмапам (индекс)
# TODO реализовать добавление информации в robots.txt
