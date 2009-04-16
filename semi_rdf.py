#!/usr/bin/python
#
# A non-validating, semi-compliant parser for XML/RDF; it's meant
# to handle most things that would be in a DOAP file.
#
# Copyright (C) 2009  Red Hat, Inc
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, If not, see
# http://www.gnu.org/licenses/.
#
import re
import sys
import xml.sax

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XML = "http://www.w3.org/XML/1998/namespace"

WHITESPACE_RE = re.compile("\s+")

class Node:
    def __init__(self, name, about):
        self.name  = name
        self.about = None
        self.properties = []

    def find_property(self, name, lang="en"):
        value = None
        for (n, l, v) in self.properties:
            if n == name:
                if l == lang:
                    return v
                elif l == None or value == None:
                    value = v

        return value

class RdfHandler(xml.sax.handler.ContentHandler):
    def __init__(self):
        self.nodes = []
        self.__node_stack = []
        self.__property_stack = []
        self.__lang_stack = []
        self.__object = None
        self.__depth = 0

    def characters(self, s):
        if isinstance(self.__object, basestring):
            self.__object += s
        elif s.strip() != "":
            self.__object = s

    def startElementNS(self, name, qname, attributes):
        if name == (RDF, "RDF"):
            return

        self.__depth += 1
        try:
            lang = attributes.getValue((XML, "lang"))
        except KeyError:
            if self.__depth > 1:
                lang = self.__lang_stack[-1]
            else:
                lang = None
        self.__lang_stack.append(lang)

        if self.__depth % 2 == 0:
            node = None
            resource = None
            for attrname in attributes.getNames():
                if attrname == (XML, "lang"):
                    pass
                elif attrname == (RDF, "resource"):
                    resource = attrname
                elif attrname == (RDF, "parseType"):
                    parseType = attributes.getValue(attrname)
                    if parseType == "resource":
                        if node == None:
                            node = Node(None, None)
                else:
                    if node == None:
                        node = Node(None, None)
                    node.properties.append((attrname, lang, attributes.getValue(attrname)))
            self.__property_stack.append((name, lang, resource))
            if node is not None:
                print node.properties
                self.__node_stack.append(node)
                self.__depth += 1
        else:
            node = Node(name, None)
            self.__node_stack.append(node)
            for attrname in attributes.getNames():
                if attrname == (RDF, "about"):
                    node.about = attributes.getValue(attrname)
                else:
                    node.properties.append((attrname, lang, attributes.getValue(attrname)))

    def popProperty(self):
        (predicate, lang, resource) = self.__property_stack.pop()
        if self.__object:
            obj = self.__object
            if isinstance(obj, basestring):
                obj = obj.strip()
                obj = WHITESPACE_RE.sub(" ", obj)
        else:
            obj = resource
        self.__object = None
        self.__node_stack[-1].properties.append((predicate, lang, obj))

    def popNode(self):
        node = self.__node_stack.pop()
        self.__object = node
        self.nodes.append(node)
        return node

    def endElementNS(self, name, qname):
        if name == (RDF, "RDF"):
            return

        if self.__depth % 2 == 0:
            self.popProperty()
        else:
            node = self.popNode()
            if (node.name == None): # omitted blank node
                self.popProperty()
                self.__depth -= 1

        self.__lang_stack.pop()
        self.__depth -= 1

def read_rdf(f):
    handler = RdfHandler()

    parser = xml.sax.make_parser()
    parser.setContentHandler(handler)
    parser.setFeature(xml.sax.handler.feature_namespaces, 1)
    parser.parse(f)

    return handler.nodes

