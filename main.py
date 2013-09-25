'''
Obelisk Client
=============

'''

# install_twisted_rector must be called before importing  and using the reactor
from kivy.support import install_twisted_reactor
install_twisted_reactor()

from twisted.internet import ssl, reactor

import os
import kivy
kivy.require('1.0.6')

from os.path import join, dirname

from kivy.app import App
from kivy.logger import Logger
from kivy.properties import StringProperty, ObjectProperty
# FIXME this shouldn't be necessary
from kivy.core.window import Window
from kivy.uix.treeview import TreeView, TreeViewNode, TreeViewLabel
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.audio import SoundLoader
import twisted.web.error

# Application imports
import droid
import plncli
import sseproto

# Menu
jsondata = """ [{"type": "title", "title": "Credentials"},
               {"type": "string", "title": "User name", "desc": "user connecting", "section": "connection", "key": "user"},
               {"type": "bool", "title": "Save pass", "desc": "wether to save the password for next time", "section": "connection", "key": "save_pass"},
               {"type": "title", "title": "Media"},
               {"type": "bool", "title": "Sounds on", "desc": "wether to play sounds", "section": "media", "key": "sounds_on"}]"""
#               {"type": "password", "title": "Password", "desc": "user connecting", "section": "connection", "key": "pass", "password": 1}]"""


class TreeViewContact(TreeViewNode, BoxLayout):
    username = StringProperty()
    status = StringProperty()
    exten = StringProperty()

class PlnApp(App):
    peers = {}
    active = False
    connector = None
    user = ""
    people = None

    # Kivy configuration
    def build_settings(self, settings):
        settings.add_json_panel('Connection', self.config, data=jsondata)

    def build_config(self, config):
        # self.user_data_dir
        config.setdefaults('connection', {
            'user': 'user',
            'save_pass': 0,
            'pass': '****'
        })
        config.setdefaults('media', {
            'sounds_on': 1
        })

    def build(self):
        # the root is created in pln.kv
        root = self.root
        self.main = self.root.main
        self.credit = self.root.credit

        #root.manager.transition = WipeTransition()
        self.show_status("PLN - Obelisk")
        self.main.pass_input.text = self.config.get('connection', 'pass')

    # Avoid getting killed on sleep
    def on_pause(self):
        return True

    # Utility functions
    def show_status(self, text):
        self.root.credit_label.text = str(text)

    def play(self):
        self.sound = SoundLoader.load(os.path.join('sounds','KDE-Im-User-Auth.ogg'))
        self.sound.play()

    # Credit management
    def credit_error(self, failure):
        if failure.type == twisted.web.error.PageRedirect:
            # server needs a proper api...
            self.show_status("Transferred")
        else:
            self.show_status("Error")

    def credit_transfered(self):
        self.show_status("Transferred")
        self.play()

    def send_credit(self):
        amount = self.credit.amount_input.text
        destination = self.credit.destination_input.text

        d = plncli.transferCredit(destination, amount)

        d.addCallback(self.credit_transfered)
        d.addErrback(self.credit_error)

    def create_credit(self):
        amount = self.credit.amount_input.text
        destination = self.credit.destination_input.text

        d = plncli.createCredit(destination, amount)

        d.addCallback(self.credit_transfered)
        d.addErrback(self.credit_error)

    # Peer list management
    def clear_widget(self, widget):
        widget.username_label.color = [1,1,1,1]

    def scroll_selected(self, event):
        selected_ext = None
        selected_node = self.main.treeview1.selected_node
        if selected_node:
            if hasattr(selected_node, 'exten_label'):
                selected_ext = selected_node.exten_label.text
                self.credit.destination_input.text = selected_ext
            else:
                # label.. toggle open
                self.main.treeview1.toggle_node(selected_node)
        if event.is_double_tap and selected_ext:
            self.start_call(selected_ext)

    #@runnable.run_on_ui_thread
    def start_call(self, exten):
        if not droid.available:
            return
        # python to java magic
        droid.action_dial(exten)

    def import_peers(self, data):
        parent = None
        if 'channels' in data and data['channels']:
            if not self.people:
                self.people = self.main.treeview1.add_node(TreeViewLabel(text='People'))
                self.channels = self.main.treeview1.add_node(TreeViewLabel(text='Channels'))
        else:
            self.people = None
            self.channels = None
        parent = self.people
        channels = self.channels
        for peer in data['local']:
            if not peer['status'] in ['UNREACHABLE', 'UNKNOWN']:
                w = self.add_peer(peer['name'], peer['exten'], peer['status'], self.people)
        for peer in data.get('channels', []):
            if not peer['status'] in ['UNREACHABLE', 'UNKNOWN']:
                w = self.add_peer(peer['name'], '', peer['status'], channels)
        if w:
            # adapt parent height if we have any new widgets
            self.main.treeview1.height = (len(self.peers)+1)*w.height

    def add_peer(self, username, exten, status, parent=None):
        if username in self.peers:
            w = self.peers[username]
            prevstatus = status
        else:
            w = self.main.treeview1.add_node(TreeViewContact(username=username, status=status, exten=exten), parent)
            self.peers[username] = w
            prevstatus = w.status
            if not prevstatus == status:
                w.status = status
        if not prevstatus == status:
            w.username_label.color = [1,0,0,1]
            reactor.callLater(1, self.clear_widget, w)
        return w

    def on_credit(self, credit_data):
        user = credit_data['user']
        credit = credit_data['credit']
        if user == self.user:
            self.show_status(credit)
            self.play()

    # Event Handler
    def got_event(self, name, data):
        if name == 'disconnected':
            self.connection_failure()
        elif name == 'rtcheckcalls':
            self.main.event_label.text = 'peer: '+data['calleridnum'] + " " + data['exten']
        elif name == 'peers':
            self.import_peers(data)
        elif name == 'credit':
            self.on_credit(data)
        elif name == 'peer':
            username = data['username']
            w = self.add_peer(username, data.get('peerstatus', 'unkn'), data.get('exten', 'none'), self.people)
        else:
            self.main.event_label.text = name
            print 'unhandled event', name

    # Initial login
    def got_login(self, credit_data):
        if self.active == 2:
            return
        self.active = 2
        self.user = credit_data['user']
        self.is_admin = credit_data['admin']

        if not self.is_admin:
            if self.credit.credit_button:
                self.credit.credit_button.parent.remove_widget(self.credit.credit_button)

        self.show_status(credit_data['credit'])

        factory = sseproto.PlnClientFactory(plncli.cookies, self.got_event)
        self.connector = reactor.connectSSL('pbx.lorea.org', 443, factory, ssl.ClientContextFactory())

        if droid.available:
            #droid.vibrate(200)
            #droid.startActivity('Intent.ACTION_DIAL', "csip:0")
            self.show_status("Droid: " + str(credit_data['credit']))

    def connection_failure(self, failure=None):
        print "Connection fail", failure
        if failure:
            print failure.printTraceback()
        self.main.connection_switch.active = False
        self.show_status("Disconnected")
        self.active = False

    # button callbacks
    def btn_pressed(self):
        if self.active:
            if self.connector:
                self.connector.disconnect()
            return
        self.show_status("Connecting")

        # save pass
        if self.config.getint('connection', 'save_pass'):
            self.config.set('connection', 'pass', self.main.pass_input.text)
        else:
            self.config.set('connection', 'pass', '****')
        self.config.write()

        # initiate connection
        d = plncli.getCredit(self.config.get('connection', 'user'), self.main.pass_input.text)
        d.addCallback(self.got_login)
        d.addErrback(self.connection_failure)

        self.active = True

if __name__ == '__main__':
    PlnApp().run()

