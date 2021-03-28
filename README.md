# Webex plugin for Weechat

This is a Cisco Webex plugin for Weechat (a.k.a. CLI tool to communicate with webex)

# Installation / prerequisities
## Install weechat
First, install weechat.
See [weechat](https://weechat.org/)

Then, execute weechat a first time to create the .weechat config folder:

```
weechat
```

## Install webexteamssdk
Install python pip:
```
sudo apt-get install python3-pip python3-dev
```
And webexteamsdk
```
sudo pip3 install webexteamssdk
```

## Install ```webex.py``` plugin
Now install the ```webex.py``` script in ```~/.weechat/python/```

```
cd `~/.weechat/python/    # folder should exist, if it does not, execute weechat
wget https://github.com/arnaudmorin/weechat-webex/raw/main/webex.py
cd
```

## Install nginx
### Why?
Cisco Webex use *webhooks* to send messages (no websockets yet in webex python SDK).
So, to be able to receive new messages, your weechat instance needs to be accessible from internet. That way, Cisco Webex API can do HTTP POST requests against you.

The ```webex.py``` weechat plugin will listen only locally (```127.0.0.1```) on port ```8080```.

So we need a nginx (or apache) web server configured to do proxypass in order to forward webhook requests to the weechat plugin.

### Install
```
sudo apt-get install nginx
```
### Configure nginx
We need to let nginx forward (proxypass) requests to weechat
```
sudo vim /etc/nginx/sites-enabled/default
```
Below the ```location / {...}``` block, add a new one:
```
        location /webhook {
                proxy_pass http://127.0.0.1:8080/webhook;
        }
```
Restart nginx
```
sudo systemctl restart nginx
```

## HTTPS with letsencrypt
It's a good idea to configure letsencrypt on your server:
```
sudo apt-get install certbot python3-certbot-nginx
certbot --nginx
... # follow the steps
```

## Cisco access token
You will need a token.
Grab one from:
[https://developer.webex.com/docs/api/getting-started](https://developer.webex.com/docs/api/getting-started)


# First run

Execute weechat:
```
weechat
```

From weechat console:
```
/python load webex
```

This will raise an error because you need to configure the plugin now :)


Configure at least ```access_token```, ```base_url``` and ```default_domain```:
From weechat console:
```
/set webex.server.access_token "your_token"
/set webex.server.base_url "https://your_server_public_ip_or_name"
/set webex.server.default_domain "your_cisco_email_domain"
/save
```

Reload the plugin:
```
/python reload
```

You're done!

# How to use
You can start a new conversation with a friend using:
```
/wmsg arnaud.morin
```
This will open a new buffer to let you write a message to your buddy

You can search for people using:
```
/wsp name
```
This will give you a list of users that have name starting with ```name``` in the main weechat buffer.

You can also search for rooms:
```
/wsr string
```
This will also give you a list of room that contains ```string```.

To join a specific room:
```
/wj room_name
```
This will open a new buffer to let you write/receive message from that room.

```
/wreconnect
# or
/wreconnect new_token
```
This will reconnect on webex API. Usefull when your token has expired or if you want to change it.

Enjoy :)


