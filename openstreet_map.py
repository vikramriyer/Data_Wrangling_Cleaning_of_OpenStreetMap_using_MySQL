#!/usr/bin/env python
# -*- coding: utf-8 -*-

import xml.etree.cElementTree as ET
import re
from collections import defaultdict
import csv
import codecs
import pprint
import cerberus
import schema

#files
OSM_FILE = "pune_india.osm"
NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']

SCHEMA = schema.schema

#regex patterns
LEGAL_POSTAL_CODES = re.compile(r'^(411)[0-9]{3}$')
ILLEGAL_POSTAL_CODES = [re.compile(r'^(411) [0-9]{3}$'), re.compile(r'^(411)[0-9] [0-9]{2}$'), re.compile(r'^(411)[0-9]{2} [0-9]$')]
path_marg_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)
street_types = defaultdict(set)

mapping = {
    "Rd": "Road",
    "Path": "Road",
    "Marg": "Road",
    "road": "Road"
}


def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS):

    # have to set node_attribs, tags, way_attribs, way_nodes, way_tags
    if element.tag == 'node':
        node_attribs, tags = set_node_attributes(element)
        return {'node': node_attribs, 'node_tags': tags}
    elif element.tag == 'way':
        way_attribs, way_nodes, tags = set_way_attributes(element)
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}

def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file, \
            codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
            codecs.open(WAYS_PATH, 'w') as ways_file, \
            codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
            codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        all_elements_file = []

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)

            all_elements_file.append(el)

            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])

        print all_elements_file

#####################################################################################
##                                  Helpers                                        ##
#####################################################################################

def set_way_attributes(element):
    way_attribs = {}
    way_nodes = []
    tags = []

    way_attribs['id'] = element.attrib['id']
    way_attribs['version'] = element.attrib['version']
    way_attribs['timestamp'] = element.attrib['timestamp']
    way_attribs['changeset'] = element.attrib['changeset']
    way_attribs['user'] = element.attrib['user']
    way_attribs['uid'] = element.attrib['uid']

    position_counter = 0
    for child in element:
        way_tags = {}
        if child.tag == 'nd':
            way_nodes.append({'id': element.attrib['id'], 'node_id': child.attrib['ref'], 'position': position_counter})
            position_counter += 1
        else:
            if ':' in child.attrib['k']:
                keys_values = child.attrib['k'].split(":", 1)
                way_tags['type'] = keys_values[0]
                way_tags['key'] = keys_values[1]
                way_tags['value'] = child.attrib['v']
                way_tags['id'] = element.attrib['id']
                tags.append(dict(way_tags))
            else:
                way_tags['type'] = 'regular'
                way_tags['key'] = child.attrib['k']
                way_tags['value'] = child.attrib['v']
                way_tags['id'] = element.attrib['id']
                tags.append(way_tags)

    return way_attribs, way_nodes, tags


def set_node_attributes(element):
    node_attribs = {}
    tags = []

    node_attribs['id'] = element.attrib['id']
    node_attribs['version'] = element.attrib['version']
    node_attribs['timestamp'] = element.attrib['timestamp']
    node_attribs['changeset'] = element.attrib['changeset']
    node_attribs['lat'] = element.attrib['lat']
    node_attribs['lon'] = element.attrib['lon']
    node_attribs['user'] = element.attrib['user']
    node_attribs['uid'] = element.attrib['uid']

    for child in element:
        node_tags = {}
        if ':' in child.attrib['k']:
            keys_values = child.attrib['k'].split(":", 1)
            node_tags['type'] = keys_values[0]
            node_tags['key'] = keys_values[1]
            node_tags['value'] = child.attrib['v']
            node_tags['id'] = element.attrib['id']
            tags.append(dict(node_tags))
        else:
            node_tags['type'] = 'regular'
            node_tags['key'] = child.attrib['k']
            node_tags['value'] = child.attrib['v']
            node_tags['id'] = element.attrib['id']
            tags.append(dict(node_tags))

    return node_attribs, tags

def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()

def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)

        raise Exception(message_string.format(field, error_string))

class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

def read_osm_file():
    return ET.iterparse(OSM_FILE, events=('start','end'))

def get_all_top_level_tags():

    all_top_level_tags = {}
    context = read_osm_file()
    _, root = next(context)

    for event, elem in context:
        tag = elem.tag
        if event == 'start':
            if tag in all_top_level_tags:
                all_top_level_tags[tag] += 1
            else:
                all_top_level_tags[tag] = 1

    return all_top_level_tags

def is_street_type(street_type):
    return street_type == "addr:street"

def audit_data():

    context = read_osm_file()
    _,root = next(context)

    for event, elem in context:
        tag_name = elem.tag
        if tag_name == 'way' or tag_name == 'node':
            for tag in elem.iter("tag"):
                if is_street_type(tag.attrib['k']):
                    audit_street_types(tag.attrib['v'])

    return street_types

def audit_street_types(street_name):

    match = path_marg_re.search(street_name)

    if match:
        street_types[match.group()].add(street_name)

def update_name(name, mapping):

    values = re.split(" ",name)

    for key,value in mapping.iteritems():
        if key in values:
            name = name.replace(key, value)
    return name

if __name__ == '__main__':

    #print "1. get all to level tags"
    #all_top_level_tags = get_all_top_level_tags()
    #print all_top_level_tags

    print "2. Audit the data"
    street_tp = audit_data()
    print street_tp

    for type, ways_nodes in street_tp.iteritems():
        for name in ways_nodes:
            print update_name(name, mapping)

    print "3. Convert to csv"
    process_map(OSM_FILE, validate=True)