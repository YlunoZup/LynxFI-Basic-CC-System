from cryptography.fernet import Fernet
from base64 import b64decode
from app import models
import rsa
import json

def fprint():
    snm = dict()
    try:
        f = open('/proc/cpuinfo','r')
        for line in f:
            if line[0:6]=='Serial':
                serial = line[10:26]
        f.close()

        eth0_mac = open("/sys/class/net/eth0/address").read().strip()

        snm['serial'] = serial
        snm['eth0_mac'] = eth0_mac
    except:
        return False
    return snm

def cc(ac=None):
    return True

def grc():
    return b'dummy_activation_code'
