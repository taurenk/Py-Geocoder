
import os
import sys
import csv
# Workaround: allows the import of package for testing
sys.path.insert(0, os.path.abspath('..'))
# from geocoder import geocoder, address
from PinPointGeocoder.geocoder.engine import Engine

def import_test_data(file):
    dict = {}
    with open(file, 'r') as f:
        reader = csv.reader(f, delimiter=',')
        for row in reader:
            dict[ row[0] ] = row[2] + ',' + row[3] + ',' + row[4] + ',' + row[5]
    return dict

def test_drive():
    # dict = import_test_data('test/data/cms_data.csv')
    dict = import_test_data('test/data/test_data.csv')
    e = Engine()
    for key in dict:
        print '\n\nRow: %s Address: %s' % (key, dict[key])
        # geocoder.Geocoder().geocode( dict[key] )
        x = e.geocode(dict[key])
        print x
        print '\n\n'
if __name__ == '__main__':
    test_drive()