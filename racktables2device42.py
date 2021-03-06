#!/usr/bin/env python
# -*- coding: utf-8 -*-
__version__ = 5.0

"""
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

#############################################################################################################
# v5.0 of python script that connects to RackTables DB and migrates data to Device42 appliance using APIs
# Refer to README for further instructions
#############################################################################################################


import sys
import os
import pymysql as sql
import codecs
import requests
import base64 
import struct
import socket
import json


try:
    requests.packages.urllib3.disable_warnings() 
except:
    pass


# ====== MySQL Source (Racktables) ====== #
DB_IP       = '192.168.3.160'
DB_PORT     = '3306'
DB_NAME     = 'racktables_db'
DB_USER     = 'root'
DB_PWD      = 'P@ssw0rd'
# ====== Log settings ==================== #
LOGFILE     = 'migration.log'
STDOUT      = True # print to STDOUT
DEBUG       = True # write debug log
DEBUG_LOG   = 'debug.log'
# ====== Device42 upload settings ========= #
D42_USER    = 'admin'
D42_PWD     = 'adm!nd42'
D42_URL     = 'https://192.168.3.30'
# ====== Other settings ========= #
CHILD_AS_BUILDING   = True      # use RT's sub-location as Device42 building. If False, use it as a Device42 room.
ROW_AS_ROOM         = True      # use RT's row as Device42 room.
                                # Note: Rooms are required because racks are mounted to rooms, not to buildings!
PDU_MOUNT           = 'left'    # Can be one of: left, right, above, below. Used for Zero-U PDU migration. Default is 'left'
PDU_ORIENTATION     = 'front'   # can be one of: front, back. Used for Zero-U PDU migration. Default is 'front'

class Logger():
    def __init__(self, logfile, stdout):
        self.logfile    = logfile
        self.stdout     = stdout
        self.check_log_file()

    def check_log_file(self):
        while 1:
            if os.path.exists(self.logfile):
                reply = raw_input("[!] Log file already exists. Overwrite or append [O|A]? ")
                if reply.lower().strip() == 'o':
                    with open(self.logfile, 'w'):
                        pass
                    break
                elif reply.lower().strip() == 'a':
                    break
            else:
                break
        if DEBUG and os.path.exists(DEBUG_LOG):
            with open(DEBUG_LOG, 'w'):
                pass

    def writer(self, msg):  
        if LOGFILE and LOGFILE != '':
            with codecs.open(self.logfile, 'a', encoding = 'utf-8') as f:
                msg = msg.decode('UTF-8','ignore')
                f.write(msg + '\r\n')  # \r\n for notepad
        if self.stdout:
            try:
                print msg
            except:
                print msg.encode('ascii', 'ignore') + ' # < non-ASCII chars detected! >'

    @staticmethod
    def debugger(msg):
        if DEBUG_LOG and DEBUG_LOG != '':
            with codecs.open(DEBUG_LOG, 'a', encoding = 'utf-8') as f:
                title, message = msg
                row = '\n-----------------------------------------------------\n%s\n%s' % (title,message)
                f.write(row + '\r\n\r\n')  # \r\n for notepad


class REST():
    def __init__(self):
        self.password = D42_PWD
        self.username = D42_USER
        self.base_url = D42_URL
        
    def uploader(self, data, url):
        payload = data
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(self.username + ':' + self.password),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        r = requests.post(url, data=payload, headers=headers, verify=False)
        msg =  unicode(payload)
        logger.writer(msg)
        msg = 'Status code: %s' % str(r.status_code)
        logger.writer(msg)
        msg = str(r.text)
        logger.writer(msg)

        try:
            return r.json()
        except Exception as e:

            print '\n[*] Exception: %s' % str(e)
            pass

    def fetcher(self, url):
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(self.username + ':' + self.password),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        r   = requests.get(url, headers=headers, verify=False)
        msg = 'Status code: %s' % str(r.status_code)
        logger.writer(msg)
        msg = str(r.text)
        logger.writer(msg)
        return r.text
        
    def post_subnet(self, data):
        url = self.base_url+'/api/1.0/subnets/'
        msg =  '\r\nPosting data to %s ' % url
        logger.writer(msg)
        self.uploader(data, url)

    def post_ip(self, data):
        url = self.base_url+'/api/ip/'
        msg =  '\r\nPosting IP data to %s ' % url
        logger.writer(msg)
        self.uploader(data, url)
            
    def post_device(self, data):
        url = self.base_url+'/api/1.0/device/'
        msg =  '\r\nPosting device data to %s ' % url
        logger.writer(msg)
        self.uploader(data, url)
            
    def post_location(self, data):
        url = self.base_url+'/api/1.0/buildings/'
        msg =  '\r\nPosting location data to %s ' % url
        logger.writer(msg)
        self.uploader(data, url)
            
    def post_room(self, data):
        url = self.base_url+'/api/1.0/rooms/'
        msg =  '\r\nPosting room data to %s ' % url
        logger.writer(msg)
        self.uploader(data, url)
            
    def post_rack(self, data):
        url = self.base_url+'/api/1.0/racks/'
        msg =  '\r\nPosting rack data to %s ' % url
        logger.writer(msg)
        response = self.uploader(data, url)
        return response

    def post_pdu(self, data):
        url = self.base_url+'/api/1.0/pdus/'
        msg =  '\r\nPosting PDU data to %s ' % url
        logger.writer(msg)
        response = self.uploader(data, url)
        return response

    def post_pdu_model(self, data):
        url = self.base_url+'/api/1.0/pdu_models/'
        msg =  '\r\nPosting PDU model to %s ' % url
        logger.writer(msg)
        response = self.uploader(data, url)
        return response

    def post_pdu_to_rack(self, data, rack):
        url = self.base_url+'/api/1.0/pdus/rack/'
        msg =  '\r\nPosting PDU to rack %s ' % rack
        logger.writer(msg)
        self.uploader(data, url)

    def post_hardware(self, data):
        url = self.base_url+'/api/1.0/hardwares/'
        msg =  '\r\nAdding hardware data to %s ' % url
        logger.writer(msg)
        self.uploader(data, url)

    def post_device2rack(self, data):
        url = self.base_url+'/api/1.0/device/rack/'
        msg =  '\r\nAdding device to rack at %s ' % url
        logger.writer(msg)
        self.uploader(data, url)

    def post_building(self, data):
        url = self.base_url+'/api/1.0/buildings/'
        msg =  '\r\nUploading building data to %s ' % url
        logger.writer(msg)
        self.uploader(data, url)
            
    def get_pdu_models(self):
        url = self.base_url+'/api/1.0/pdu_models/'
        msg =  '\r\nFetching PDU models from %s ' % url
        logger.writer(msg)
        self.fetcher(url)
        
    def get_racks(self):
        url = self.base_url+'/api/1.0/racks/'
        msg =  '\r\nFetching racks from %s ' % url
        logger.writer(msg)
        data = self.fetcher(url)
        return data
            
    def get_devices(self):
        url = self.base_url+'/api/1.0/devices/'
        msg =  '\r\nFetching devices from %s ' % url
        logger.writer(msg)
        data = self.fetcher(url)
        return data

    def get_buildings(self):
        url = self.base_url+'/api/1.0/buildings/'
        msg =  '\r\nFetching buildings from %s ' % url
        logger.writer(msg)
        data = self.fetcher(url)
        return data

    def get_rooms(self):
        url = self.base_url+'/api/1.0/rooms/'
        msg =  '\r\nFetching rooms from %s ' % url
        logger.writer(msg)
        data = self.fetcher(url)
        return data

        
class DB():
    """
    Fetching data from Racktables and converting them to Device42 API format.
    """
    def __init__(self):
        self.con                = None
        self.tables             = []
        self.rack_map           = []
        self.vm_hosts           = {}
        self.rack_id_map        = {}
        self.container_map      = {}
        self.building_room_map  = {}
        
    def connect(self):
        """
        Connection to RT database
        :return:
        """
        self.con = sql.connect(host=DB_IP,  port=int(DB_PORT),  db=DB_NAME, user=DB_USER, passwd=DB_PWD)

    @staticmethod
    def convert_ip(ip_raw):
        """
        IP address conversion to human readable format
        :param ip_raw:
        :return:
        """
        ip = socket.inet_ntoa(struct.pack('!I', ip_raw))
        return ip

    def get_ips(self):
        """
        Fetch IPs from RT and send them to upload function
        :return:
        """
        adrese = []
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = 'SELECT * FROM IPv4Address WHERE IPv4Address.name != ""'
            cur.execute(q)
            ips = cur.fetchall()
            if DEBUG:
                msg = ('IPs',str(ips))
                logger.debugger(msg)
        
        for line in ips:
            net = {}
            ip_raw, name, comment, reserved = line
            ip = self.convert_ip(ip_raw)
            adrese.append(ip)
          
            net.update({'ipaddress':ip})
            msg =  'IP Address: %s' % ip
            logger.writer(msg)

            net.update({'tag':name})
            msg =  'Label: %s' % name
            logger.writer(msg)
            rest.post_ip(net)

    def get_subnets(self):
        """
        Fetch subnets from RT and send them to upload function
        :return:
        """
        subs = {}
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = "SELECT * FROM IPv4Network" 
            cur.execute(q)
            subnets = cur.fetchall()
            if DEBUG:
                msg = ('Subnets',str(subnets))
                logger.debugger(msg)
        for line in subnets:
            sid, raw_sub, mask, name, x = line
            subnet = self.convert_ip(raw_sub)
            subs.update({'network':subnet})
            subs.update({'mask_bits':str(mask)})
            subs.update({'name':name})
            rest.post_subnet(subs)

    def get_infrastructure(self):
        """
        Get locations, rows and racks from RT, convert them to buildings and rooms and send to uploader.
        :return:
        """
        buildings_map   = {}
        rooms_map       = {}
        rows_map        = {}
        racks           = []

        if not self.con:
            self.connect()

        # ============ BUILDINGS AND ROOMS ============
        with self.con:
            cur = self.con.cursor()
            q   = """select id,name, parent_id, parent_name from Location"""
            cur.execute(q)
            raw = cur.fetchall()
        if CHILD_AS_BUILDING:
            for rec in raw:
                building_id, building_name, parent_id, parent_name = rec
                buildings_map.update({building_id:building_name})
        else:
            for rec in raw:
                building_id, building_name, parent_id, parent_name = rec
                if not parent_name:
                    buildings_map.update({building_id:building_name})
                else:
                    rooms_map.update({building_name : parent_name})

        # upload buildings
        if DEBUG:
            msg = ('Buildings',str(buildings_map))
            logger.debugger(msg)
        bdata   = {}
        for bid, building in buildings_map.items():
            bdata.update({'name':building})
            rest.post_building(bdata)

        # upload rooms
        buildings = json.loads((rest.get_buildings()))['buildings']
        if not CHILD_AS_BUILDING:
            for room, parent in rooms_map.items():
                roomdata = {}
                roomdata.update({'name':room})
                roomdata.update({'building':parent})
                rest.post_room(roomdata)

        # ============ ROWS AND RACKS ============
        with self.con:
            cur = self.con.cursor()
            q   = """SELECT id, name ,height, row_id, row_name, location_id, location_name from Rack;"""
            cur.execute(q)
            raw = cur.fetchall()

        for rec in raw:
            rack_id, rack_name, height, row_id, row_name, location_id, location_name = rec

            rows_map.update({row_name:location_name})

            # prepare rack data. We will upload it a little bit later
            rack = {}
            rack.update({'name': rack_name})
            rack.update({'size': height})
            rack.update({'rt_id': rack_id}) # we will remove this later
            if ROW_AS_ROOM:
                rack.update({'room': row_name})
                rack.update({'building': location_name})
            else:
                row_name = row_name[:10] # there is a 10char limit for row name
                rack.update({'row': row_name})
                if location_name in rooms_map:
                    rack.update({'room': location_name})
                    building_name = rooms_map[location_name]
                    rack.update({'building': building_name})
                else:
                    rack.update({'building': location_name})
            racks.append(rack)

        # upload rows as rooms
        if ROW_AS_ROOM:
            if DEBUG:
                msg = ('Rooms',str(rows_map))
                logger.debugger(msg)
            for room, parent in rows_map.items():
                roomdata = {}
                roomdata.update({'name':room})
                roomdata.update({'building':parent})
                rest.post_room(roomdata)

        # upload racks
        if DEBUG:
            msg = ('Racks',str(racks))
            logger.debugger(msg)
        for rack in racks:
            rt_rack_id  = rack['rt_id']
            del rack['rt_id']
            response    = rest.post_rack(rack)
            d42_rack_id = response['msg'][1]

            self.rack_id_map.update({rt_rack_id:d42_rack_id})

    def get_hardware(self):
        """
        Get hardware from RT and send it to uploader
        :return:
        """
        if not self.con:
            self.connect()
        with self.con:
            # get hardware items (except PDU's)
            cur = self.con.cursor()
            q   =   """SELECT
                    Object.id,Object.name as Description, Object.label as Name,
                    Object.asset_no as Asset,Dictionary.dict_value as Type
                    FROM Object
                    LEFT JOIN AttributeValue ON Object.id = AttributeValue.object_id
                    LEFT JOIN Attribute ON AttributeValue.attr_id = Attribute.id
                    LEFT JOIN Dictionary ON Dictionary.dict_key = AttributeValue.uint_value
                    WHERE Attribute.id=2 AND Object.objtype_id != 2
                    """
            cur.execute(q)
        data = cur.fetchall()

        if DEBUG:
            msg = ('Hardware',str(data))
            logger.debugger(msg)

        # create map device_id:height
        # RT does not impose height for devices of the same hardware model so it might happen that -
        # two or more devices based on same HW model have different size in rack
        # here we try to find and set smallest U for device
        hwsize_map  = {}
        for line in data:
            line    = [0 if not x else x for x in line]
            data_id, description, name, asset, dtype = line
            size    = self.get_hardware_size(data_id)
            if size:
                floor,  height,  depth,  mount = size
                if data_id not in hwsize_map:
                    hwsize_map.update({data_id:height})
                else:
                    h = float(hwsize_map[data_id])
                    if float(height) < h:
                        hwsize_map.update({data_id:height})

        for line in data:
            hwddata = {}
            line    = [0 if not x else x for x in line]
            data_id, description, name, asset, dtype = line

            if '%GPASS%' in dtype:
                vendor, model =  dtype.split("%GPASS%")
            elif len(dtype.split()) > 1:
                venmod =  dtype.split()
                vendor = venmod[0]
                model  = ' '.join(venmod[1:])
            else:
                vendor = dtype
                model  = dtype

            size = self.get_hardware_size(data_id)
            if size:
                floor,  height,  depth,  mount = size
                # patching height
                height = hwsize_map[data_id]
                hwddata.update({'notes':description})
                hwddata.update({'type':1})
                hwddata.update({'size':height})
                hwddata.update({'depth':depth})
                hwddata.update({'name':model})
                hwddata.update({'manufacturer':vendor})
                rest.post_hardware(hwddata)

    def get_hardware_size(self, data_id):
        """
        Calculate hardware size.
        :param data_id: hw id
        :return:
            floor   - starting U location for the device in the rack
            height  - height of the device
            depth   - depth of the device (full, half)
            mount   - orientation of the device in the rack. Can be front or back
        """
        if not self.con:
            self.connect()
        with self.con:
            # get hardware items
            cur = self.con.cursor()
            q   = """SELECT unit_no,atom FROM RackSpace WHERE object_id = %s""" % data_id
            cur.execute(q)
        data    = cur.fetchall()
        if data != ():
            front    = 0
            interior = 0
            rear     = 0
            floor    = 0
            depth    =  1 # 1 for full depth (default) and 2 for half depth
            mount    = 'front' # can be [front | rear]
            i = 1

            for line in data:
                flr, tag  = line

                if i == 1:
                    floor = int(flr) -1  # '-1' since RT rack starts at 1 and Device42 starts at 0.
                else:
                    if int(flr) <  floor:
                        floor = int(flr) -1
                i += 1
                if tag == 'front':
                    front += 1
                elif tag == 'interior':
                    interior += 1
                elif tag == 'rear':
                    rear += 1

            if front and interior and rear: # full depth
                height = front
                return  floor,  height,  depth,  mount

            elif front and interior and not rear: #half depth, front mounted
                height = front
                depth  = 2
                return floor,  height,  depth,  mount

            elif interior and rear and not front: # half depth,  rear mounted
                height = rear
                depth  = 2
                mount  = 'rear'
                return floor,  height,  depth,  mount

            # for devices that look like less than half depth:
            elif front and not interior and not rear:
                height = front
                depth  = 2
                return  floor,  height,  depth,  mount
            elif rear and not interior and not front:
                height = rear
                depth  = 2
                return  floor,  height,  depth,  mount
            else:
                return None, None, None, None
        else:
            return None, None, None, None

    @staticmethod
    def add_hardware(height, depth, name):
        """

        :rtype : object
        """
        hwddata = {}
        hwddata.update({'type':1})
        if height:
            hwddata.update({'size':height})
        if depth:
            hwddata.update({'depth':depth})
        if name:
            hwddata.update({'name':name})
            rest.post_hardware(hwddata)

    def get_vmhosts(self):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q   = """SELECT O.id, O.name,
                    (SELECT O_C.id
                    FROM EntityLink EL
                    LEFT JOIN Object O_C ON EL.parent_entity_id = O_C.id
                    WHERE EL.child_entity_id = O.id
                    AND EL.parent_entity_type = 'object'
                    AND EL.child_entity_type = 'object'
                    AND O_C.objtype_id = 1505 LIMIT 1) AS cluster_id,
                    (SELECT O_C.name
                    FROM EntityLink EL
                    LEFT JOIN Object O_C ON EL.parent_entity_id = O_C.id
                    WHERE EL.child_entity_id = O.id
                    AND EL.parent_entity_type = 'object'
                    AND EL.child_entity_type = 'object'
                    AND O_C.objtype_id = 1505 LIMIT 1) AS cluster_name,
                    (SELECT COUNT(*) FROM EntityLink EL
                    LEFT JOIN Object O_VM ON EL.child_entity_id = O_VM.id
                    WHERE EL.parent_entity_type = 'object'
                    AND EL.child_entity_type = 'object'
                    AND EL.parent_entity_id = O.id
                    AND O_VM.objtype_id = 1504) AS VMs
                    FROM Object O
                    LEFT JOIN AttributeValue AV ON O.id = AV.object_id
                    WHERE O.objtype_id = 4
                    AND AV.attr_id = 26
                    AND AV.uint_value = 1501
                    ORDER BY O.name"""
            cur.execute(q)
            raw = cur.fetchall()

        dev = {}
        for rec in raw:
            host_id = int(rec[0])
            name    = rec[1].strip()
            self.vm_hosts.update({host_id:name})
            dev.update({'name':name})
            dev.update({'is_it_virtual_host': 'yes'})
        rest.post_device(dev)

    def get_container_map(self):
        """
        Which VM goes into which VM host?
        :return:
        """
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = """SELECT parent_entity_id AS container_id ,child_entity_id AS object_id
                    FROM EntityLink WHERE child_entity_type='object' AND parent_entity_type = 'object'"""
            cur.execute(q)
            raw = cur.fetchall()
        for rec in raw:
            container_id, object_id = rec
            self.container_map.update({object_id:container_id})

    def get_devices(self):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            # get object IDs
            q = 'SELECT id FROM Object'
            cur.execute(q)
            idsx = cur.fetchall()
        ids = [x[0] for x in idsx]

        with self.con:
            for dev_id in ids:
                q = """Select
                            Object.objtype_id,
                            Object.name as Description, 
                            Object.label as Name, 
                            Object.asset_no as Asset, 
                            Attribute.name as Name,Dictionary.dict_value as Type,
                            Object.comment as Comment,
                            RackSpace.rack_id as RackID,
                            Rack.name as rack_name,
                            Rack.row_name,
                            Rack.location_id,
                            Rack.location_name,
                            Location.parent_name

                            FROM Object
                            LEFT JOIN AttributeValue ON Object.id = AttributeValue.object_id 
                            LEFT JOIN Attribute ON AttributeValue.attr_id = Attribute.id
                            LEFT JOIN Dictionary ON Dictionary.dict_key = AttributeValue.uint_value
                            LEFT JOIN RackSpace ON Object.id = RackSpace.object_id
                            LEFT JOIN Rack ON RackSpace.rack_id = Rack.id
                            LEFT JOIN Location ON Rack.location_id = Location.id
                            WHERE Object.id = %s
                            AND Object.objtype_id not in (1560,1561,1562,50275)""" % dev_id
                        
                cur.execute(q)
                data = cur.fetchall()
                if data: # RT objects that do not have data are locations, racks, rows etc...
                    self.process_data(data, dev_id)

    def process_data(self, data, dev_id):
        devicedata  = {}
        device2rack = {}
        name        = None
        opsys       = None
        hardware    = None
        note        = None
        rrack_id    = None
        floor       = None
        dev_type    = 0

        for x in data:
            dev_type,  rdesc, rname,  rasset, rattr_name,  rtype, \
            rcomment, rrack_id, rrack_name, rrow_name, \
            rlocation_id, rlocation_name,  rparent_name = x
            
            name    = x[1]
            note    = x[-7]
  
            if 'Operating System' in x:
                opsys  = x[-8]
                if '%GSKIP%' in opsys:
                    opsys = opsys.replace('%GSKIP%', ' ')
                if '%GPASS%' in opsys:
                    opsys = opsys.replace('%GPASS%', ' ')
            if 'SW type' in x:
                opsys  = x[-8]
                if '%GSKIP%' in opsys:
                    opsys = opsys.replace('%GSKIP%', ' ')
                if '%GPASS%' in opsys:
                    opsys = opsys.replace('%GPASS%', ' ')
            
            if 'Server Hardware' in x:
                hardware = x[-8]
                if '%GSKIP%' in hardware:
                    hardware = hardware.replace('%GSKIP%', ' ')
                if '%GPASS%' in hardware:
                    hardware = hardware.replace('%GPASS%', ' ')
                if '\t' in hardware:
                    hardware = hardware.replace('\t', ' ')
                    
            if 'HW type' in x:
                hardware = x[-8]
                if '%GSKIP%' in hardware:
                    hardware = hardware.replace('%GSKIP%', ' ')
                if '%GPASS%' in hardware:
                    hardware = hardware.replace('%GPASS%', ' ')
                if '\t' in hardware:
                    hardware = hardware.replace('\t', ' ')
            if note:
                note = note.replace('\n', ' ')
                if '&lt;' in note:
                    note = note.replace('&lt;', '')
                if '&gt;' in note:
                    note = note.replace('&gt;', '')
            
        if name:
            # set device data
            devicedata.update({'name':name})
            if hardware:
                devicedata.update({'hardware':hardware})
            if opsys:
                devicedata.update({'os':opsys})
            if note:
                devicedata.update({'notes':note})
            if dev_id in self.vm_hosts:
                devicedata.update({'is_it_virtual_host':'yes'})
            if dev_type == 8:
                devicedata.update({'is_it_switch':'yes'})
            elif dev_type == 1504:
                devicedata.update({'type':'virtual'})
                try:
                    vm_host_id = self.container_map[dev_id]
                    vm_host_name = self.vm_hosts[vm_host_id]
                    devicedata.update({'virtual_host':vm_host_name})
                except KeyError:
                    pass

            d42_rack_id = None

            if rrack_id: # rrack_id is RT rack id
                d42_rack_id = self.rack_id_map[rrack_id]

            # if the device is mounted in RT, we will try to add it to D42 hardwares.
            floor,  height,  depth,  mount = self.get_hardware_size(dev_id)
            if floor is not None:
                floor = int(floor) + 1
            if not hardware:
                hardware ='generic'+str(height)+'U'
            self.add_hardware(height, depth, hardware)


                
            # upload device
            if devicedata:
                if hardware:
                    devicedata.update({'hardware':hardware})
                rest.post_device(devicedata)

                # if there is a device, we can try to mount it to the rack
                if d42_rack_id and floor: #rack_id is D42 rack id
                    device2rack.update({'device':name})
                    if hardware:
                        device2rack.update({'hw_model':hardware})
                    device2rack.update({'rack_id':d42_rack_id})
                    device2rack.update({'start_at':int(floor)})
                    rest.post_device2rack(device2rack)
                else:
                    if not floor and dev_type != 1504:
                        msg = '\n-----------------------------------------------------------------------\
                        \n[!] INFO: Cannot mount device "%s" (RT id = %d) to the rack.\
                        \n\tFloor returned from "get_hardware_size" function was: %s' % (name, dev_id,str(floor))
                        logger.writer(msg)
            else:
                msg = '\n-----------------------------------------------------------------------\
                \n[!] INFO: Device %s (RT id = %d) cannot be uploaded. Data was: %s' % (name, dev_id, str(devicedata))
                logger.writer(msg)

        else:
            # device has no name thus it cannot be migrated
            msg = '\n-----------------------------------------------------------------------\
            \n[!] INFO: Device with RT id=%d cannot be migrated because it has no name.' % dev_id
            logger.writer(msg)

    def get_device_to_ip(self):
        if not self.con:
            self.connect()
        with self.con:
            # get hardware items (except PDU's)
            cur = self.con.cursor()
            q   = """SELECT
                    IPv4Allocation.ip,IPv4Allocation.name,
                    Object.name as hostname
                    FROM %s.`IPv4Allocation`
                    LEFT JOIN Object ON Object.id = object_id""" % DB_NAME
            cur.execute(q)
        data = cur.fetchall()

        if DEBUG:
            msg = ('Device to IP',str(data))
            logger.debugger(msg)

        for line in data:
            devmap = {}
            rawip, nic_name, hostname = line
            ip = self.convert_ip(rawip)
            devmap.update({'ipaddress':ip})
            devmap.update({'device':hostname})
            if nic_name:
                devmap.update({'tag':nic_name})
            rest.post_ip(devmap)

    def get_pdus(self):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q   = """SELECT
                    Object.id,Object.name as Description, Object.label as Name, Object.asset_no as Asset, 
                    Object.comment as Comment,Dictionary.dict_value as Type, RackSpace.atom as Position, 
                    (SELECT Object.id FROM Object WHERE Object.id = RackSpace.rack_id) as RackID
                    FROM Object
                    LEFT JOIN AttributeValue ON Object.id = AttributeValue.object_id 
                    LEFT JOIN Attribute ON AttributeValue.attr_id = Attribute.id
                    LEFT JOIN Dictionary ON Dictionary.dict_key = AttributeValue.uint_value
                    LEFT JOIN RackSpace ON RackSpace.object_id = Object.id
                    WHERE Object.objtype_id = 2  
                  """
            cur.execute(q)
        data = cur.fetchall()

        if DEBUG:
            msg = ('PDUs',str(data))
            logger.debugger(msg)

        rack_mounted    = []
        pdumap          = {}
        pdumodels       = []
        pdu_rack_models = []

        for line in data:
            pdumodel    = {}
            pdudata     = {}
            line        = ['' if not x else x for x in line]
            pdu_id, description, name, asset, comment, pdu_type, position, rack_id = line

            if '%GPASS%' in pdu_type:
                pdu_type = pdu_type.replace('%GPASS%', ' ')
            pdudata.update({'name':name})
            pdudata.update({'notes':comment})
            pdudata.update({'pdu_model':pdu_type})
            pdumodel.update({'name':pdu_type})
            pdumodel.update({'pdu_model':pdu_type})
            if rack_id:
                floor,  height,  depth,  mount = self.get_hardware_size(pdu_id)
                pdumodel.update({'size':height})
                pdumodel.update({'depth':depth})

            # post pdu models
            if pdu_type and name not in pdumodels:
                rest.post_pdu_model(pdumodel)
                pdumodels.append(pdumodel)
            elif pdu_type and rack_id:
                if pdu_id not in pdu_rack_models:
                    rest.post_pdu_model(pdumodel)
                    pdu_rack_models.append(pdu_id)

            # post pdus
            if pdu_id not in pdumap:
                response = rest.post_pdu(pdudata)
                d42_pdu_id = response['msg'][1]
                pdumap.update({pdu_id:d42_pdu_id})

            # mount to rack
            if position:
                if pdu_id not in rack_mounted:
                    rack_mounted.append(pdu_id)
                    floor,  height,  depth,  mount = self.get_hardware_size(pdu_id)
                    floor = int(floor) + 1
                    d42_rack_id = self.rack_id_map[rack_id]
                    if floor:
                        rdata = {}
                        rdata.update({'pdu_id':pdumap[pdu_id]})
                        rdata.update({'rack_id':d42_rack_id})
                        rdata.update({'pdu_model':pdu_type})
                        rdata.update({'where':'mounted'})
                        rdata.update({'start_at':floor})
                        rdata.update({'orientation':mount})
                        rest.post_pdu_to_rack(rdata,d42_rack_id)
            # It's Zero-U then
            else:
                rack_id = self.get_rack_id_for_zero_Us(pdu_id)
                if rack_id:
                    d42_rack_id = self.rack_id_map[rack_id]
                    if PDU_MOUNT.lower() in ('left', 'right', 'above', 'below'):
                        where  = PDU_MOUNT.lower()
                    else:
                        where = 'left'
                    if PDU_ORIENTATION.lower() in ('front', 'back'):
                        mount = PDU_ORIENTATION.lower()
                    else:
                        mount = 'front'
                    rdata = {}

                    rdata.update({'pdu_id':pdumap[pdu_id]})
                    rdata.update({'rack_id':d42_rack_id})
                    rdata.update({'pdu_model':pdu_type})
                    rdata.update({'where':where})
                    rdata.update({'orientation':mount})
                    rest.post_pdu_to_rack(rdata,d42_rack_id)

    def get_rack_id_for_zero_Us(self,pdu_id):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q   = """SELECT
                    EntityLink.parent_entity_id
                    FROM EntityLink
                    WHERE EntityLink.child_entity_id = %s
                    AND EntityLink.parent_entity_type = 'rack'""" % pdu_id
            cur.execute(q)
        data = cur.fetchone()
        if data:
            return data[0]



def main():
    db = DB()
    #db.get_subnets()
    #db.get_ips()
    db.get_infrastructure()
    db.get_hardware()
    db.get_container_map()
    db.get_vmhosts()
    db.get_devices()
    db.get_device_to_ip()
    db.get_pdus()




if __name__ == '__main__':
    logger = Logger(LOGFILE, STDOUT)
    rest = REST()
    main()
    print '\n[!] Done!'
    sys.exit()


