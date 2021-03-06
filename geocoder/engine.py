
import psycopg2
import address
import standards
import regex_library
from fuzzy import DMetaphone
from math import radians, degrees, cos, sin, asin, sqrt, atan, pi, atan2
import sys
import json

class Engine:
    conn = None
    regexlib = regex_library.RegexLib() 

    def __init__(self):
        try:
            self.conn = psycopg2.connect("dbname='geodb' user='postgres' host='104.131.183.132'")
        except psycopg2.Error as e:
            print 'Connection Error: %s' % e.pgerror

    def execute(self, statement):
        """ Return result set in List of Lists """
        results = []
        try:
            cur = self.conn.cursor()
            cur.execute(statement)
            for record in cur:
                results.append(list(record))
            return results
        except:
            print 'Error Executing Query' 
            return []

    def places_by_zip(self, zip):
        """ Retreive place names by zip code only
        results = [zip, city, string distance, county, lat, lon]
        """
        query = "SELECT zip, place, 0, name2, name1, code1, latitude, longitude FROM place WHERE zip = '" + zip + "';"  
        return self.execute(query)

    def places_by_city(self, city):
        """ Retreive zips/place names by city
        results = [zip, city, string distance, county, state, state_abbr lat, lon]
        """
        query = "SELECT zip, place, levenshtein(place,'"+city.title()+ "') as score, name2, name1, code1, latitude, longitude "+\
                    "FROM place WHERE UPPER(place) = UPPER('" + city + "');"  
        return self.execute(query)

    def addrfeats_by_street_zip(self, street, ziplist):
        query = "SELECT gid, tlid, name, levenshtein(name, '"+street+"') score, " +\
                "predirabrv, pretypabrv,suftypabrv, zipl, lcity, zipr, rcity, state, " +\
                "lfromhn, ltohn, rfromhn, rtohn, ST_asText(geom) " +\
                "FROM addrfeat " +\
                "WHERE dmetaphone(name) = dmetaphone('"+street+"') " +\
                "AND ( zipl IN ("+ziplist+") OR zipr IN ("+ziplist+") ) " +\
                "AND levenshtein(name, '"+street+"') < 2 " +\
                "ORDER BY score;" 
                # dev-note:Take out Limit: " ASC LIMIT 10;"
        return self.execute(query)

    def addrfeats_by_street_state(self, street, state):
        query = "SELECT gid, tlid, name, levenshtein(name, '"+street+"') score, " +\
                "predirabrv, pretypabrv,suftypabrv, zipl, lcity, zipr, rcity, state, " +\
                "lfromhn, ltohn, rfromhn, rtohn, ST_asText(geom) " +\
                "FROM addrfeat " +\
                "WHERE dmetaphone(name) = dmetaphone('"+street+"') " +\
                "AND state = '"+state+"' " +\
                "AND levenshtein(name, '"+street+"') < 2 " +\
                "ORDER BY score ASC;"
        return self.execute(query)

    def cities_by_list(self, city_tokens, state_abbr=None):
        """ Expiremental Query to find cities based on probable city tokens
        """    
        query = "SELECT iso_code, zip, place, name1, code1, name2, code2, name3, code3, " +\
                    "latitude, longitude, accuracy " +\
                    "FROM place WHERE dmetaphone(place) IN (" + city_tokens + ") " 
        if state_abbr: query += "AND code1 = '" + state_abbr + "';"
        else: query += ';'
        return self.execute(query)

    def geocode_zipcode(self, address):
        """ Find city, state, lat, lon given a zipcode 
        For testing, Throw "Could not Geocode Zipcode" for tracing
        """
        try:
            # [zip, city, string distance, county, lat, lon]
            place = self.places_by_zip(address.zip)
            if place:
                address.city = place[0][1]
                address.state = place[0][5]
                address.geocode_level = 'zip'
                return self.create_results(address,[place[0][-2],place[0][-1]])
        except:
            return { 'Error' : 'Could not geocode zipcode.'}

    
    def guess_city(self, address):
        """ Typically, cities will be emebeded in the street.
        To counter this, we tokenize the address and created metaphones 
        from reversing the list. 
        """
        tokens = address.street1.split(' ')
        tokens.reverse()

        dmetaphone = DMetaphone()
        
        # initial list is just the metaphones of all tokens in address
        combined = []

        # string together words in order to try and make a match
        potential_word = ''
        for idx in range(len(tokens)-1):
            combined.append(dmetaphone(tokens[idx])[0]) # add metaphone of current word
            potential_word = tokens[idx] + ' ' +  potential_word # string together words
            combined.append(dmetaphone(potential_word)[0])

        # combine list into query string 
        combined = ','.join(["'"+c+"'" for c in combined])

        cities = self.cities_by_list(combined, address.state)
        """ We have to hack this a bit
        Do it this by TOTAL word count in match
        example: EAST HAMPTON vs HAMPTON for addresses in NY 
        """
        match_list = []
        for c in cities:
            if c[2] in address.street1:
                match_list.append( (c,c[2].count(' ')) )  # add match and length of hit               
                address.city = c[2]
                address.street1 = address.street1.replace(c[2],'').strip()    
        # very unscientific - highest match wins!
        # ORDER LIST OF TUPLES         
        match_list.sort(key=lambda tup: tup[1])      
        if match_list[0]: 
            return match_list[0][0]
        return None

    def geocode_address(self, address):
        """ Geocode an address using soley the AddrFeats table """
        places = [] # [zip, City, LevDistance, County, lat, lon]

        # Gather possible City/Zip/State combinations for the search
        # Can we make this a bit more efficient?
        if address.zip:
            places = self.places_by_zip(address.zip)
        if address.city:
            places = places + self.places_by_city(address.city)
        
        # 
        if not places: 
            # this wont because...not city?
            city_guessed = self.guess_city(address)
            if city_guessed==None: 
                if address.zip: return self.geocode_zipcode(address)               
                else: return  {'Error' : 'Could not find a city or zipcode.'}        
            else:
                places.append(city_guessed)

        """ dev-note: take into account case where city name is in street.
        Rule: Extract place names out of the street based on length of city.
        ToDo: implement levenshtein distance calculation here to take care of misplellings. 
        If it's close ENOUGH,
        i.e. 1 pt away, it's probally correct. This would take care of some simple misplellings.
        """
        if places and (address.city is None):
            if ' ' in address.street1: 
                street_tokens = address.street1.split(' ') 
            else:
                street_tokens = [address.street1]
            for place in places:
                # Check for City
                place_length = place[1].count(' ') # get num of words in place name
              
                if place_length >= 1: place_length+=1
                else: place_length += 1

                potential_place = ' '.join(street_tokens[-place_length:])
                if place[1] in potential_place:
                    address.city = place[1]
                    address.street1 = ' '.join(street_tokens[:-place_length])
                    break
                
                # Do This for County...
                place_length = place[3].count(' ') # get num of words in place name
              
                if place_length >= 1: place_length+=1
                else: place_length += 1

                potential_place = ' '.join(street_tokens[-place_length:])
                
                if place[3] in potential_place:
                    address.city = place[3]
                    address.street1 = ' '.join(street_tokens[:-place_length])
                    break
                
        if address.city:
            places = places + self.places_by_city(address.city)
        
        """ ToDo: What if city is still not found?
        Query db for all cities within state?
        """
        if (address.city is None) and (address.street1):
            found_place = self.guess_city(address)
            if found_place==None: return self.geocode_zipcode(address)
            places.append(found_place)               
        if not address.street1 or address.street1 == '': 
            return self.geocode_zipcode(address)

        address.post_parse_dev()      
        
        # Compile list of zipcodes for search
        zips = [ "'" + p[0] + "'" for p in places]
        if len(zips)>1: zips = ','.join(zips)
        else: zips = zips[0] 
        
        candidates = self.addrfeats_by_street_zip(address.street1, zips)
        
        # Try to find the street one last time-broader search.
        if (not candidates) and (address.state):
            candidates = self.addrfeats_by_street_state(address.street1, address.state)    
            
        if candidates:
            # print candidates[0]
            ranked_candidates = self.rank_candidates(address, candidates)
            # need to take in fully qualified street...
            address.street1 = '%s %s' % (address.street1,ranked_candidates[0][6])
            # print '\t%s' % (ranked_candidates[0])
            interpolated_point = self.interpolate(ranked_candidates[0],address)
            # print '\t\tPoint:%s' % (interpolated_point)
            # Reset City + Zip
            address.zip = ranked_candidates[0][7]
            address.city = ranked_candidates[0][8]
            address.geocode_level = 'street'
            return self.create_results(address,interpolated_point)
        else:
            address.geocode_level = 'street-with-issue'
            return address.to_json()

    def rank_candidates(self, address, candidates):
        """ Scoring Algorithm for potential candidates
        1. zip
        """
        """
        0   1       2     3         4            5           6      7       8     9     10    11
        gid, tlid, name, score, predirabrv, pretypabrv,suftypabrv, zipl, lcity, zipr, rcity, state, " +\
        12         13      14       15     16
        lfromhn, ltohn, rfromhn, rtohn, ST_asText(geom)
        """
        candidate_list = []
        for candidate in candidates:
            score = 0

            # Street Score
            if candidate[2] == address.street1: score += 1 
            else: score += 1/candidate[3]
            
            # street type
            if candidate[6]:
                if candidate[6].upper() == address.street1_type: score += 1

            # TODO:Pre/Post Directions 
            
            # zipcode 
            if candidate[7] == address.zip: score += 1
            elif candidate[9] == address.zip: score += 1

            # city
            if candidate[8] == address.city: score += 2
            elif candidate[10] == address.city: score += 2
            
            # Figure out ranges piece
            # TODO: Add which side the point was hitp->this will help in interpolation.
            addr_score = 0
            side_flag = None
            if address.number:
                i = 12
                while i <= 15:
                    try: 
                        if candidate[i] and '-' in candidate[i]: candidate[i]=self.convert_number(candidate[i]) 
                        if (candidate[i+1] and '-' in candidate[i+1]): candidate[i+1]=self.convert_number(candidate[i+1])
                        addr_score += self.check_range(
                                int(candidate[i]), int(candidate[i+1]), int(address.number) ) 
                        if addr_score:
                            if i==12: side_flag='L'
                            else: side_flag='R'
                    except: 
                        pass #Just pass for now aka TODO
                    i+=2
            score += addr_score
            candidate_list.append(candidate + [score] + [side_flag] ) 

        # Sort list by score
        candidate_list.sort(key=lambda x: x[17], reverse=True)
        if len(candidate_list) >= 5:
            return candidate_list[:4]
        else: 
            return candidate_list

    def create_results(self, address, point=None):
        results = { 'street1':address.street1,
                'geocode_level':address.geocode_level
                }
        if address.apartment: results['apartment'] = address.apartment
        if address.number: results['number'] = address.number
        if address.city: results['city'] = address.city
        if address.state: results['state'] = address.state
        if address.zip: results['zipcode'] = address.zip
        if point: 
            results['lat'] = point[0]
            results['lon'] = point[1]
        return results

    def check_range(self, fromnum, tonum, target):
        # score the candidate against a range of numbers
        score=0
        if fromnum <= target <= tonum: 
            score+=1
        elif fromnum >= target >= tonum: 
            score+=1
        return score

    def convert_multilinestring(self, multilinestring):
        """ Point values come in the form of an odd formatted string. 
        Convert string to list of points
        """
        if multilinestring:
            point_list = []
            multilinestring = multilinestring.replace('MULTILINESTRING((','')
            multilinestring = multilinestring.replace('))','')
            multilinestring = multilinestring.split(',')
            for point in multilinestring:
                point = point.split(' ')
                point_list.append([float(point[1]), float(point[0])])
            return point_list
        else: 
            return []

    def convert_number(self, number):
        """ remove '-' in number if exists """
        return int(number[:number.index('-')])
    
    def interpolate(self,candidate, address):
        """ Basic Street to Coordinates Algorithm [Interpolation] 
        Convert multiline string, determine which side of street,
        total houses, total distance of line, 
        for each point to point:
            determine bearing, add until line is filled or steps
            count is met. change bearing if new line point is hit.
        """
        points = []
        points = self.convert_multilinestring(candidate[16])

        # determine sid e better...please?!
        if candidate[16] != None:
            try:    
                """
                print '\tSide=%s' % candidate[-1]
                print '\tLfrom/Lto=%s-%s' % (candidate[12],candidate[13])
                print '\tRfrom/Rto=%s-%s' % (candidate[14],candidate[15])
                """
                fromnum = tonum = 0

                if candidate[-1] == 'L':
                    # set the if bigger/swap here
                    fromnum = int(candidate[12])
                    tonum = int(candidate[13])
                else: 
                    fromnum = int(candidate[14])
                    tonum = int(candidate[15])


                fromnum = float(fromnum)
                tonum = float(tonum)
                
                # This rule is a thing...          
                if fromnum == tonum: return [points[0][0], points[0][1]]   

                # Convert multilinestring to lists of points[lists]
                total_dist = 0
                dist_dict = {}
                for idx in range(len(points)-1):
                    dist_dict[idx] = self.haversine(points[idx][0], points[idx][1], points[idx+1][0], points[idx+1][1])
                    total_dist += dist_dict[idx]
                
                total_steps = 0
                if fromnum <=  tonum: 
                    total_steps = (tonum-fromnum)
                else: 
                    total_steps = (fromnum-tonum)
            
                target_hn = float(address.number)
                ratio = total_dist / ((tonum-fromnum)/2) # tohn could be smaller than
                target_dist = ((target_hn - fromnum)/2) * ratio
                

                interpolated_point = None
                counted_dist = 0
                for k in dist_dict:
                    counted_dist += dist_dict[k]
                    if counted_dist >= target_dist: 
                        delta = counted_dist-target_dist
                        segment_distance = dist_dict[k]-delta 
                        
                        bearing = self.bearing2(points[k][0], points[k][1], points[k+1][0], points[k+1][1])
        
                        interpolated_point = self.find_point2(points[k][0], points[k][1], bearing, segment_distance)
                        break

                if interpolated_point is None: raise Exception('Failed to Geocode')
                else: return interpolated_point
            except:
                print 'ERROR%s' % sys.exc_info()[0]
                return [points[0][0], points[0][1]]
        else: 
            return None
  
    def haversine(self, lat1, lon1, lat2, lon2):
        """ Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        """
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        delta_lat = (lat2-lat1) 
        delta_lon = (lon2-lon1)
        a = sin(delta_lat/2) * sin(delta_lat/2) +\
                cos(lat1) * cos(lat2) * \
                sin(delta_lon/2) * sin(delta_lon/2)
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return 6371 * c

    def bearing2(self, lat1, lon1, lat2, lon2):
        """ Calculate bearing """
        lat1, lat2 = map(radians, [lat1,lat2])
        delta = radians((lon2-lon1))
        y = sin(delta) * cos(lat2)
        # y = sin(lon2-lon1) * cos(lat2);
        x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(lon2-lon1)
        bearing = atan2(y, x) 
        return (degrees(bearing) + 360) % 360

    def find_point2(self, lat, lon, bearing, distance):
        """ create a new point from origin point via 
        a distance and bearing
        """
        d = distance/63741
        lat, lon, bearing = map(radians, [lat,lon,bearing])
        
        new_lat = asin( sin(lat) * cos(d) + cos(lat) * sin(d) * cos(bearing) )
        new_lon = lon + atan2(sin(bearing)*sin(d)*cos(lat),
                         cos(d)-sin(lat)*sin(new_lat))
        new_lon = (new_lon+3*pi) % (2*pi) - pi #normalise...
        return [degrees(new_lat), degrees(new_lon)]

    def geocode(self, addr_string):
        results = ''
        try:
            addr = address.Address(self.regexlib, standards.standards(), addr_string)
            # print addr.to_json()

            # This will take into account streets + cities.
            if addr.street1:
                results = self.geocode_address(addr) # will return a json address...sorta
            elif addr.zip:
                results =  self.geocode_zipcode(addr)
            else:
                results =  { 'Error':'No Results.'}
            return results   
        except:
            error = '%s | %s' % (sys.exc_info()[0],sys.exc_info()[1])
            return {'Error': error}
