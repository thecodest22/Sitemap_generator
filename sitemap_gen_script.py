#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from argparse import ArgumentParser
from re import search
from sys import exit
from shutil import rmtree, copyfileobj
from gzip import open as gzip_open
from itertools import islice
from pathlib import Path


try:
    from lxml import etree
except ModuleNotFoundError as e:
    print(e.msg, "Make sure it has been installed to the active environment!", sep='\n')
    exit(1)


def addresses_num_validator(digits: str) -> int:
    digits = int(digits)
    if not 0 < digits <= 50_000:
        raise ValueError
    return digits


def priority_range_validator(priority: str) -> float:
    priority = float(priority)
    if not 0 <= priority <= 1:
        raise ValueError
    return priority


def filename_prefix_validator(prefix: str) -> str:
    if search(r'[#<>$+%!`&*‘|{}?"=/:\\ @[\]]', prefix):  # I'm not sure about this set of symbols!
        raise ValueError
    return prefix


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(description='Creates a sitemap from an uploaded XML-file')
    parser.add_argument('-f', '--file', type=Path, required=True, help='Path to an XML-file (or a gz-archive with it)')
    parser.add_argument('-o', '--output dir', type=Path, default='./zip77.ru',
                        help='Path to the directory where the sitemap will be placed')
    parser.add_argument('-a', '--addresses per file', type=addresses_num_validator, default=50_000,
                        help='Max addresses number for each sitemap file (up to 50k)')
    parser.add_argument('-p', '--priority url', type=priority_range_validator, default=0.3,
                        help='URLs priority (from 0 to 1.0')
    parser.add_argument('-P', '--filename prefix', type=filename_prefix_validator, default='sitemap',
                        help='Prefix to use in output filenames, eg. "prefix.xml", "prefix1.xml"...')
    parser.add_argument('-z', '--zip', action='store_true', help='Add sitemap archive files (.gz)')

    return parser


def handle(options) -> None:
    input_xml_file: Path = options['file']
    output_dir: Path = options['output dir']
    entries_number: int = options['addresses per file']
    urls_priority: float = options['priority url']
    prefix: str = options['filename prefix']
    need_zip: bool = options['zip']

    try:
        parsed_xml_data = etree.parse(input_xml_file)
    except IOError:
        print(f'File "{input_xml_file}" does not exist')
        exit(1)
    except etree.XMLSyntaxError:
        print(f'File "{input_xml_file}" contains invalid elements')
        exit(1)

    if output_dir.exists():
        rmtree(output_dir)
    output_dir.mkdir(parents=True)

    sitemap_index_root = etree.Element('sitemapindex', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    sitemap_index_tree = etree.ElementTree(sitemap_index_root)

    parent_xml_elem = parsed_xml_data.find('shop/offers')
    url_elements_iterator = parent_xml_elem.iter('url')

    sitemap_file_number = 0
    while True:
        sitemap_root = etree.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        data_output = etree.ElementTree(sitemap_root)
        for i_url in islice(url_elements_iterator, entries_number):
            if i_url.text:
                sitemap_url_element = etree.SubElement(sitemap_root, 'url')
                sitemap_loc_element = etree.SubElement(sitemap_url_element, 'loc')
                sitemap_loc_element.text = i_url.text
                sitemap_priority_element = etree.SubElement(sitemap_url_element, 'priority')
                sitemap_priority_element.text = str(urls_priority)

        if not len(sitemap_root):
            break

        output_file_path = output_dir / f'{prefix}{sitemap_file_number or ""}.xml'

        with output_file_path.open('wb+') as xml_output:
            data_output.write(xml_output, pretty_print=True, encoding='utf-8', xml_declaration=True)
            if need_zip:
                with gzip_open(output_file_path.with_suffix('.xml.gz'), 'wb') as zipped_file:
                    xml_output.seek(0)
                    copyfileobj(xml_output, zipped_file)

        sitemap_index_sitemap_elem = etree.SubElement(sitemap_index_root, 'sitemap')
        sitemap_index_loc_elem = etree.SubElement(sitemap_index_sitemap_elem, 'loc')
        sitemap_index_loc_elem.text = str(output_file_path)

        sitemap_file_number += 1

    if len(sitemap_index_root) > 1:
        output_sitemap_file = output_dir / 'sitemap-index.xml'
        sitemap_index_tree.write(output_sitemap_file, pretty_print=True, encoding='utf-8', xml_declaration=True)


def run() -> None:
    parser = create_parser()
    namespace = parser.parse_args()
    handle(vars(namespace))


if __name__ == "__main__":
    run()
