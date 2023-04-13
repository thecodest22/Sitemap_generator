from itertools import islice
from pathlib import Path

from lxml import etree


UPLOAD_DATA_FILE = './articles.xml.gz'
FILENAME_PREFIX = 'sitemap'
URL_PRIORITY = '0.3'
TARGET_NODE = '//offer/url'

parsed_xml_tree = etree.parse(UPLOAD_DATA_FILE)

iterator = parsed_xml_tree.iterfind(TARGET_NODE)

sitemap_root = etree.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
sitemap_tree = etree.ElementTree(sitemap_root)

sitemap_file_number = 1
while True:
    for i_node in islice(iterator, 50000):
        sitemap_url = etree.SubElement(sitemap_root, 'url')
        etree.SubElement(sitemap_url, 'loc').text = i_node.text
        etree.SubElement(sitemap_url, 'priority').text = URL_PRIORITY

    if not len(sitemap_root):
        break

    output_sitemap_file = Path() / f'{FILENAME_PREFIX}_{str(sitemap_file_number).zfill(2)}.xml'
    with output_sitemap_file.open('wb') as xml_output:
        sitemap_tree.write(xml_output, pretty_print=True, encoding='utf-8', xml_declaration=True)

    sitemap_root.clear()
    sitemap_file_number += 1
