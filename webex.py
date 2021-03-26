# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Arnaud Morin <arnaud.morin@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

#
# Cisco Webex protocol for WeeChat.
#
# For help, see /help webex
# Happy chat, enjoy :)

import os
import weechat

# See if there is a `venv` directory next to our script, and use that if
# present. This first resolves symlinks, so this also works when we are
# loaded through a symlink (e.g. from autoload).
# See https://virtualenv.pypa.io/en/latest/userguide/#using-virtualenv-without-bin-python
# This does not support pyvenv or the python3 venv module, which do not
# create an activate_this.py: https://stackoverflow.com/questions/27462582
try:
    activate_this = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'venv', 'bin', 'activate_this.py')
    if os.path.exists(activate_this):
        exec(open(activate_this).read(), {'__file__': activate_this})
except Exception:
    pass

from webexteamssdk import WebexTeamsAPI
import socket
import re
import json
from http.server import BaseHTTPRequestHandler
from io import BytesIO

SCRIPT_NAME = "webex"
SCRIPT_AUTHOR = "Arnaud Morin <arnaud.morin@gmail.com>"
SCRIPT_VERSION = "0.1.1"
SCRIPT_LICENSE = "APACHE2"
SCRIPT_DESC = "Cisco Webex protocol for WeeChat"
SCRIPT_COMMAND = SCRIPT_NAME

webex_config_file = None
webex_config_section = {}
webex_config_option = {}

webex_server = None


# =================================[ config ]=================================

def webex_config_init():
    """ Initialize config file: create sections and options in memory. """
    global webex_config_file, webex_config_section, webex_config_option

    # This will create webex.conf file
    webex_config_file = weechat.config_new(SCRIPT_NAME, "webex_config_reload_cb", "")
    if not webex_config_file:
        return

    # server section
    webex_config_section["server"] = weechat.config_new_section(
        webex_config_file, "server", 0, 0, "", "", "", "", "", "", "", "", "", "")

    webex_config_option["access_token"] = weechat.config_new_option(
        webex_config_file, webex_config_section["server"],
        "access_token", "string", "Access Token", "", 0, 0,
        "token", "token", 0, "", "", "", "", "", "")
    webex_config_option["autojoin_rooms"] = weechat.config_new_option(
        webex_config_file, webex_config_section["server"],
        "autojoin_rooms", "string", "Rooms to join on start", "", 0, 0,
        "", "", 0, "", "", "", "", "", "")
    webex_config_option["autojoin_directs"] = weechat.config_new_option(
        webex_config_file, webex_config_section["server"],
        "autojoin_directs", "string", "1:1 rooms to join on start", "", 0, 0,
        "", "", 0, "", "", "", "", "", "")
    webex_config_option["base_url"] = weechat.config_new_option(
        webex_config_file, webex_config_section["server"],
        "base_url", "string", "Your public base URL for Webex Webhook to join you", "", 0, 0,
        "", "", 0, "", "", "", "", "", "")
    webex_config_option["default_domain"] = weechat.config_new_option(
        webex_config_file, webex_config_section["server"],
        "default_domain", "string", "Default domain for emails.", "", 0, 0,
        "", "", 0, "", "", "", "", "", "")


def webex_config_reload_cb(data, config_file):
    """ Reload config file. """
    return weechat.config_reload(config_file)


def webex_config_read():
    """ Read config file. """
    global webex_config_file
    return weechat.config_read(webex_config_file)


def webex_config_write():
    """ Write config file """
    global webex_config_file, webex_config_section, webex_config_option, webex_server
    return weechat.config_write(webex_config_file)


# ================================[ commands ]================================

def webex_hook_commands_and_completions():
    """ Hook commands and completions. """
    weechat.hook_command("wmsg", "Open a chat with a person",
                         "<buddy>",
                         " buddy: user name (like arnaud.morin)",
                         "",
                         "webex_cmd_wmsg", "")
    weechat.hook_command("wj", "Join a room",
                         "<room>",
                         " room: room name",
                         "",
                         "webex_cmd_wj", "")
    weechat.hook_command("wsr", "Search room based on name",
                         "<name>",
                         " name: room name",
                         "",
                         "webex_cmd_wsr", "")
    weechat.hook_command("wsp", "Search user based on name",
                         "<name>",
                         " name: user name (like arnaud)",
                         "",
                         "webex_cmd_wsp", "")


def webex_cmd_wmsg(data, buffer, buddy):
    """ Send a message to a person """
    global webex_server
    webex_server.prnt(f"Opening chat with {buddy}")

    # Add domain if not set
    if '@' not in buddy:
        buddy = f"{buddy}@{webex_server.domain}"
    person = webex_server.get_person(buddy)
    if person:
        buddy = Buddy(person)
        webex_server.prnt(f"Found person: {buddy.name}")
        chat = Chat(webex_server, buddy.name, buddy.id, "direct")
        webex_server.chats.append(chat)
    else:
        webex_server.prnt(f"No room found with name {buddy}")

    return weechat.WEECHAT_RC_OK


def webex_cmd_wj(data, buffer, room_name):
    """ Join a room """
    global webex_server
    webex_server.prnt(f"Trying to join {room_name}")

    room = webex_server.search_room(room_name)
    if room:
        webex_server.prnt(f"Found room: {room.title}")
        chat = Chat(webex_server, room.title, room.id, "room")
        webex_server.chats.append(chat)
    else:
        webex_server.prnt(f"No room found with name {room_name}")

    return weechat.WEECHAT_RC_OK


def webex_cmd_wsr(data, buffer, room_name):
    """ Search a room """
    global webex_server
    webex_server.prnt(f"List of room with '{room_name}' in name:")

    rooms = webex_server.search_rooms(room_name)
    for room in rooms:
        webex_server.prnt(f" - {room.title}")

    return weechat.WEECHAT_RC_OK


def webex_cmd_wsp(data, buffer, name):
    """ Search a person """
    global webex_server
    webex_server.prnt(f"List of people with '{name}' in name:")

    persons = webex_server.search_persons(name)
    for person in persons:
        webex_server.prnt(f" - {person.emails[0]}")

    return weechat.WEECHAT_RC_OK


# ================================[ server ]==================================
class Server(object):
    def __init__(self):
        self.chats = []
        self.webexapi = None
        self.buddy = None
        self.hook = None
        self.sock = None
        self.domain = None

    def connect(self):
        # API
        try:
            self.webexapi = WebexTeamsAPI(access_token=self.get_config_value("access_token"))
        except Exception as e:
            self.prnt(f"Error while trying to connect to webex API: {e}")
            return False

        self.domain = self.get_config_value("default_domain")

        # Test API and grab your name
        try:
            buddy = self.webexapi.people.me()
        except Exception as e:
            self.prnt(f"Error while trying to get me(): {e}")
            return False
        self.buddy = Buddy(buddy)
        self.prnt(f"Bienvenue {self.buddy.name}")

        # Join rooms that are in config
        rooms_to_join = self.get_config_value("autojoin_rooms")
        for room_name in rooms_to_join.split(','):
            room = self.search_room(room_name)
            self.chats.append(Chat(self, room.title, room.id, "room", auto=False))

        # Join direct chats that are in config
        directs_to_join = self.get_config_value("autojoin_directs")
        for email in directs_to_join.split(','):
            if '@' not in email:
                email = f"{email}@{self.domain}"
            buddy = Buddy(self.get_person(email))
            self.chats.append(Chat(self, buddy.name, buddy.id, "direct", auto=False))

        # SOCKET
        # We bind on 127.0.0.1:8080
        # So we need a proxy pass (like nginx or apache)
        # to forward the request to this socket
        if not self.sock:
            self.prnt("Starting HTTP server")
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.bind(("127.0.0.1", 8080))
                self.sock.listen(5)
            except Exception as e:
                self.prnt(f"Error while creating the HTTP server: {e}")
                return False
            self.prnt(f"Server listening on {self.sock.getsockname()}")

        # WEECHAT HOOK
        if not self.hook:
            self.hook = weechat.hook_fd(self.sock.fileno(), 1, 0, 0, "socket_cb", "")

        # WEBEX HOOK
        # Delete old webex hooks if any
        try:
            self.delete_webex_hook()
        except Exception as e:
            self.prnt(f"Error while deleting old hooks: {e}")
        # Now create a new one
        self.prnt('Creating Webex Webhook')
        # Base url is supposed to be public so webex can talk to us
        # This is the web server that will proxypass to the socket
        base_url = self.get_config_value("base_url")
        try:
            self.webexapi.webhooks.create(
                name="weechat_hook",
                targetUrl=f"{base_url}/webhook",
                resource="messages",
                event="created")
        except Exception as e:
            self.prnt(f"Error while creating webex webhook: {e}")
            return False
        self.prnt('Webex Webhook created')
        return True

    def list_rooms(self, type="group"):
        """Grab room list from webex"""
        return self.webexapi.rooms.list(type=type, sortBy="lastactivity")

    def search_room(self, name):
        """Search for a room by name. Return first room that match"""
        for room in self.list_rooms():
            if name in room.title:
                return room

    def search_rooms(self, name):
        """Search for rooms by name. Return all rooms that match"""
        result = []
        for room in self.list_rooms():
            if name.lower() in room.title.lower():
                result.append(room)
        return result

    def get_person(self, email):
        """Get person from email"""
        try:
            people = list(self.webexapi.people.list(email=email))[0]
            return people
        except Exception:
            return None

    def get_person_from_id(self, id):
        """Get person from id"""
        try:
            return self.webexapi.people.get(id)
        except Exception:
            return None

    def search_persons(self, name):
        """Search for buddies by name. Return all buddies that match"""
        return list(self.webexapi.people.list(displayName=name))

    def delete_webex_hook(self):
        """Delete all webex hooks created by weechat"""
        hooks = self.webexapi.webhooks.list()
        for hook in hooks:
            # Delete all previously set hooks
            if hook.name == "weechat_hook":
                self.prnt("Removing webex hook")
                self.webexapi.webhooks.delete(hook.id)

    def get_config_value(self, option):
        """ Get an option """
        global webex_config_option
        return weechat.config_string(webex_config_option[option])

    def prnt(self, message):
        weechat.prnt("", message)

    def send_room_message(self, room_id, message):
        self.webexapi.messages.create(roomId=room_id, text=message)

    def send_direct_message(self, person_id, message):
        self.webexapi.messages.create(toPersonId=person_id, text=message)

    def receive_message(self, raw):
        self.prnt(raw)
        try:
            data = json.loads(raw)
            if 'data' in data:
                # Discard message from myself
                if data['data']['personId'] == self.buddy.id:
                    self.prnt("Message from myself")
                # Messages for a room
                elif data['data']['roomId'] in [x.id for x in self.chats]:
                    self.prnt(f"Receive a message for room {data['data']['roomId']}")
                    chat = next((x for x in self.chats if x.id == data['data']['roomId']), None)
                    chat.receive_message(data['data']['id'])
                # Messages from a person
                elif data['data']['roomType'] == "direct":
                    self.prnt(f"Receive a message from a person {data['data']['personId']}")
                    chat = next((x for x in self.chats if x.id == data['data']['personId']), None)
                    # If this is first time we are talking to this person
                    # Create a new chat
                    if not chat:
                        buddy = Buddy(self.get_person_from_id(data['data']['personId']))
                        chat = Chat(self, buddy.name, buddy.id, "direct", auto=False)
                        self.chats.append(chat)
                    chat.receive_message(data['data']['id'])
        except Exception as e:
            self.prnt(f"Error while receiving data {e}")


def get_chat_from_buffer(buffer):
    """ Search a chat from a buffer. """
    global webex_server
    for chat in webex_server.chats:
        if chat.buffer == buffer:
            return chat
    return None


def get_chat_from_name(name):
    """ Search a chat from a name. """
    global webex_server
    for chat in webex_server.chats:
        print(chat.name)
        if chat.name == name:
            return chat
    return None


# =================================[ chats ]==================================

class Chat:
    """ Class to manage private chat or rooms. """

    def __init__(self, server, name, id, kind="room", auto=True):
        """ Init chat """
        self.server = server
        self.name = f"{name}"
        self.id = f"{id}"
        self.buffer = weechat.buffer_search("python", self.id)
        self.kind = kind    # can be room or direct
        if not self.buffer:
            self.buffer = weechat.buffer_new(self.id,
                                             "webex_buffer_input_cb", "",
                                             "webex_buffer_close_cb", "")
        if self.buffer:
            weechat.buffer_set(self.buffer, "title", self.name)
            weechat.buffer_set(self.buffer, "short_name", self.name)
            weechat.hook_signal_send("logger_backlog",
                                     weechat.WEECHAT_HOOK_SIGNAL_POINTER, self.buffer)
            if auto:
                weechat.buffer_set(self.buffer, "display", "auto")

    def prnt(self, message):
        """ Print a message in the buffer """
        weechat.prnt(self.buffer, message)

    def receive_message(self, message_id):
        """ Receive a message from someone """
        try:
            message = self.server.webexapi.messages.get(message_id)
            buddy = message.personEmail.split('@')[0]
            weechat.prnt_date_tags(self.buffer, 0,
                                   "notify_private,nick_%s,prefix_nick_%s,log1" %
                                   (buddy,
                                    weechat.config_string(weechat.config_get("weechat.color.chat_nick_other"))),
                                   "%s%s\t%s" % (weechat.color("chat_nick_other"),
                                                 buddy,
                                                 message.text))
        except Exception as e:
            self.prnt(f"Unable to retrieve a message from webex API {e}")

    def send_message(self, message):
        """ Send message """
        if self.kind == "room":
            self.server.send_room_message(self.id, message)
        else:
            self.server.send_direct_message(self.id, message)
        weechat.prnt_date_tags(self.buffer, 0,
                               "notify_none,no_highlight,nick_%s,prefix_nick_%s,log1" %
                               (self.server.buddy.name,
                                weechat.config_string(weechat.config_get("weechat.color.chat_nick_self"))),
                               "%s%s\t%s" % (weechat.color("chat_nick_self"),
                                             self.server.buddy.name,
                                             message))

    def delete(self):
        """ Delete chat. """
        if self.buffer:
            self.buffer = None


# ================================[ buddy ]=================================
class Buddy(object):
    def __init__(self, data):
        self.id = data.id
        self.email = data.emails[0]
        self.name = self.parse_email(self.email)

    def parse_email(self, email):
        """Parse email to grab name"""
        return email.split('@')[0]


# ================================[ HTTP ]=================================

class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, raw_http_request):
        self.rfile = BytesIO(raw_http_request.encode('utf-8'))
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()

        # Headers
        self.headers = dict(self.headers)
        # Data
        try:
            self.data = raw_http_request[raw_http_request.index('\n\n') + 2:].rstrip()
        except ValueError:
            self.data = None


def http_reply(conn, code, extra_header, message, mimetype='text/html'):
    """Send a HTTP reply to client."""
    global urlserver_settings
    if extra_header:
        extra_header += '\r\n'
    s = 'HTTP/1.1 %s\r\n' \
        '%s' \
        'Content-Type: %s\r\n' \
        'Content-Length: %d\r\n' \
        '\r\n' \
        % (code, extra_header, mimetype, len(message))
    msg = None
    if type(message) is bytes:
        msg = s.encode('utf-8') + message
    else:
        msg = s.encode('utf-8') + message.encode('utf-8')
    conn.sendall(msg)


# ================================[ callbacks ]=================================

def webex_unload_cb():
    """ Function called when script is unloaded. """
    global webex_server
    webex_server.prnt("Unloading")
    webex_config_write()
    if webex_server.sock:
        webex_server.sock.close()
        webex_server.sock = None
    if webex_server.hook:
        weechat.unhook(webex_server.hook)
        webex_server.hook = None
    webex_server.delete_webex_hook()
    return weechat.WEECHAT_RC_OK


def webex_buffer_input_cb(data, buffer, input_data):
    """ Callback called for input data on a buffer. """
    chat = get_chat_from_buffer(buffer)
    if chat:
        chat.send_message(input_data)

    return weechat.WEECHAT_RC_OK


def webex_buffer_close_cb(data, buffer):
    """ Callback called when a jabber buffer is closed. """
    global webex_server
    chat = get_chat_from_buffer(buffer)
    if chat:
        # Unset the buffer
        chat.delete()
        # Delete the chat from server.chats
        webex_server.chats.remove(chat)

    return weechat.WEECHAT_RC_OK


def socket_cb(data, fd):
    global webex_server
    data = None
    if webex_server.sock.fileno() == int(fd):
        conn, addr = webex_server.sock.accept()
        # Grab data
        try:
            conn.settimeout(0.3)
            data = conn.recv(4096).decode('utf-8')
            data = data.replace('\r\n', '\n')
        except Exception:
            return weechat.WEECHAT_RC_OK

        m = re.search('^POST /webhook HTTP/.*$', data, re.MULTILINE)
        if m:
            http_request = HTTPRequest(data)
            webex_server.receive_message(http_request.data)

        http_reply(conn, "200 OK", "", "OK")
        conn.close()
    return weechat.WEECHAT_RC_OK


# ==================================[ main ]==================================

if __name__ == "__main__":
    if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
                        SCRIPT_LICENSE, SCRIPT_DESC,
                        "webex_unload_cb", ""):

        webex_hook_commands_and_completions()
        webex_config_init()
        webex_config_read()

        webex_server = Server()
        webex_server.connect()
