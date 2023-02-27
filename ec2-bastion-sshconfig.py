#!/usr/bin/env python

import argparse
import boto
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from collections import defaultdict

# command line arguments
parser = argparse.ArgumentParser()
parser.add_argument(
  '--profile', 
  default=os.environ.get('AWS_PROFILE'), 
  help='Specify AWS credential profile to use.'
  )
parser.add_argument(
  '--ec2Py', 
  default='ec2.py', 
  help='inventory script to use.'
  )
parser.add_argument(
  '--ec2PyINI', 
  default=os.environ.get('EC2_INI_PATH'), 
  help='inventory config file to use'
  )
parser.add_argument(
  '--sshUser',
  default=os.environ.get('USER'),
  help='SSH username'
  )
parser.add_argument(
  '--sshKeyPATH',
  default="~/SSHKEYS/",
  help='PATH to SSH keys'
  )
parser.add_argument(
  '--sshPort',
  default="22",
  help='Alternate SSH port'
)
parser.add_argument(
  '--debug', 
  default=False, 
  help='Set to True to enable debug msgs'
)
parser.add_argument(
  '--awsDNSProfile',
  default="default",
  help='The AWS profile used to interact with route53'
)
parser.add_argument(
  '--tld',
  default="example.com",
  help='tld to append to hostnames'
)
args = parser.parse_args()

def main():
  # check for valid AWS_PROFLE
  if not args.profile:
    print("AWS_PROFILE not set. Please provide one.")
    exit(parser.print_usage())

  # check for valid EC2_INI_PATH
  if not args.ec2PyINI:
    print("EC2_INI_PATH not set. Please provide one.")
    exit(parser.print_usage())
  
  genConfig()

def debug(msg):
  if args.debug:
    print('DEBUG: ' + msg, file=sys.stderr)

def zoneaxfr():
  debug('Creating a map of public ips to hostnames ..')
  r53 = boto.connect_route53(profile_name=args.awsDNSProfile)
  z = r53.get_zone(args.tld).id
  o = r53.get_all_rrsets(z, type=None, name=None, identifier=None, maxitems=None)
  list = []
  dict = {}

  if not args.tld.endswith('.'):
    args.tld += '.'

  for i in o:
    for c in "<" ">":
      i = str(i).replace(c, '')
      s = str(i).split(':')
      name = s[1]
      type = s[2]
      record = s[3]

    if ',' not in record:
      if type == 'A' and ipaddress.ip_address(record).is_global:
        if record in dict:
          dict[record].append(name.rstrip('.'))
        else:
          dict[record] = [name.rstrip('.')]
      elif type == 'A' and ipaddress.ip_address(record).is_private:
        if record in dict:
          dict[record].append(name.rstrip('.'))
        else:
          dict[record] = [name.rstrip('.')]
      elif type == 'CNAME':
        if record in dict:
          dict[record].append(name.rstrip('.'))
        else:
          dict[record] = [name.rstrip('.')]

  debug('dumping dns map:')
  for k in dict.keys():
    debug('keyname: ' + k + ': ')
    for s in dict[k]:
      debug('\t- ' + s)
    debug("")

  return dict

def cmd():
  # output the json output from ec2.py

  # verify inventory scipt exists
  x = shutil.which(
    args.ec2Py, 
    mode=os.F_OK | os.X_OK, 
    path=None
    )
  # test that we can execute ec2.py
  try:
    subprocess.run(
      [sys.executable, x, "--help"], 
      capture_output=True
      )
  except:
    print("inventory script", args.ec2Py, "not found.")
  # execute ec2.py, exit on error
  debug('found ec2.py: ' + x)
  debug('running ec2.py ..')
  process = subprocess.run(
    [sys.executable, x, "--refresh-cache", "--profile", args.profile], 
    env=dict(EC2_INI_PATH=args.ec2PyINI), 
    capture_output=True, 
    text=True
    )
  if process.returncode == 0:
    return process.stdout
  else:
    exit(print(process.stderr))

def listVPCs(inv):
  # return a list of VPCs
  list = []
  for i in inv['vpcs']['children']:
    list.append(i)
  debug('list of vpcs: ' + " ".join(list))
  list.sort()
  return list

def listInstances(inv, vpc):
  # return a list of instances within an environment
  list = []
  for i in inv[vpc]:
    list.append(i)
  debug('list of instances in vpc ' + vpc + ': ' + " ".join(list))
  list.sort()
  return list

def instanceProp(inv, inst, key):
  d = inv['_meta']['hostvars']
  return d[inst][key]

def bannerEntry(vpc):
  # outout section divider
  banner = "####   " + vpc.replace("vpc_id_", "") + "   #####"
  print("#".ljust(50, "#"))
  print(banner.ljust(50, "#"))
  print("#".ljust(50, "#"), "\n")

def portCheck(inst, port):
   socket.setdefaulttimeout(3)
   s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   try:
      s.connect((inst, int(port)))
      s.shutdown(2)
      return True
   except:
      return False

def findSshPort(inv, inst):
  port = ""
  if instanceProp(inv, inst, "ec2_ip_address"):
    ip = instanceProp(inv, inst, "ec2_ip_address")
    debug(inst + ' has a public ip: ' + ip)
    # if sshPort is defined try both alternate port and port 22
    if args.sshPort != "22":
      if portCheck(ip, args.sshPort):
        port = args.sshPort
      elif portCheck(ip, "22"):
        port = "22"
    # otherwise just try port 22
    elif portCheck(ip, "22"):
      port = "22"
    else:
      port = False

  if port:
    debug(inst + ' accepting connections on port: ' + port)
  else:
    debug(inst + ' not accepting connections') 

  return port

def findBastion(inv, vpc):
  list = []
  r = ""
  debug('looping through vpc hosts to find a host with a public ip')
  # return a bastion host for a vpc
  for inst in listInstances(inv, vpc):
    i = instanceProp(inv, inst, "ec2_ip_address")
    if i:
      debug(inst + ' has a public ip ' + i)
      list.append(inst)

  if list:
    for n in list:
      if "bastion" in n:
        r = n
        break
      else:
        r = n
    return r
  else:
    return False

def genConfig():
  # output the sshconfigs
  pattern = r'[0-9]+'

  # load output of ec2.py into inv
  inv = json.loads(cmd())
  z = zoneaxfr()
  tld = args.tld.rstrip('.')

  for vpc in listVPCs(inv):
    debug('')
    debug('Processing vpc: ' + vpc)
    bannerEntry(vpc)

    for inst in listInstances(inv, vpc):
      print('# <--', end='')
      debug('')
      debug('Processing host: ' + inst)
      i = instanceProp(inv, inst, "ec2_id")
      p = findSshPort(inv, inst) 
      d = inst + "." + tld
      b = ""
      q = []
      h = [inst, i]

      if instanceProp(inv, inst, "ec2_ip_address") in z:
        debug('seaching the dictionary for keyname matching the public ip: ' + instanceProp(inv, inst, "ec2_ip_address"))
        for x in z[instanceProp(inv, inst, "ec2_ip_address")]:
          debug('found public ip alias: ' + x)
          if x not in h:
            h.append(x)
      else:
        debug('no public ip keyname matched found for: ' + instanceProp(inv, inst, "ec2_ip_address"))

      if instanceProp(inv, inst, "ec2_private_ip_address") in z:
        debug('searching the dictionary for keyname matching the private ip: ' + instanceProp(inv, inst, "ec2_private_ip_address"))
        for x in z[instanceProp(inv, inst, "ec2_private_ip_address")]:
          debug('found private ip alias: ' + x)
          if x not in h:
            h.append(x)
      else:
        debug('no private ip keyname matched found for: ' + instanceProp(inv, inst, "ec2_private_ip_address"))

      if d in z:
        debug('searching the dictionary for keynames matching cname ' + d)
        for x in z[d]:
          debug('found cname alias: ' + x)
          if x not in h:
            h.append(x)

      for x in h:
        debug('searching the dictionary for keynames matching alias ' + x)
        if x.endswith(tld) and x in z:
          debug('found alias alias: ' + x)
          if x not in h:
            h.append(x)
        
        if x in z:
          for y in z[x]:
            debug('found cname alias: ' + y)
            if y not in h:
              h.append(y)

      #add another alias with the tld removed
      for x in h:
        if x.endswith(tld):
          h.append(x[:-len(tld) -1])

      #remove any duplicates
      h = sorted(list(dict.fromkeys(h)))
      
      debug('final list of aliases: ' + ' '.join(h))

      if not p:
        b = findBastion(inv, vpc) 
        debug('bastion host found: ' + str(b))

      print("\nHost", ' '.join(str(s) for s in h))
      print('  ForwardAgent yes')
      print('  StrictHostKeyChecking no')
      if p:
        print('  Hostname ' + instanceProp(inv, inst, "ec2_dns_name"))
        print('  Port ' + p)
      else:
        print('  Hostname ' + instanceProp(inv, inst, "ec2_private_ip_address"))
      if args.sshUser != os.environ.get('USER'):
        print('  User', args.sshUser)
        print('  IdentityFile %s/%s' % (args.sshKeyPATH.rstrip('/'), instanceProp(inv, inst, "ec2_key_name")))
      if b:
        print('  ProxyJump ' + b)
      print('# -->\n')
      debug('')
      debug('')

main()
