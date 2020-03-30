#!/usr/bin/env python3

import os, sys
import xml.etree.ElementTree as ET
import argparse
import base64
import copy

MAX_SEGMENTS_DEFAULT = 1024

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

def parse_cmdline():
    parser = argparse.ArgumentParser(description="Dissect XLIFF file")
    parser.add_argument("--segments", "-s", type=int, default=MAX_SEGMENTS_DEFAULT,
            metavar="N", help="Soft maximum segment count")
    parser.add_argument("file", type=str, metavar="FILE", help="name of the file to process")
    args = parser.parse_args()

    if not args.file:
        raise Exception("No source file was given")

    return args

class SegmentCounter:
    def __init__(self, max_segments=MAX_SEGMENTS_DEFAULT, file_pattern='part-{}.xlf'):
        self.count = 0
        self.max_segments = max_segments
        self.chunk = 0
        self.file_pattern = file_pattern

    @property
    def current_chunk(self):
        return self.chunk

    @property
    def next_chunk(self):
        count = self.count + 1
        chunk = self.chunk
        if count >= self.max_segments:
            chunk += 1
            self.chunk = chunk
            count = 0

        self.count = count
        self.chunk = chunk

        return chunk

    def process_group(self, group):
        output_group = copy.copy(group)
        output_group[:] = []
        chunk = self.current_chunk

        for elem in group:
            if elem.tag == TAG_GROUP:
                for grp_chunk, grp_part in self.process_group(elem):
                    if grp_chunk != chunk:
                        yield chunk, output_group
                        chunk = grp_chunk
                        output_group = copy.copy(group)
                        output_group[:] = [ grp_part ]

                    else:
                        output_group.append(grp_part)

            elif elem.tag == TAG_TRANS_UNIT:
                output_group.append(elem)
                next_chunk = self.next_chunk
                if next_chunk != chunk:
                    yield chunk, output_group
                    chunk = next_chunk
                    output_group = copy.copy(group)
                    output_group[:] = []

            else:
                raise Exception("Unexpected tag: {}".format(elem.tag))

        if output_group:
            yield chunk, output_group

    def process_file(self, file):
        body = file.find('./x:body', NAMESPACES)
        for chunk, part in self.process_group(body):
            out_file = copy.copy(file)
            out_file[:] = [ part ]
            yield self.file_pattern.format(chunk), out_file


def process_file(args):
    for key, url in NAMESPACES_OUT:
        ET.register_namespace(key, url)

    parsed_xml = ET.parse(args.file)

    root = parsed_xml.getroot()
    attachments_xml = copy.copy(root)
    attachments_xml[:] = []

    file_index = 0
    for file in root.iterfind('./x:file', NAMESPACES):
        binary = file.find('./x:header/x:reference/x:internal-file', NAMESPACES)

        if binary is not None:
            form = binary.get('form')
            if form != 'base64':
                raise Exception("unknown attachment format: {}".format(form))

            content = base64.decodebytes(binary.text.encode('ascii'))
            with open(file.get('original'), "wb") as fd:
                fd.write(content)

            attachments_xml.append(copy.copy(file))

        else:
            body = file.find('./x:body', NAMESPACES)
            if body:
                counter = SegmentCounter(max_segments=args.segments,
                        file_pattern='{}.file{}.part{{}}.xlf'.format(args.file, file_index))
                for file_name, file_part in counter.process_file(file):
                    file_xml = copy.copy(root)
                    file_xml[:] = [ file_part ]
                    with open(file_name, 'wb') as fd:
                        fd.write(ET.tostring(file_xml, encoding="utf-8"))

    with open(args.file + '.attachments.xlf', 'wb') as fd:
        fd.write(ET.tostring(attachments_xml, encoding="utf-8"))

if __name__ == '__main__':
    args = parse_cmdline()
    process_file(args)
