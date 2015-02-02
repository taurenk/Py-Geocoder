
"""
12/24/2014
Compile ALL reusable regex in one location, for centralized use.
"""

import re
import standards

class RegexLib:
	number_regex = re.compile( r'^\d+[-]?(\w+)?')	
	po_regex = re.compile( r'(?:(PO BOX|P O BOX)\s(\d*[- ]?\d*))' )
	intersection_test = re.compile(r'(?:\s(AT|@|AND|&)\s)')
	street_regex = re.compile(r'(?:([A-Z0-9\'\-]+)\s?)+')
	apt_regex = re.compile(r'[#][A-Z0-9]*')
	city_regex = re.compile(r'(?:[A-Z\-]+\s*)+')
	state_regex = None
	zip_regex = re.compile(r'(?:(\d+)|(\d*[- ]?\d*))?$') 
	
	secondary_str_regex = None
	street_prefix_regex = None


	def __init__(self):
		print 'Initiating RegexLib'
		self.state_regex = re.compile(r'(?:\b' + self.import_state_regex() + r')')
		self.street_prefix_regex = re.compile(r'^(' + self.import_prefix_regex() + r')' )
		self.secondary_str_regex = re.compile(r'(?:\s(' + self.import_secondary_regex() + r') \w+?)' )
	
	def import_state_regex(self):
   		"""Generate the US States regex string """
		list = []
   		for key in standards.standards().states:
   			list.append(key + r'\s?$') 
   			list.append(standards.standards().states[key]+ r'\s?$')
   		return r'|'.join(list)

   	def import_secondary_regex(self):
   		list = []
   		for key in standards.standards().units:
   			list.append(key) 
   			list.append(standards.standards().units[key])
   		return r'|'.join(list)
   		
  	def import_prefix_regex(self):
   		list = []
   		for key in standards.standards().tiger_prefix_types:
   			list.append(key + r'\s?') 
   			list.append(standards.standards().tiger_prefix_types[key]+ r'\s?')
   		return r'|'.join(list)
   		