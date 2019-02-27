from __future__ import absolute_import
from builtins import input
from builtins import object
import re
import os
import sys
import json
import requests
import urllib
from getpass import getpass
from constants import *
from bs4 import BeautifulSoup

"""
Lecture authentication procedures

@Version 2.0.0

"""
class Authenticator(object):

    def __init__(self, two_fa = True, duo_factor_handler = None, passcode_factor_handler = None):
        """
        See README
        """
        self.reset_session()
        self._username = None
        self._password = None

        self._two_fa = two_fa
        self._custom_duo_2fa_choice = duo_factor_handler
        self._custom_duo_2fa_passcode = passcode_factor_handler
    
    def authenticate(self, service="cosign-weblogin"):
        """
        Authenticating various umich services
        Credits to Maxim The Man

        Keyword Arguments:
            service {str} -- Service Type (default: {None})
        """
        self.reset_session()
        if self._two_fa:
            self._authenticate_service_2fa(service)
        else:
            self._authenticate_service_simple(service)
    
    def set_credentials(self, username=None, password=None):
        """
        Retrieve the credentials
        
        Keyword Arguments:
            username {str} -- login username (default: {None})
            password {str} -- login password (default: {None})
        """
        self._username = username
        self._password = password   

    def is_authenticated(self):
        """
        Check whether the user has authenticated
        """
        html = self._session.get(AUTH_PAGE_URL).text
        return not ("login.html" in html or "login_error.html" in html)

    def session(self):
        """
        Get the underlining requests session
        """
        return self._session

    def reset_session(self):
        """
        Reset the current session
        """
        self._session = requests.Session()

    """
    Helpers
    """
    def _authenticate_service_simple(self, service_type):
        # load login page to get cookie
        self._session.get(AUTH_PAGE_URL)
        # post to login
        self._session.post(AUTH_URL, {
            "service": service_type,
            "required": "",
            "login": self._username,
            "password": self._password
        })

    def _authenticate_service_2fa(self, service_type):
        # load login page to get cookie
        self._session.get(AUTH_PAGE_URL)
        # pass username/password check
        html = self._session.post(AUTH_URL, {
            "service": service_type,
            "required": "",
            "login": self._username,
            "password": self._password
        }).text

        # extract duo signatures/host/post_args from html
        tx, app, host, post_arg = self._extract_duo_info(html)
        # post to duo's iframe
        html = self._session.post("https://%s/frame/web/v1/auth?%s" % (
                host, urllib.parse.urlencode({
                    'tx': tx, 'parent': "https%3A%2F%2Fweblogin.umich.edu%2Fcosign-bin%2Fcosign.cgi", 'v': '2.6'
                })
            )
        ).text
        # extract sid and 2fa methods
        sid, device_methods = self._extract_duo_2fa_details(html)
        # start the authentication process
        # request choice from user
        device_name, factor = self._request_duo_2fa_choice(device_methods)
        # construct data to send to Duo for 2fa action
        action_data = {
            'device': device_name,
            'factor': factor
        }
        if factor == 'Passcode':
            passcode = self._request_duo_2fa_passcode()
            action_data['passcode'] = passcode
        # send to duo for txid
        prompt_res = self._session.post(
            "https://%s/frame/prompt?%s" % (host, urllib.parse.urlencode({ 'sid': sid })),
            data = action_data
        ).json() 
        if prompt_res['stat'] != 'OK':
            raise Exception("Failed to send 2fa request. Please try again.")
        txid = prompt_res['response']['txid']
        # 1st status check
        auth_status = self._session.post(
            "https://%s/frame/status?%s" % (host, urllib.parse.urlencode({ 'sid': sid })),
            data = {'txid': txid }
        ).json()
        if auth_status['stat'] != 'OK':
            raise Exception("Failed to check status for 2fa request. Please try again.")
        # 2nd status check (should block until succeeded)
        auth_status = self._session.post(
            "https://%s/frame/status?%s" % (host, urllib.parse.urlencode({ 'sid': sid })),
            data = {'txid': txid }
        ).json()
        if auth_status['stat'] != 'OK' or auth_status['response']['result'] != 'SUCCESS':
            raise Exception("2fa failed with reason (%s). Please try again." % auth_status['response']['reason'])
        # otherwise, authentication succeeded
        result_url = auth_status['response']['result_url']
        result_status = self._session.post(
            "https://%s%s?%s" % (host, result_url, urllib.parse.urlencode({ 'sid': sid }))
        ).json()
        if result_status['stat'] != 'OK':
            raise Exception("Unexpected error happened when retrieving cookie. Please try again.")
        # get the cookie
        duo_cookie = result_status['response']['cookie']
        redirect_url = result_status['response']['parent']
    
        # send a final request to weblogin to complete authentication
        validation_data = { 'required': "mtoken" }
        validation_data[post_arg] = duo_cookie + ':' + app
        self._session.post(urllib.parse.unquote(redirect_url), data=validation_data)
    
    def _extract_duo_info(self, html):
        tx, app = self._match_duo_config(html, 'sig_request')
        host = self._match_duo_config(html, 'host')
        post_arg = self._match_duo_config(html, 'post_argument')
        return tx, app, host, post_arg
    
    def _match_duo_config(self, html, key):
        result = re.search(r"'%s':\s*'[^']+'" % key, html)
        if not result:
            raise Exception("Could not find Duo Info. Maybe username/password is wrong?")
        content = result[0]
        value = content.replace("'", "").split()[1]
        if key == 'sig_request':
            tx, app = value.split(':')
            return tx, app
        return value

    def _extract_duo_2fa_details(self, html):
        html = BeautifulSoup(html, 'html.parser')
        try:
            # find sid input
            sid_input = html.find(attrs={"name": "sid"})
            sid = sid_input['value']
            # find devices inputs
            input_section = html.find_all(lambda tag : tag.has_attr('data-device-index'))
            # extract tokens
            device_methods = []
            for fieldset in input_section:
                method = {
                    "device_name": fieldset['data-device-index'],
                    "factors": []
                }
                for div in fieldset.find_all('div', "row-label"):
                    factor_input = div.find("input", attrs={"name": "factor"})
                    method['factors'].append(factor_input['value'])
                device_methods.append(method)
            return sid, device_methods
        except Exception as e:
            raise Exception("Cannot find duo details. Maybe the protocol has changed. Report to developer ASAP. (err msg) %s " % e)
    
    def _request_duo_2fa_choice(self, device_methods):
        # check for custom handler
        if self._custom_duo_2fa_choice:
            return self._custom_duo_2fa_choice(device_methods)

        print("You have the following 2fa options: ")
        for idx, method in enumerate(device_methods):
            print("Device: %s (%s)" % (method['device_name'], idx+1) )
            for idx2, factor in enumerate(method['factors']):
                print("\tAction: %s (%s)" % (factor, idx2+1))
        result = input("Please choose your device and action (e.g. enter 1,1 to pick the 1st device for its 1st action): ")
        device_id, method_id = result.split(',')
        try:
            device = device_methods[int(device_id)-1]
            device_name = device['device_name']
            factor = device['factors'][int(method_id)-1]
            return device_name, factor
        except Exception as e:
            print(e)
            raise Exception("Please choose a valid option")
    
    def _request_duo_2fa_passcode(self):
        # check for custom handler
        if self._custom_duo_2fa_passcode:
            return self._custom_duo_2fa_passcode()

        passcode = input("You have selected the passcode option. Please enter your passcode: ")
        return passcode


