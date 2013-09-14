#!/usr/bin/env python
# coding=utf-8
#
# Copyright 2013 Mark Johnson
#
# Authors: Mark Johnson
#
# Based on the PyGTK Application Indicators example by Jono Bacon
# and Neil Jagdish Patel
# http://developer.ubuntu.com/resources/technologies/application-indicators/
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the applicable version of the GNU Lesser General Public
# License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License version 3 along with this program.  If not, see
# <http://www.gnu.org/licenses/>
#
import gobject
import gtk
import appindicator

import urllib
import requests
import time
import sys
import re
import json
import os
import argparse

TIMEOUT = 2 # seconds

class BtSyncIndicator:
    def __init__(self):
        self.ind = appindicator.Indicator ("example-simple-client",
                                          "btsync",
                                          appindicator.CATEGORY_APPLICATION_STATUS,
                                          os.path.dirname(os.path.realpath(__file__))+"/icons")
        self.ind.set_status (appindicator.STATUS_ACTIVE)
        self.ind.set_attention_icon ("btsync-attention")

        self.load_config()

        self.urlroot = 'http://'+self.config['webui']['listen']+'/gui/'
        self.folderitems = {}
        self.info = {}
	self.clipboard = gtk.Clipboard()
        self.animate = None

        self.menu_setup()
        self.ind.set_menu(self.menu)

    def load_config(self):
        config = ""
        for line in open(args.config, 'r'):
            if line.find('//') == -1:
                config += line
        self.config = json.loads(config)

    def menu_setup(self):
        # create a menu
        self.menu = gtk.Menu()

        self.quit_item = gtk.MenuItem("Quit")
        self.quit_item.connect("activate", self.quit)
        self.quit_item.show()
        self.menu.append(self.quit_item)

    def setup_session(self):
      tokenparams = {'t': time.time()}
      tokenurl = self.urlroot+'token.html'
      tokenresponse = requests.post(tokenurl, params=tokenparams)
      regex = re.compile("<html><div[^>]+>([^<]+)</div></html>")
      html = tokenresponse.text
      r = regex.search(html)
      self.token = r.group(1)
      self.cookies = tokenresponse.cookies

      actions = [
              'license', 
              'getostype', 
              'getsettings', 
              'getversion', 
              'getdir', 
              'checknewversion', 
              'getuserlang', 
              'iswebuilanguageset']


      for a in actions:
           params = {'token': self.token, 'action': a}
           response = requests.get(self.urlroot, params=params, cookies=self.cookies)
           self.info[a] = json.loads(response.text)

    def check_status(self):
        params = {'token': self.token, 'action': 'getsyncfolders'}
        response = requests.get(self.urlroot, params=params, cookies=self.cookies)
        status = json.loads(response.text)

        self.check_activity(status['folders'])

        for folder in status['folders']:
            name = folder['name']
            buf = name+" "+folder['size']
            if name in self.folderitems:
                folderitem = self.folderitems[name]
                menuitem = folderitem['menuitem']
                buf = menuitem.set_label(buf)
            else:
                menuitem = gtk.MenuItem(buf)
                self.menu.prepend(menuitem)
                menuitem.show()
                menuitem.set_sensitive(False)
		folderitem = {'menuitem': menuitem, 'peeritems': {}}
                self.folderitems[name] = folderitem

		pos = self.menu.get_children().index(menuitem)

		buf = "Get Secret"
		secretitem = gtk.MenuItem(buf)
		secretmenu = self.build_secret_menu(folder)
		secretitem.set_submenu(secretmenu)
		self.menu.insert(secretitem, pos+1)
		secretitem.show()

		sep = gtk.SeparatorMenuItem()
		self.menu.insert(sep, pos+2)
		sep.show()

            if len(folder['peers']) > 0:
                for peer in folder['peers']:
                    if peer['name'] in folderitem['peeritems']:
                        self.update_peer(folderitem['peeritems'][peer['name']], peer)
                    else:
                        self.add_peer(folderitem, peer)
            else:
                if len(folderitem['peeritems']) > 0:
                    for peeritem in folderitem['peeritems']:
                        self.remove_peer(folderitem, peeritem)

        return True;

    def check_activity(self, folders):
        isactive = False
        for folder in folders:
            for peer in folder['peers']:
                if peer['status'].find('Synced') == -1:
                    isactive = True
                    break

        self.active = isactive
        if self.active:
            if self.animate == None:
                gtk.timeout_add(1000, self.animate_icon)




    def add_peer(self, folderitem, peer):
	name = peer['name']
        buf = self.format_status(peer)
        peeritem = gtk.MenuItem(buf)
	folderposition = self.menu.get_children().index(folderitem['menuitem'])
	self.menu.insert(peeritem, folderposition+1)
	peeritem.set_sensitive(False)
	peeritem.show()
	folderitem['peeritems'][name] = peeritem
        return True;

    def update_peer(self, peeritem, peer):
        buf = self.format_status(peer)
        peeritem.set_label(buf)
        return True;

    def remove_peer(self, folderitem, peeritem):
        self.menu.remove(peer)
        del folderitem['peeritems'][peeritem]
        return True;

    def format_status(self, peer):
	name = peer['name']
	status = peer['status'].replace("<div class='uparrow' />", "⇧")
	status = status.replace("<div class='downarrow' />", "⇩")
        return name+': '+status

    def build_secret_menu(self, folder):
	menu = gtk.Menu()
	readonly = gtk.MenuItem('Read only')
	readonly.connect("activate", self.copy_secret, folder['readonlysecret'])
	readwrite = gtk.MenuItem('Full access')
	readwrite.connect("activate", self.copy_secret, folder['secret'])
	menu.append(readonly)
	menu.append(readwrite)
	readonly.show()
	readwrite.show()
	return menu

    def copy_secret(self, menuitem, secret):
	self.clipboard.set_text(secret)
	return True;

    def animate_icon(self):
        if self.active == False:
            self.animate = None
            return False
        else:
            self.set_icon('-active')
            gtk.timeout_add(500, self.set_icon, '')
            return True
        
    def set_icon(self, variant):
        self.ind.set_icon('btsync'+variant)
        return False

    def main(self):
        self.setup_session()
        self.check_status()

        gtk.timeout_add(TIMEOUT * 1000, self.check_status)
        gtk.main()

    def quit(self, widget):
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', 
                        default=os.environ['HOME']+'/.btsync.conf',
                        help="Location of Bittorrent Sync config file")
    args = parser.parse_args()

    indicator = BtSyncIndicator()
    indicator.main()
