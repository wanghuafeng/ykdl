#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ykdl.util.html import get_content, add_header
from ykdl.util.match import match1, matchall
from ykdl.extractor import VideoExtractor
from ykdl.videoinfo import VideoInfo
from ykdl.compact import urlencode

from .util import get_h5enc, ub98484234

import time
import json
import uuid
import traceback
import random
import requests
import string


douyu_match_pattern = [ 'class="hroom_id" value="([^"]+)',
                        'data-room_id="([^"]+)'
                      ]

class Douyutv(VideoExtractor):
    name = u'斗鱼直播 (DouyuTV)'

    stream_ids = ['BD10M', 'BD8M', 'BD4M', 'BD', 'TD', 'HD', 'SD']
    profile_2_id = {
        u'蓝光10M': 'BD10M',
        u'蓝光8M': 'BD8M',
        u'蓝光4M': 'BD4M',
        u'蓝光': 'BD',
        u'超清': 'TD',
        u'高清': 'HD',
        u'流畅': 'SD'
     }

    def purchase(self, room_id, gift_id, headers):
        data = {
            'giftId': gift_id,
            'giftCount': '1',
            'roomId': room_id,
            'bizExt': '{"yzxq":{}}',
        }

        purchase_api = 'https://www.douyu.com/japi/gift/donate/mainsite/v1'
        response = requests.post(purchase_api, headers = headers, data = data, timeout = 20, verify = False)
        print "Purchase Result:", response.text

        #Success
        '''
        {
            "error": 0,
            "msg": "success",
            "data": {
                "priceType": 2,
                "sb": 300,
                "noble_gold": 0,
                "ry": 0,
                "noble_gold_black": 0,
                "gid": 20595,
                "gx": 30,
                "num": 1,
                "messages": ["type@=dgb/rid@=673305/gfid@=20595/gs@=0/uid@=331816442/nn@=娉＄繀/ic@=avatar_v3@S201910@Sf3ed359595964ea59d146cf01349cf53/eid@=0/eic@=20053/level@=5/dw@=0/gfcnt@=1/hits@=1/bcnt@=1/bst@=3/ct@=0/el@=/cm@=0/bnn@=/bl@=0/brid@=0/hc@=/sahf@=0/fc@=0/bnid@=1/bnl@=1/"]
            }
        }
        '''

    def prepare(self):
        info = VideoInfo(self.name, True)
        add_header("Referer", 'https://www.douyu.com')

        html = get_content(self.url)
        self.vid = match1(html, '\$ROOM\.room_id\s*=\s*(\d+)',
                                'room_id\s*=\s*(\d+)',
                                '"room_id.?":(\d+)',
                                'data-onlineid=(\d+)')
        title = match1(html, 'Title-headlineH2">([^<]+)<')
        artist = match1(html, 'Title-anchorName" title="([^"]+)"')

        if not title or not artist:
            html = get_content('https://open.douyucdn.cn/api/RoomApi/room/' + self.vid)
            room_data = json.loads(html)
            if room_data['error'] == 0:
                room_data = room_data['data']
                title = room_data['room_name']
                artist = room_data['owner_name']

        info.title = u'{} - {}'.format(title, artist)
        info.artist = artist

        js_enc = get_h5enc(html, self.vid)
        params = {
            'cdn': '',
            'iar': 0,
            'ive': 0
        }
        ub98484234(js_enc, self, params)
        
        #My Start Here
        params['rate'] = 0
        data = urlencode(params)
        if not isinstance(data, bytes):
            data = data.encode()
        html_content = get_content('https://www.douyu.com/lapi/live/getH5Play/{}'.format(self.vid), data=data)
        live_data = json.loads(html_content)
        if live_data['error']:
            return live_data['msg']
        
        cdns = []
        for i in live_data['data']['cdnsWithName']:
            cdns.append(i['cdn'])
                
        best_rate = -1
        max_bit = 0
        for i in live_data['data']['multirates']:
            if i['bit'] > max_bit:
                max_bit = i['bit']
                best_rate = i['rate']
        assert best_rate != -1

        def get_live_info(rate, cdn):
            #print "get_live_info rate:", rate, " cdn:", cdn
            params['rate'] = rate
            params['cdn'] = cdn
            data = urlencode(params)
            if not isinstance(data, bytes):
                data = data.encode()
            html_content = get_content('https://www.douyu.com/lapi/live/getH5Play/{}'.format(self.vid), data=data)
            self.logger.debug(html_content)

            live_data = json.loads(html_content)
            if self.vid == '673305':
                print "live_data:", live_data
            if live_data['error']:
                return live_data['msg']

            live_data = live_data["data"]
            rate_2_profile = dict((rate['rate'], rate['name']) for rate in live_data['multirates'])
            video_profile = rate_2_profile[live_data['rate']]
            stream = self.profile_2_id[video_profile]
            if stream in info.streams:
                return
            
            #如果需要票,live_data['rtmp_live']则为空
            #检测到需要门票,就登录并重新获取url
            if not live_data['rtmp_live'] and live_data['eticket'] is not None:
                acf_auth = 'da40xtE8psQrUbKp6AkzPLMI%2BGLzngC849FtSiXl2vbWgayaE%2FjGFSI6etbcBYO1MCa82A%2BiWiUa%2FBv8itB15X9%2FXnaOAInELIGsaO3Gr%2FCjLIh%2BPQz3Pds'
                headers = {
                    'Connection': 'keep-alive',
                    'Accept': 'application/json, text/plain, */*',
                    'Origin': 'https://www.douyu.com',
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36',
                    'Sec-Fetch-Mode': 'cors',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Sec-Fetch-Site': 'same-origin',
                    'Accept-Encoding': 'gzip, deflate',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                    'Referer': 'https://www.douyu.com/{}'.format(self.vid),
                    'Cookie': "dy_did={};  acf_auth={};".format(params['did'], acf_auth)
                    }

                data = {
                    'v': params['v'],
                    'did': params['did'],
                    'tt': int(time.time()),
                    'sign': params['sign'],
                    'cdn': '',
                    'rate': rate,
                    'ver': 'Douyu_219110105',
                    'iar': '1',
                    }
                '''
                data = urlencode(data)
                if not isinstance(data, bytes):
                    data = data.encode()
                '''
                try:
                    response = requests.post('https://www.douyu.com/gapi/live/ticket/getH5Play/{}'.format(self.vid), headers = headers, data = data, timeout = 20, verify = False)
                    if self.vid == '673305':
                        print "Ticket content:", response.text    
                    response.raise_for_status()
                    live_data = json.loads(response.content)
                    if live_data['error']:
                        return live_data['msg']
                    live_data = live_data["data"]
                    payment_mode = live_data['payment_mode']
                    is_trail = live_data['is_trail']
                    gift_id = live_data['gift_id']
                    if payment_mode == -1:
                        print "Should perchase"
                        self.purchase(self.vid, gift_id, headers)
                except Exception as exception:
                    print traceback.format_exc()
            
            if live_data['rtmp_live']:
                real_url = '{}/{}'.format(live_data['rtmp_url'], live_data['rtmp_live'])
                info.stream_types.append(stream)
                info.streams[stream] = {
                    'container': 'flv',
                    'video_profile': video_profile,
                    'src' : [real_url],
                    'size': float('inf')
                }
            else:
                print self.vid, "can not retrieve live url"

            '''
            error_msges = []
            if rate == 0:
                rate_2_profile.pop(0, None)
                rate_2_profile.pop(live_data['rate'], None)
                for rate in rate_2_profile:
                    error_msg = get_live_info(rate)
                    if error_msg:
                        error_msges.append(error_msg)
            if error_msges:
                return ', '.join(error_msges)
            '''

        error_msg = get_live_info(best_rate, random.choice(cdns))
        #assert len(info.stream_types), error_msg
        info.stream_types = sorted(info.stream_types, key=self.stream_ids.index)
        return info

    def prepare_list(self):

        html = get_content(self.url)
        return matchall(html, douyu_match_pattern)

site = Douyutv()
