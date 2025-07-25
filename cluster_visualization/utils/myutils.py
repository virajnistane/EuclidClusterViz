### -*- coding: utf-8 -*-
### @file: myutils.py
### Author: Viraj Nistane
### Date: 2025-06-30



import os, sys
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import json

from astropy.io import fits
from astropy.table import Table, Column 
from astropy import wcs
from astropy.coordinates import SkyCoord
from astropy import units as u

import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

def get_xml_tree(xml_file):
    """
    Get the XML tree from the given XML file.
    
    Parameters:
    xml_file (str): Path to the XML file.
    
    Returns:
    ElementTree: Parsed XML tree.
    """
    if not os.path.exists(xml_file):
        raise FileNotFoundError(f"XML file {xml_file} does not exist.")
    
    tree = ET.parse(xml_file)
    return tree

def get_xml_root(xml_file):
    """
    Get the root element of the XML tree from the given XML file.
    
    Parameters:
    xml_file (str): Path to the XML file.
    
    Returns:
    Element: Root element of the parsed XML tree.
    """
    tree = get_xml_tree(xml_file)
    return tree.getroot()

def get_xml_element(xml_file, element_name):
    """
    Get the first occurrence of the specified element from the XML file.
    
    Parameters:
    xml_file (str): Path to the XML file.
    element_name (str): Name of the element to find.
    
    Returns:
    Element: The first occurrence of the specified element, or None if not found.
    """
    root = get_xml_root(xml_file)
    return root.find(element_name) if root is not None else None

def get_xml_elements(xml_file, element_name):
    """
    Get all occurrences of the specified element from the XML file.
    
    Parameters:
    xml_file (str): Path to the XML file.
    element_name (str): Name of the element to find.
    
    Returns:
    list: List of all elements with the specified name, or an empty list if not found.
    """
    root = get_xml_root(xml_file)
    return root.findall(element_name) if root is not None else []

def get_xml_text(element):
    """
    Get the text content of an XML element.
    
    Parameters:
    element (Element): The XML element.
    
    Returns:
    str: Text content of the element, or None if the element is None.
    """
    return element.text if element is not None else None

def get_xml_attribute(element, attribute_name):
    """
    Get the value of a specific attribute from an XML element.
    
    Parameters:
    element (Element): The XML element.
    attribute_name (str): Name of the attribute to retrieve.
    
    Returns:
    str: Value of the specified attribute, or None if the element is None or the attribute does not exist.
    """
    return element.get(attribute_name) if element is not None else None

