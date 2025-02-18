#!/usr/bin/python
# -*- coding: utf-8 -*-

from base64 import b64decode
from json import loads, dumps
from re import search, findall
from os import environ
from hashlib import sha1
from math import floor
from sys import exit
from datetime import datetime, timedelta
from resources.lib.const import CONST
import resources.lib.compat as compat
import resources.lib.request_helper as request_helper
import resources.lib.cache as cache
import resources.lib.xbmc_helper as xbmc_helper
from resources.lib.mpd_parser import mpd_parser as mpd_parser

if compat.PY2:
	from urllib import urlencode
	from urlparse import urlparse, urlunparse , parse_qs
elif compat.PY3:
	from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

class lib_joyn:


	def __init__(self, default_icon):

		self.config = lib_joyn.get_config(default_icon)
		self.default_icon = default_icon


	def get_joyn_json_response(self, url, headers=None, params=None):

		if headers is not None:
				headers.append(('key', self.config['CONFIG']['header_7TV_key']))
		else:
			headers = [('key', self.config['CONFIG']['header_7TV_key'])]

		decoded_json = request_helper.get_json_response(url, self.	config, headers, params)

		if decoded_json[compat._unicode('status')] == 200:
			return decoded_json[compat._unicode('response')]
		else:
			return None


	def build_signature(self, video_id, encoded_client_data, entitlement_token):

		sha_input = video_id + ','
		sha_input += entitlement_token + ','
		sha_input += encoded_client_data

		for char in findall('.',self.config['PSF_VARS'][CONST['PSF_VARS_IDX']['SECRET']]):
			sha_input += hex(ord(char))[2:]

		sha_1 = sha1()
		sha_1.update(sha_input.encode('utf-8'))
		sha_output = sha_1.hexdigest()

		return sha_output


	def get_json_by_type(self, path_type, replacements={}, additional_params={}, url_annex=''):

		valued_query_params = {}

		if 'search' not in additional_params.keys():
			for key, value in CONST['PATH'][path_type]['QUERY_PARAMS'].items():
				if search('^##(.)+##$', value) is not None:
					key = value[2:-2]
					if (key in replacements.keys()):
						value = replacements[key]
				valued_query_params.update({key : value})

		valued_query_params.update({'selection' : CONST['PATH'][path_type]['SELECTION']})
		valued_query_params.update(additional_params)

		return self.get_joyn_json_response(url=CONST['MIDDLEWARE_URL'] + CONST['PATH'][path_type]['PATH'] + url_annex , params=valued_query_params)


	def set_mpd_props(self, list_item, url, stream_type='VOD'):

		xbmc_helper.log_debug('get_mpd_path : ' + url + 'stream_type: ' + stream_type)
		mpdparser = None

		##strip out the filter parameter
		parts = urlparse(url)
		query_dict = parse_qs(parts.query)

		if 'filter' in query_dict.keys():
			query_dict.update({'filter' : ''})
			new_parts = list(parts)
			new_parts[4] = urlencode(query_dict)
			new_mpd_url = urlunparse(new_parts)
			xbmc_helper.log_debug('Stripped out filter from mpd url is ' + new_mpd_url)
			try:
				mpdparser = mpd_parser(new_mpd_url,self. config)
			except Exception as e:
				xbmc_helper.log_debug('Invalid MPD - Exception: ' + str(e))
				pass

		if mpdparser is None or mpdparser.mpd_tree is None:
			try:
				mpdparser = mpd_parser(url, self.config)
			except Exception as e:
				xbmc_helper.log_error('Invalid Orginal MPD - Exception: ' + str(e))

		if mpdparser is not None and mpdparser.mpd_tree is not None:

			list_item.setProperty('inputstreamaddon', CONST['INPUTSTREAM_ADDON'])
			list_item.setProperty(CONST['INPUTSTREAM_ADDON'] + '.manifest_type', 'mpd')

			if stream_type == 'LIVE':
				list_item.setProperty(CONST['INPUTSTREAM_ADDON'] + '.manifest_update_parameter', 'full')

			toplevel_base_url = None

			# the mpd has a Base URL at toplevel at a remote location
			# inputstream adaptive currently can't handle this correctly
			# it's known that this Base URL can be used to retrieve a 'better' mpd
			toplevel_base_url_res = mpdparser.get_toplevel_base_url()
			if toplevel_base_url_res is not None and toplevel_base_url_res.startswith('http'):
				xbmc_helper.log_debug('Found MPD with Base URL at toplevel : ' + toplevel_base_url_res)
				toplevel_base_url =  toplevel_base_url_res

			if toplevel_base_url is not None :
				if stream_type == 'VOD':
					new_mpd_url = toplevel_base_url + '.mpd?filter='
					try :
						test_mpdparser = mpd_parser(new_mpd_url, self.config);
						if test_mpdparser.mpd_tree is not None:
							mpdparser = test_mpdparser
							toplevel_base_url = None
							toplevel_base_url_res = mpdparser.get_toplevel_base_url()
							if toplevel_base_url_res is not None and toplevel_base_url_res.startswith('http'):
								xbmc_helper.log_debug('Found MPD with Base URL at toplevel in REPLACED url: ' + toplevel_base_url_res + 'URL: ' + new_mpd_url)
								toplevel_base_url =  toplevel_base_url_res
							else:
								toplevel_base_url = None
					except Exception as e:
						xbmc_helper.log_debug('Invalid MPD - Exception: ' + str(e))
						pass

				elif stream_type == 'LIVE':
					period_base_url_res = mpdparser.query_node_value(['Period','BaseURL']);
					if period_base_url_res is not None and period_base_url_res.startswith('/') and period_base_url_res.endswith('/'):
						new_mpd_url = toplevel_base_url + period_base_url_res + 'cenc-default.mpd'

						try :
							test_mpdparser = mpd_parser(new_mpd_url, self.config);
							if test_mpdparser.mpd_tree is not None:
								mpdparser = test_mpdparser
								toplevel_base_url = None
								toplevel_base_url_res = mpdparser.get_toplevel_base_url()
								if toplevel_base_url_res is not None and toplevel_base_url_res.startswith('http'):
									xbmc_helper.log_debug('Found MPD with Base URL at toplevel in REPLACED url: ' + toplevel_base_url_res + 'URL: ' + new_mpd_url)
									toplevel_base_url =  toplevel_base_url_res
								else:
									toplevel_base_url = None
						except Exception as e:
							xbmc_helper.log_debug('Invalid MPD - Exception: ' + str(e))
							pass

			if toplevel_base_url is not None :
				xbmc_helper.log_debug('Writing MPD file to local disc, since it has a remote top Level Base URL ...')
				sha_1 = sha1()
				sha_1.update(mpdparser.mpd_url)

				mpd_filepath = xbmc_helper.get_file_path(CONST['TEMP_DIR'],  sha_1.hexdigest() + '.mpd')
				with open (mpd_filepath, 'w') as mpd_filepath_out:
					mpd_filepath_out.write(mpdparser.mpd_contents)

				xbmc_helper.log_debug('Local MPD filepath is: ' + mpd_filepath)
				list_item.setPath(mpd_filepath)

			else:
				list_item.setPath( mpdparser.mpd_url + '|' + request_helper.get_header_string({'User-Agent' : self.config['USER_AGENT']}))

			return True

		return False


	def get_entitlement_data(self, video_id, stream_type):

		entitlement_request_data = {
			'access_id' 	: self.config['PSF_CLIENT_CONFIG']['accessId'],
			'content_id' 	: video_id,
			'content_type'	: stream_type,
		}
		entitlement_request_headers = [('x-api-key', self.config['PSF_CONFIG']['default'][stream_type.lower()]['apiGatewayKey'])]

		return request_helper.post_json(self.config['PSF_CONFIG']['default'][stream_type.lower()]['entitlementBaseUrl'] + CONST['ENTITLEMENT_URL'],
					self.config, entitlement_request_data, entitlement_request_headers)


	def get_video_data(self, video_id, stream_type):

		video_url = self.config['PSF_CONFIG']['default'][stream_type.lower()]['playoutBaseUrl']

		client_data = self.get_client_data(video_id, stream_type)
		if stream_type == 'VOD':
			video_url += 'playout/video/' + client_data['videoId']

		elif stream_type == 'LIVE':
			video_url += 'playout/channel/' + client_data['channelId']

		entitlement_data = self.get_entitlement_data(video_id, stream_type)

		encoded_client_data = request_helper.base64_encode_urlsafe(dumps(client_data))
		signature = self.build_signature(video_id, encoded_client_data, entitlement_data['entitlement_token'])

		video_url_params = {
			'entitlement_token'	: entitlement_data['entitlement_token'],
			'clientData'		: encoded_client_data,
			'sig'			: signature,
		}

		video_url += '?' + urlencode(video_url_params)

		return request_helper.get_json_response(url=video_url, config=self.config, headers=[('Content-Type', 'application/x-www-form-urlencoded charset=utf-8')], post_data='false')


	def get_client_data(self, video_id, stream_type):

		client_data = {}
		if stream_type == 'VOD':
			video_metadata = self.get_joyn_json_response(CONST['MIDDLEWARE_URL'] + 'metadata/video/' + video_id)

			client_data.update({
					'startTime' 	: '0',
					'videoId' 	: video_metadata['tracking']['id'],
					'duration'	: video_metadata['tracking']['duration'],
					'brand'		: video_metadata['tracking']['channel'],
					'genre'		: video_metadata['tracking']['genres'],
					'tvshowid'	: video_metadata['tracking']['tvShow']['id'],
			})

			if 'agofCode' in video_metadata['tracking']:
				client_data.update({'agofCode' : video_metadata['tracking']['agofCode']})

		elif stream_type == 'LIVE':
			client_data.update({
					'videoId' 	: None,
					'channelId'	: video_id,

			})

		return client_data


	def get_epg(self):

		epg = {}
		raw_epg = self.get_json_by_type('EPG',{
				'from' : (datetime.now() - timedelta(hours=CONST['EPG']['REQUEST_OFFSET_HOURS'])).strftime('%Y-%m-%d %H:%M:00'),
				'to': (datetime.now() + timedelta(hours=CONST['EPG']['REQUEST_HOURS'])).strftime('%Y-%m-%d %H:%M:00')}
			);

		for raw_epg_data in raw_epg['data']:
			raw_epg_data['channelId'] = str(raw_epg_data['channelId'])
			if raw_epg_data['channelId'] not in epg.keys():
				epg.update({raw_epg_data['channelId'] : []})
			epg[raw_epg_data['channelId']].append(raw_epg_data);

		return epg


	@staticmethod
	def extract_metadata(metadata, selection_type):
		extracted_metadata = {
			'art': {},
			'infoLabels' : {},
		};

		path = CONST['PATH'][selection_type]

		if 'descriptions' in metadata.keys() and 'description' in path['TEXTS'].keys():
			for description in metadata['descriptions']:
				if description['type'] == path['TEXTS']['description']:
					extracted_metadata['infoLabels'].update({'Plot' : description['text']})
					break
		if 'titles' in metadata.keys() and 'title' in path['TEXTS'].keys():
			for title in metadata['titles']:
				if title['type'] ==  path['TEXTS']['title']:
					extracted_metadata['infoLabels'].update({'Title' : title['text']})
					break
		if 'images' in metadata.keys() and 'ART' in path.keys():
			for image in metadata['images']:
				if image['type'] in path['ART'].keys():
					for art_type, img_profile in path['ART'][image['type']].items():
						extracted_metadata['art'].update({art_type : image['url'] + '/' + img_profile})

		return extracted_metadata


	@staticmethod
	def extract_metadata_from_epg(epg_channel_data):
		extracted_metadata = {
			'art': {},
			'infoLabels' : {},
		};


		for idx, program_data in enumerate(epg_channel_data):
			endTime = datetime.fromtimestamp(program_data['endTime'])
			if  endTime > datetime.now():
				extracted_metadata['infoLabels']['Title'] = compat._unicode(CONST['TEXT_TEMPLATES']['LIVETV_TITLE']).format(
											program_data['tvChannelName'], program_data['tvShow']['title'])

				if len(epg_channel_data) > (idx+2):
					extracted_metadata['infoLabels']['Plot'] = compat._unicode(CONST['TEXT_TEMPLATES']['LIVETV_UNTIL_AND_NEXT']).format(
											endTime,epg_channel_data[idx+1]['tvShow']['title'])
				else:
					extracted_metadata['infoLabels']['Plot'] = compat._unicode(CONST['TEXT_TEMPLATES']['LIVETV_UNTIL']).format(endTime)

				if program_data['description'] is not None:
					extracted_metadata['infoLabels']['Plot'] += program_data['description']

				for image in program_data['images']:
					if image['subType'] == 'cover':
						extracted_metadata['art']['poster'] = image['url'] + '/' + CONST['PATH']['EPG']['IMG_PROFILE']
				break

		return extracted_metadata;


	@staticmethod
	def get_config(default_icon):

		recreate_config = True
		config = {}
		cached_config = None

		expire_config_mins = xbmc_helper.get_int_setting('configcachemins')
		if expire_config_mins is not None:
			confg_cache_res = cache.get_json('CONFIG', (expire_config_mins * 60))
		else:
			confg_cache_res = cache.get_json('CONFIG')

		if confg_cache_res['data'] is not None:
			cached_config =  confg_cache_res['data']

		if confg_cache_res['is_expired'] is False:
			recreate_config = False;
			config = cached_config;

		if recreate_config == True:
			xbmc_helper.log_debug('get_config(): create config')
			config = {
				'CONFIG'		: {
								'header_7TV_key_web': None,
								'header_7TV_key': None,
								'SevenTV_player_config_url': None
							  },
				'PLAYER_CONFIG'		: {},
				'PSF_CONFIG' 		: {},
				'PSF_VARS'		: {},
				'PSF_CLIENT_CONFIG'	: {},
				'IS_ANDROID'		: False,

			}

			os_uname = compat._uname_list()
			#android
			if os_uname[0] == 'Linux' and 'KODI_ANDROID_LIBS' in environ:
				config['USER_AGENT'] = 'Mozilla/5.0 (Linux Android 8.1.0 Nexus 6P Build/OPM6.171019.030.B1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.91 Mobile Safari/537.36'
				config['IS_ANDROID'] = True
			# linux on arm uses widevine from chromeos
			elif os_uname[0] == 'Linux' and os_uname[4].lower().find('arm') is not -1:
				config['USER_AGENT'] = 'Mozilla/5.0 (X11 CrOS '+  os_uname[4] + ' 4537.56.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.38 Safari/537.36'
			elif os_uname[0] == 'Linux':
				config['USER_AGENT'] = 'Mozilla/5.0 (X11 Linux ' + os_uname[4] + ') AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
			else:
				config['USER_AGENT'] = 'Mozilla/5.0 (Windows NT 10.0 Win64 x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36'

			html_content = request_helper.get_url(CONST['BASE_URL'], config);
			for match in findall('<script type="text/javascript" src="(.*?)"></script>', html_content):
				if match.find('/main') is not -1:
					main_js =  request_helper.get_url(CONST['BASE_URL'] + match, config)
					for key in config['CONFIG']:
						find_str = key + ':"'
						start = main_js.find(find_str)
						length = main_js[start:].find('",')
						config['CONFIG'][key] = main_js[(start+len(find_str)):(start+length)]


			config['PLAYER_CONFIG'] = request_helper.get_json_response(url=config['CONFIG']['SevenTV_player_config_url'], config=config)

			config['PSF_CONFIG'] =  request_helper.get_json_response(url=CONST['PSF_CONFIG_URL'], config=config)

			psf_vars = request_helper.get_url(CONST['PSF_URL'], config)
			find_str = 'call(this,['
			start = psf_vars.find(find_str + '"exports')
			length = psf_vars[start:].rfind('])')
			psf_vars = psf_vars[(start+len(find_str)):(start+length)].split(',')
			for i in range(len(psf_vars)):
				psf_vars[i] = psf_vars[i][1:-1]
			config['PSF_VARS'] = psf_vars

			if (cached_config is not None and
			    cached_config['PSF_VARS'][CONST['PSF_VARS_IDX']['SECRET']] == config['PSF_VARS'][CONST['PSF_VARS_IDX']['SECRET']] and
			    cached_config['PLAYER_CONFIG']['toolkit']['psf'] == config['PLAYER_CONFIG']['toolkit']['psf']):
				config['PSF_CLIENT_CONFIG'] = cached_config['PSF_CLIENT_CONFIG']
			else:
				try:
					config['PSF_CLIENT_CONFIG'] = loads(
									compat._decode(
										b64decode(
											lib_joyn.decrypt(
												lib_joyn.uc_string_to_long_array(config['PSF_VARS'][CONST['PSF_VARS_IDX']['SECRET']]),
												lib_joyn.uc_string_to_long_array(
													lib_joyn.uc_slices_to_string(
														lib_joyn.uc_slice(config['PLAYER_CONFIG']['toolkit']['psf'])
													)
												)
											)
										)
									)
								)

				except Exception as e:
					xbmc_helper.notification('Fehler', 'Konfiguration konnte nicht entschlüsselt werden.', default_icon)
					xbmc_helper.log_error('Could not decrypt config: ' + str(e))
					exit(0)

			cache.set_json('CONFIG', config)

		return config


	@staticmethod
	def decrypt(key, value):
		n = len(value) - 1
		z = value[n - 1]
		y = value[0]

		mx = e = p = None
		q = int(floor(6 + 52 / (n + 1)))
		sum = q * 2654435769 & 4294967295

		while sum != 0:
			e = sum >> 2 & 3
			p = n
			while p > 0:
				z = value[p - 1]
				mx = (z >> 5 ^ y << 2) + (y >> 3 ^ z << 4) ^ (sum ^ y) + (key[p & 3 ^ e] ^ z)
				y = value[p] = value[p] - mx & 4294967295
				p = p-1

			z = value[n]
			mx = (z >> 5 ^ y << 2) + (y >> 3 ^ z << 4) ^ (sum ^ y) + (key[p & 3 ^ e] ^ z)
			y = value[0] = value[0] - mx & 4294967295
			sum = sum - 2654435769 & 4294967295

		length = len(value)
		n = length - 1 << 2
		m = value[length -1]
		if m < n - 3 or m > n:
			return None

		n = m
		ret = compat._encode('')
		for i in range(length):
			ret+= compat._unichr(value[i] & 255)
			ret+= compat._unichr(value[i] >> 8 & 255)
			ret+= compat._unichr(value[i] >> 16 & 255)
			ret+= compat._unichr(value[i] >> 24 & 255)

		return ret[0:n]


	@staticmethod
	def uc_slice(hex_string, start_pos=None, end_pos=None):
		unit8s = []
		res = []

		for hex_val in findall('..',hex_string):
			unit8s.append(int(hex_val,16) & 0xff)

		start = 0 if start_pos is None else start_pos
		end = len(unit8s) if end_pos is None else end_pos

		bytes_per_sequence = 0
		i = 0

		while i < end:
			first_byte = unit8s[i]
			code_point = None

			if first_byte > 239:
				bytes_per_sequence  = 4
			elif first_byte > 223:
				bytes_per_sequence = 3
			elif first_byte > 191:
				bytes_per_sequence = 2
			else:
				bytes_per_sequence = 1

			if (i + bytes_per_sequence) <= end:
				second_byte = None
				third_byte = None
				fourth_byte = None
				temp_code_point = None

				if bytes_per_sequence == 1 and first_byte < 128:
					code_point = first_byte
				elif bytes_per_sequence == 2:
					second_byte = unit8s[i + 1]
					if (second_byte & 192) == 128:
						temp_code_point = (first_byte & 31) << 6 | second_byte & 63
						if temp_code_point > 127:
							code_point = temp_code_point
				elif bytes_per_sequence == 3:
					second_byte = unit8s[i + 1]
					third_byte = unit8s[i + 2]
					if (second_byte & 192) == 128 and (third_byte & 192) == 128:
						temp_code_point = (first_byte & 15) << 12 | (second_byte & 63) << 6 | third_byte & 63
						if temp_code_point > 2047 and (temp_code_point < 55296 or temp_code_point > 57343):
							code_point = temp_code_point
				elif bytes_per_sequence == 4:
					second_byte = unit8s[i + 1]
					third_byte = unit8s[i + 2]
					fourth_byte = unit8s[i + 3]
					if (second_byte & 192) == 128 and (third_byte & 192) == 128 and (fourth_byte & 192) == 128:
						temp_code_point = (first_byte & 15) << 18 | (second_byte & 63) << 12 | (third_byte & 63) << 6 | fourth_byte & 63
					if temp_code_point > 65535 and temp_code_point < 1114112:
						code_point = temp_code_point
			if code_point == None:
				code_point = 65533
				bytes_per_sequence = 1
			elif code_point > 65535:
			    code_point -= 65536
			    res.append(code_point > 10 & 1023 | 55296)
			    code_point = 56320 | code_point & 1023

			res.append(code_point)
			i += bytes_per_sequence

		return res


	@staticmethod
	def uc_slices_to_string(uc_slices):
		uc_string = compat._encode('')

		for codepoint in uc_slices:
			uc_string += compat._unichr(codepoint)

		return uc_string


	@staticmethod
	def uc_string_to_long_array(uc_string, length=None):
		length = len(uc_string) if length is None else length

		if length % 4 > 0:
			result = [None] * ((length >> 2) + 1)
		else:
			result = [None] * (length >> 2)

		i = 0

		while i < length and ((i >> 2) < len(result)):
			result[i >> 2] = ord(uc_string[i:(i+1)])
			result[i >> 2] |= ord(uc_string[(i+1):(i+2)]) << 8
			if len(uc_string[(i+2):(i+3)]) > 0:
				result[i >> 2] |= ord(uc_string[(i+2):(i+3)]) << 16
			if len(uc_string[(i+3):(i+4)]) > 0:
				result[i >> 2] |= ord(uc_string[(i+3):(i+4)]) << 24
			i+=4

		return result
