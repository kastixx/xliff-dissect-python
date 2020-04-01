#!/usr/bin/env python3

import os, sys
import xml.etree.ElementTree as ET
import argparse
import copy
import re

NS_XLIFF = 'urn:oasis:names:tc:xliff:document:1.2'

NAMESPACES_OUT = [
        ( '', NS_XLIFF ),
        ( 'its', "http://www.w3.org/2005/11/its" ),
        ( 'itsxlf', "http://www.w3.org/ns/its-xliff/" ),
        ( 'okp', "okapi-framework:xliff-extensions" ),
        ( 'mtc', "https://www.matecat.com" ),
        ]

NAMESPACES = {
    'x': NS_XLIFF,
    'its': "http://www.w3.org/2005/11/its",
    'itsxlf': "http://www.w3.org/ns/its-xliff/",
    'okp': "okapi-framework:xliff-extensions",
    'mtc': "https://www.matecat.com",
    }

NS_XLIFF_PREFIX = '{' + NS_XLIFF + '}'

TAG_GROUP = NS_XLIFF_PREFIX + 'group'
TAG_TRANS_UNIT = NS_XLIFF_PREFIX + 'trans-unit'
TAG_BODY = NS_XLIFF_PREFIX + 'body'

def parse_cmdline():
    parser = argparse.ArgumentParser(description="Combine XLIFF file that was splitted by dissect tool")
    parser.add_argument("file", type=str, metavar="FILE", help="name of the file to combine to")
    args = parser.parse_args()

    if not args.file:
        raise Exception("No source file was given")

    return args

def add_chunk(base, add):
    if not add:
        return

    first_elem = add[0]
    if (first_elem.tag == TAG_GROUP and
            base[-1].tag == TAG_GROUP and
            base[-1].attrib['id'] == first_elem.attrib['id']):
        add_chunk(base[-1], add[0])
        add = add[1:]

    else:
        add = add[:]

    base.extend(add)

def merge_files(filenames):
    first_file, *others = filenames

    out_xml = ET.parse(first_file)
    root = out_xml.getroot()
    body = root.find('./x:file/x:body', NAMESPACES)
    print("Rc {}".format(first_file))

    for filename in others:
        add_xml = ET.parse(filename)
        add_root = add_xml.getroot()
        add_body = add_root.find('./x:file/x:body', NAMESPACES)
        add_chunk(body, add_body)
        print("Rca {}".format(filename))

    return root

def process_file(args):
    for key, url in NAMESPACES_OUT:
        ET.register_namespace(key, url)

    re_part = re.compile('^{}\\.file([0-9]+)\\.part([0-9]+)\\.xlf$'.format(re.escape(args.file)))

    part_files = {}
    for filename in os.listdir('.'):
        match = re_part.match(filename)
        if not match:
            continue

        file_index = int(match.group(1))
        part_index = int(match.group(2))

        part_files.setdefault(file_index, []).append((part_index, filename))

        for part in part_files.values():
            part.sort(key=lambda p: p[0])

    attachments_xml = ET.parse(args.file + '.attachments.xlf')

    root = attachments_xml.getroot()

    for file_index, file in enumerate(root.iterfind('./x:file', NAMESPACES)):
        parts = part_files.get(file_index, None)
        if not parts:
            continue

        body = file.find('./x:body', NAMESPACES)
        if body is None:
            continue

        merged_xml = merge_files(fn for _, fn in parts)
        merged_body = merged_xml.find('./x:file/x:body', NAMESPACES)
        if not merged_body:
            continue

        body[:] = merged_body[:]

    with open(args.file + '.combined.xlf', 'wb') as fd:
        fd.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))

    print("W {}".format(args.file + ".combined.xlf"))

if __name__ == '__main__':
    args = parse_cmdline()
    process_file(args)
