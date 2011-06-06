#!/usr/bin/env python

import base64
import logging
import os
import re
import thread
import time
import urllib2

from dbus.mainloop.glib import DBusGMainLoop
import dbus
import gobject


DEBUG_LEVEL = logging.INFO


class Application(object):

    cache_dir = os.path.expanduser('~/.cache/spotify-extras')
    default_icon_url = 'http://open.spotify.com/static/images/icon-48.png'
    img_re = re.compile('<img.*?id="cover-art".*?src="(.*?)"')
    spotify_track_url = 'http://open.spotify.com/track/%s'

    def __init__(self):
        self.bus = None
        self.last_notification = 0
        self.last_track = None
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        self.update_default_icon()

        gobject.threads_init()

        DBusGMainLoop(set_as_default=True)
        self.loop = gobject.MainLoop()

    def connect(self):
        self.bus = dbus.Bus(dbus.Bus.TYPE_SESSION)

    def get_interface(self, bus_name, object_path, interface):
        if self.bus is None:
            self.connect()
        obj = self.bus.get_object(bus_name, object_path)
        return dbus.Interface(obj, interface)

    def get_current_track(self):
        interface = self.get_interface('com.spotify.qt', '/',
            'org.freedesktop.MediaPlayer2')
        return interface.GetMetadata()

    def update_default_icon(self):
        default_icon_path = self.get_icon_path('default')
        if not os.path.exists(default_icon_path):
            response = urllib2.urlopen(self.default_icon_url) 
            f = open(default_icon_path, 'wb')
            f.write(response.read())
            f.close()

    def get_icon_path(self, icon):
        return os.path.join(self.cache_dir, icon) 

    def get_track_icon_path(self, track):
        raw_icon_name = '%s-%s' % (track['xesam:artist'], track['xesam:album'])
        icon_name = base64.b64encode(raw_icon_name.encode('utf-8'))
        return self.get_icon_path(icon_name)

    def get_track_url(self, track):
        track_id = track['mpris:trackid'].split(':')[-1]
        return self.spotify_track_url % track_id

    def update_track_icon(self, track):
        track_icon_path = self.get_track_icon_path(track)
        if not os.path.exists(track_icon_path):
            track_url = self.get_track_url(track)
            response = urllib2.urlopen(track_url)
            img_match = self.img_re.search(response.read())
            if img_match:
                img_url = img_match.group(1)
                response = urllib2.urlopen(img_url)
                img_f = open(track_icon_path, 'wb')
                img_f.write(response.read())
                img_f.close()

                self.notify(*self.get_playback_info())

    def _notify(self, summary, icon_path=None, body=""):
        interface = self.get_interface('org.freedesktop.Notifications',
            '/org/freedesktop/Notifications', 'org.freedesktop.Notifications')
        if icon_path is None:
            icon_path = self.get_icon_path('default')
        if self.last_notification:
            logging.debug('Closing notification %s.' % self.last_notification)
            interface.CloseNotification(self.last_notification)

        self.last_notification = interface.Notify('spotify-extras',
            self.last_notification, icon_path, summary, body, [],
                {}, 2)

    def notify(self, status, track):
        if status == "Stopped":
            self._notify("[stopped]")
            return

        summary = track['xesam:artist']
        body = '%s\n%s (%s)' % (track['xesam:title'], track['xesam:album'],
            track['xesam:contentCreated'][:4])

        logging.info('Current track: %(xesam:title)s by %(xesam:artist)s' % 
            track)

        logging.debug('Raising notification %s.' % track['mpris:trackid'])

        track_icon_path = self.get_track_icon_path(track)
        if os.path.exists(track_icon_path):
            icon_path = track_icon_path 
        else:
            icon_path = None

        self._notify(summary, icon_path, body)

        if icon_path != track_icon_path:
            thread.start_new_thread(self.update_track_icon, (track,))

    def get_playback_status(self):
        interface = self.get_interface('org.mpris.MediaPlayer2.spotify',
            '/org/mpris/MediaPlayer2', 'org.freedesktop.DBus.Properties')
        return interface.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus")


    def get_playback_info(self):
        status = self.get_playback_status()
        track = self.get_current_track()
        return status, track

    def update_track_display(self, sender=None, *args, **kwargs):
        info = self.get_playback_info()
        if info and info != self.last_track:
            self.notify(*info)
            self.last_track = info

    def start_notifications(self):
        self.update_track_display()
        interface = self.get_interface('org.mpris.MediaPlayer2.spotify',
            '/org/mpris/MediaPlayer2', 'org.freedesktop.DBus.Properties')
        interface.connect_to_signal('PropertiesChanged',
            self.update_track_display)

    def player_command(self, command):
        interface = self.get_interface('org.mpris.MediaPlayer2.spotify',
            '/org/mpris/MediaPlayer2', 'org.mpris.MediaPlayer2.Player')
        method = getattr(interface, command)
        method()

    def media_player_key_pressed(self, sender, key, **kwargs):
        command = {
            "Next": "Next",
            "Play": "PlayPause",
            "Previous": "Previous",
        }.get(key)

        if command:
            self.player_command(command)
            

    def listen_for_keys(self):
        interface = self.get_interface('org.gnome.SettingsDaemon',
            '/org/gnome/SettingsDaemon/MediaKeys',
            'org.gnome.SettingsDaemon.MediaKeys')
        interface.connect_to_signal('MediaPlayerKeyPressed',
            self.media_player_key_pressed)

    def run(self):
        self.start_notifications()
        self.listen_for_keys()
        self.loop.run()


if __name__ == '__main__':
    logging.getLogger().setLevel(DEBUG_LEVEL)

    application = Application()
    application.run()
