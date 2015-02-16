"""
Tauren Kristich 
address.py
this is testing version of the address/address parsing class.
"""

import re
import sys

class Address:
    regex_lib = None
    standards = None

    number = None
    intersection_flag = False 
    po_box_flag = False

    street1_predir = None 
    street1 = None
    street1_type = None 
    street1_postdir = None
    street1_pretype = None


    street2_predir = None  
    street2 = None
    street2_type = None 
    street2_postdir = None
    
    apartment = None
    city = None
    state = None
    zip = None
    delta = None # Save remainder of the String
    geocode_level = None
    dev_sections = None # holds how address was parsed/coded

    def __init__(self, regex, standards, address_string):
        self.regex_lib = regex
        self.standards = standards
        addr = self.cleanse(address_string)
        self.parse(addr)
    
    def to_json(self):
        """ return json representation of string """
        return {'number':self.number,
                    'street1':self.street1,
                    'unit':self.apartment,
                    'city':self.city,
                    'state':self.state,
                    'zip':self.zip,
                    'geocode_level':self.geocode_level
                }
        
    def cleanse(self, string):
        """ Clean up string - 
        remove commas, periods, tabs
        Remove excesive whitespace
        TODO: Remove Space between words with hypens
        """
        string = string.upper().strip()
        string = re.sub('[.,\t]', ' ', string)   
        string = re.sub(r'( +)', ' ',  string)
        string = re.sub(r' - ', '-', string)
        return string
        
    def parse(self, addr):
        """ Parse of the address into 
        zip, state, number, apartment/unit,
        PO Box, Street1
        Detect intersection
        TODO: street2
        """
        zip = self.regex_lib.zip_regex.search(addr)
        if zip:
            self.zip = zip.group(0).strip()
            addr = addr.replace(self.zip, '')
        else:
            self.zip = ''

        state = self.regex_lib.state_regex.search(addr)
        if state:
            self.state = state.group(0).strip().upper()
            addr = addr[0:state.span()[0]]    
        else:
            self.state = ''


        # TODO: What if pre text?
        # What if number LIKE A701?
        number = self.regex_lib.number_regex.search(addr)
        if number:
            self.number = number.group(0).strip()
            addr = addr.replace(self.number, '')
            if '-' in self.number:
                self.number = self.number[:self.number.index('-')]
        else:
            self.number = ''
        
        pobox = self.regex_lib.po_regex.search(addr)
        if pobox:
            self.po_box_flag = True


        # TODO: Apt Regex needs to be more flexible
        apt = self.regex_lib.apt_regex.search(addr.strip())
        if apt:
            self.apartment = apt.group(0).strip()
            addr = addr.replace(apt.group(0), '')
        # search for line 2 address
        apt = self.regex_lib.secondary_str_regex.search(addr.strip())
        if apt:
            self.apartment = apt.group(0).strip()
            addr = addr.replace(apt.group(0), '')

        # ISSUE: If no/incorrect zip: need street/city value...
        # HACK: Cannot standardize Street direction until 100% positive
        #   that City is not in street - EAST HAMPTON , EAST HANOVER, ETC
        #intersection_test = re.search(r'(?:\s(AT|@|AND|&)\s)', addr)
        intersection_test = self.regex_lib.intersection_test.search(addr)
        if intersection_test:
            self.intersection_flag = True
            self.street1 = addr[0:intersection_test.span()[0]]
            addr = addr.replace(intersection_test.group(0), '')
            addr = addr.replace(self.street1, '')
            self.street1 = self.street1.upper()

        street = self.regex_lib.street_regex.search(addr)
        if street:
            street = street.group(0).strip().split(' ')
            if self.intersection_flag:
                self.street2 = ' '.join(street)
            else:
                self.street1 = ' '.join(street).upper().strip()
        self.delta = addr

    def post_parse_dev(self):
        """ Standardize Street/Direction Values
        *Q. Would it make sense to standardize all values in one shot? Revisit this. 
        *A. No, we need to hold off until city is [hopefully] found.
        Parses out Street into tokens and standardizes City name
        Examples: North Elm Street
        Elm Street North    White PLAIN Road
        Concourse Village Place Avenue X
        """
        """ 
        Prefix Type-some of these are 2+ words. 
            need to be able to handle this. Maybe via regex with anchor in front?
        If No City is found -> educated guess by chopping off chunks?
        """
        try:

            street = self.street1.upper().strip()
            # Pre-Street Type\
            pretype = self.regex_lib.street_prefix_regex.search(street.strip())
            if pretype:
                self.street1_pretype = pretype.group(0).strip().title()
                street = street.replace(pretype.group(0), '')
            
            addr_tokens = street.split(' ')
            
            if len(addr_tokens) > 2:
                # Post-Direction
                if addr_tokens[-1] in self.standards.street_direction:
                    self.street1_postdir = self.standards.street_direction[addr_tokens[-1]]
                    # remove addr_tokens[-1]      
                    addr_tokens[-1] = self.standards.street_direction[addr_tokens[-1]]
                    del addr_tokens[-1]

                # Post Street Type
                if addr_tokens[-1] in self.standards.cannonical_types:
                    self.street1_type = self.standards.cannonical_types[addr_tokens[-1]].strip()
                    self.street1_type = self.street1_type.strip()
                    del addr_tokens[-1]

                # Pre-Direction
                if len(addr_tokens) > 1 and addr_tokens[0] in self.standards.street_direction:
                    street1_predir = self.standards.street_direction[addr_tokens[0]]
                    del addr_tokens[0]

            else:                
                # Post Street Type
                if addr_tokens[-1] in self.standards.cannonical_types:
                    self.street1_type = self.standards.cannonical_types[addr_tokens[-1]].strip()
                    del addr_tokens[-1]
            self.street1 = ' '.join(addr_tokens).strip()

            # State Standardization
            if (self.state) and (self.state.upper() in self.standards.states_v2):
                self.state = self.standards.states_v2[self.state.upper()]
                # self.state = self.state.title()
                self.state = self.state
        except:
            #print '\t\tERROR IN POST_PARSE_DEV: %s\n%s' % (sys.exc_info()[1], sys.exc_info()[2] ) 
            return