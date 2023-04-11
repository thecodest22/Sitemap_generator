#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from argparse import ArgumentParser
from gzip import open as gzip_open
from itertools import islice, chain, zip_longest
from pathlib import Path
from pprint import pprint
from re import search
from shutil import copyfileobj
from sys import exit
from time import perf_counter
from typing import Union, Iterable

try:
    from lxml import etree
except ModuleNotFoundError as e:
    print(e.msg, "Make sure it has been installed to the active environment!", sep='\n')
    exit(1)


def run() -> None:
    """Controls the general workflow. Also measures the script execution time and prints a report (if requested).
    The workflow includes:
      1. Creation a parser with necessary arguments;
      2. Parsing command-line arguments;
      3. Execution of work logic with a report generation;
      4. Printing the report.

    :return: None
    """
    report_info = {
        'time spent (sec)': perf_counter(),
    }

    parser = create_parser()
    namespace = parser.parse_args()
    report_info, print_report = handle(vars(namespace), report_info)
    report_info['time spent (sec)'] = round(perf_counter() - report_info['time spent (sec)'], 6)

    if print_report:
        pprint(report_info, sort_dicts=False, width=10)


def create_parser() -> ArgumentParser:
    """Creates a parser instance and adds necessary arguments to it.
    Some of these arguments undergo additional value validation by calling validation functions when parsing.

    :return: A parser instance
    """
    parser = ArgumentParser(description='Parses command-line arguments for further sitemap creation')
    parser.add_argument('-f', '--file', type=Path, required=True,
                        help='Path to an XML-file (or a gz-archive with it)')
    parser.add_argument('-t', '--target tag(s)', nargs='*',
                        help='Tag(s) to find and include in the sitemap (separated by space).'
                             'See the "readme" for details!')
    parser.add_argument('-o', '--output dir', type=Path, default='./sitemap',
                        help='Path to the directory where the sitemap will be placed')
    parser.add_argument('-a', '--addresses per file', type=addresses_num_validator, default=50_000,
                        help='Max addresses number for each sitemap file (up to 50k)')
    parser.add_argument('-u', '--url priority', type=priority_range_validator, default=0.3,
                        help='URLs priority (from 0 to 1.0')
    parser.add_argument('-p', '--filename prefix', type=filename_prefix_validator, default='sitemap',
                        help='Prefix to use in output filenames, eg. "prefix.xml", "prefix1.xml"...')
    parser.add_argument('-z', '--zip', action='store_true', help='Add sitemap archive files (.gz)')
    parser.add_argument('-r', '--report', action='store_true', help='Print a short report')

    return parser


def addresses_num_validator(digits: str) -> int:
    """Check if the value is in an allowable range.

    :param digits: A string with digits

    :raise ValueError: If the value is not in an allowable range

    :return: A validated integer value
    """
    digits = int(digits)
    if not 0 < digits <= 50_000:
        raise ValueError
    return digits


def priority_range_validator(priority: str) -> float:
    """Check if the value is in an allowable range.

        :param priority: A string with digits

        :raise ValueError: If the value is not in an allowable range

        :return: A validated float value
    """
    priority = float(priority)
    if not 0 <= priority <= 1:
        raise ValueError
    return priority


def filename_prefix_validator(prefix: str) -> str:
    """Checks if string contains any of the unallowable symbols.
    It should prevent the creation of a file with a name that is not valid for a server.

    :param prefix: A string to check

    :raise ValueError: If any of unallowable symbols is in the string

    :return: The same string
    """
    if search(r'[#<>$+%!`&*‘|{}?"=/:\\ @[\]]', prefix):  # I'm not sure about this set of symbols!
        raise ValueError
    return prefix


def handle(options: dict, report: dict) -> tuple[dict, bool]:
    """Controls the working logic of the script.
    It calls the necessary functions to create directories, parse input, create data trees, and write them to files.

    :param options: Parsed arguments from a command-line
    :param report: A dict for collecting report data

    :return: (Report data dict, Boolean whether to print the report)
    """
    input_xml_file: Path = options['file']
    output_dir: Path = options['output dir']
    entries_number: int = options['addresses per file']
    urls_priority: float = options['url priority']
    prefix: str = options['filename prefix']
    need_zip: bool = options['zip']
    tags: list[str] = options['target tag(s)']
    need_report: bool = options['report']

    input_xml_file = input_xml_file.resolve()
    try:
        parsed_xml_tree = etree.parse(input_xml_file)
    except IOError:
        print(f'File "{input_xml_file}" does not exist')
        exit(1)
    except etree.XMLSyntaxError:
        print(f'File "{input_xml_file}" contains invalid elements')
        exit(1)

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report['sitemap path'] = str(output_dir)

    # Make a sitemap-index tree. It will be need if there are more than one sitemap files
    sitemap_index_root = etree.Element('sitemapindex', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    sitemap_index_tree = etree.ElementTree(sitemap_index_root)

    # Get iterators based on the specified tags
    element_iterators, report = get_element_iterators(parsed_xml_tree, tags, report)

    # Create sitemap trees and write them to files until the iterator is empty
    while True:
        sitemap_tree, report = make_sitemap_tree(element_iterators, entries_number, urls_priority, report)

        if not len(sitemap_tree.getroot()):
            break

        output_file_path, report = write_sitemap_tree(sitemap_tree, output_dir, prefix, need_zip, report)

        sitemap_index_sitemap = etree.SubElement(sitemap_index_root, 'sitemap')
        etree.SubElement(sitemap_index_sitemap, 'loc').text = str(output_file_path)

    # Write the sitemap-index tree to a file if there are multiple sitemap files
    if len(sitemap_index_root) > 1:
        report = write_sitemap_index_tree(sitemap_index_tree, output_dir, report)

    return report, need_report


def get_element_iterators(element: Union[etree.Element, etree.ElementTree], xpath_expressions: list[str],
                          report: dict) -> tuple[chain, dict]:
    """Takes a tag(s) to be found in an upload data file and returns an iterator(s) with the found elements.
    Also fills the report dict with data for further tags counting.

    :param element: An instance of ElementTree or Element. In the latter case it must be the root of the tree
    :param xpath_expressions: A tag(s) to be found. It must be represented as XPath expressions.
        See the "readme" for more information
    :param report: A dict for collecting report data

    :return: (An iterator that returns item: (ElementTree instance, XPath expression), Report data dict)
    """
    report['tags handled'] = dict.fromkeys(xpath_expressions, 0)
    iterators = []
    for x_path in xpath_expressions:
        try:
            iterators.append(zip_longest(element.iterfind(x_path), [], fillvalue=x_path))
        except SyntaxError:
            print(f'Wrong syntax of the tag "{x_path}". See the "readme" for help!')
            exit(1)

    return chain(*iterators), report


def make_sitemap_tree(iterators: Iterable, entries_num: int, url_priority: float,
                      report: dict) -> tuple[etree.ElementTree, dict]:
    """Creates a sitemap tree (ElementTree), adds elements there and counts the number of handled tags.

    :param iterators: An iterator that yields tree elements (Element) and tag names
    :param entries_num: A number of entries per sitemap file
    :param url_priority: A value of url priority in a sitemap
    :param report: A dict for collecting report data

    :return: (An ElementTree filled by data, Report data dict)
    """
    sitemap_root = etree.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    sitemap_tree = etree.ElementTree(sitemap_root)
    url_priority = str(url_priority)

    for i_elem, i_tag in islice(iterators, entries_num):
        if i_elem.text:
            sitemap_url = etree.SubElement(sitemap_root, 'url')
            etree.SubElement(sitemap_url, 'loc').text = i_elem.text
            etree.SubElement(sitemap_url, 'priority').text = url_priority
            report['tags handled'][i_tag] += 1

    return sitemap_tree, report


def write_sitemap_tree(tree: etree.ElementTree, output_path: Path, filename_prefix: str, zipped: bool,
                       report: dict) -> tuple[Path, dict]:
    """Writes the sitemap tree to a file and counts the number of created files. Also archives files if required.

    :param tree: An ElementTree instance
    :param output_path: A directory path for sitemap output files
    :param filename_prefix: A prefix to be included to the file name
    :param zipped: Is files archiving required
    :param report: A dict for collecting report data

    :return: (A path to the created file, Report data dict)
    """
    file_number = report.get('sitemap files created', 0)
    output_file = output_path / f'{filename_prefix}{file_number or ""}.xml'
    report['sitemap files created'] = file_number + 1

    with output_file.open('wb+') as xml_output:
        tree.write(xml_output, pretty_print=True, encoding='utf-8', xml_declaration=True)
        if zipped:
            with gzip_open(output_file.with_suffix('.xml.gz'), 'wb') as zipped_file:
                # This way is faster than rewriting by the tree method - tree.write(zipped_file)
                xml_output.seek(0)
                copyfileobj(xml_output, zipped_file)

    return output_file, report


def write_sitemap_index_tree(tree: etree.ElementTree, output_path: Path, report: dict) -> dict:
    """Writes the sitemap-index tree to a file and sets the number of created sitemap-index files to 1.

    :param tree: An ElementTree instance
    :param output_path: A directory path for sitemap-index output file
    :param report: A dict for collecting report data

    :return: Report data dict
    """
    output_sitemap_index_file = output_path / 'sitemap-index.xml'
    tree.write(output_sitemap_index_file, pretty_print=True, encoding='utf-8', xml_declaration=True)
    report['sitemap-index created'] = 1

    return report


if __name__ == "__main__":
    run()
