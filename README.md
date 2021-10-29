# ec2-bastion-sshconfig
This script will interate over instances found by [`ec2.py`](https://raw.githubusercontent.com/ansible/ansible/stable-1.9/plugins/inventory/ec2.py) and if those instances are not publically accessible it will search the associated VPC for any public instance that can be used as a bastion.  Additionally it will create host aliases for any DNS records found in route53 that match the instance's IP(s) and CNAME records. The resulting output can be added to your `~/.ssh/config`. 

---

## Requirements
This scipt depends on the [`ec2.py`](https://raw.githubusercontent.com/ansible/ansible/stable-1.9/plugins/inventory/ec2.py) script and [`ec2.ini`](https://raw.githubusercontent.com/ansible/ansible/stable-1.9/plugins/inventory/ec2.ini) configuration file to work.  You also need a working `AWS_PROFILE` as expected by the boto module.

---
## Assumptions
* `ec2.py` and `ec2.ini` are installed.
* `group_by_vpc_id = True` in `ec2.ini`
* SSH keys are named on your filesystem to the value of `ec2_key_name`. (You can use symlinks) 

---
## Setup environment
### Create a python environment for testing

```# python3 -m venv ec2-bastion-sshconfig```

### Enter the environment

```# source ec2-bastion-sshconfig/bin/activate```

### Install required python modules

```# pip install -r requirements.txt```

### Set ENV vars
```
# export AWS_PROFILE=default
# export EC2_INI_PATH=/usr/local/etc/ec2.ini
```
---
## Run

```
# ./ec2-bastion-sshconfig.py -h
usage: ec2-bastion-sshconfig.py [-h] [--profile PROFILE] [--ec2Py EC2PY]
                                [--ec2PyINI EC2PYINI] [--sshUser SSHUSER]
                                [--sshKeyPATH SSHKEYPATH] [--sshPort SSHPORT]
                                [--debug DEBUG] [--awsDNSProfile AWSDNSPROFILE]
                                [--tld TLD]

optional arguments:
  -h, --help            show this help message and exit
  --profile PROFILE     Specify AWS credential profile to use.
  --ec2Py EC2PY         inventory script to use.
  --ec2PyINI EC2PYINI   inventory config file to use
  --sshUser SSHUSER     SSH username
  --sshKeyPATH SSHKEYPATH
                        PATH to SSH keys
  --sshPort SSHPORT     Alternate SSH port
  --debug DEBUG         Set to True to enable debug msgs
  --awsDNSProfile AWSDNSPROFILE
                        The AWS profile used to interact with route53
  --tld TLD             tld to append to hostnames
```

| Option | Description | Default |
| ------ | ----------- | ------- |
| `--profile` | `AWS_PROFILE` used to run ec2.py | `$AWS_PROFILE` |
| `--ec2Py` | Full path to the `ec2.py` script | `$PATH` |
| `--ec2PyINI` | Full path to the `ec2.ini` configuration file | `$EC2_INI_PATH` |
| `--sshUser` |  Username to populate the `User` parameter in `~/.ssh/config`. If set the `IdentityFile` parameter will be set to the value of `ec2_key_name` found by `ec2.py`. (requires `--sshKeyPATH`) | `$USER` |
| `--sshKeyPATH` | Full path to local folder containing ssh key files. | `None` |
| `--sshPort` | Alternate port to try in addition to the default SSH port | "22" |
| `--debug` | Show debug messages | `False` |
| `awsDNSProfile` | `AWS_PROFILE` used to read from `route53` | "default"
| `--tld` | DNS zone for which your instances belong | "example.com" |

## Example 
```
# python ./ec2-bastion-sshconfig.py \
  --profile test \
  --ec2Py /usr/local/bin/ec2.py \
  --ec2PyINI /usr/local/etc/ec2.ini \
  --sshUser ec2_user \
  --sshKeyPATH ~/.ssh/ec2_keys \
  --sshPort 2222 \
  --awsDNSProfile default \
  --tld example.com | tee -a ~/.ssh/conf.d/example.com

##################################################
####   vpc-99999999999999999   ###################
##################################################

# <--
Host bastion bastion.example.com i-99999999999999999
  ForwardAgent yes
  StrictHostKeyChecking no
  Hostname 1.2.3.257
  Port 2222
  User ec2_user
  IdentityFile /data/home/username/.ssh/ec2_keys/test.pem
# -->

# <--
Host web-1 web-1.example.com i-99999999999999991
  ForwardAgent yes
  StrictHostKeyChecking no
  Hostname 10.0.0.4
  User ec2_user
  IdentityFile /data/home/username/.ssh/ec2_keys/test.pem
  ProxyJump bastion
# -->

# <--
Host web-2 web-2.example.com i-99999999999999992
  ForwardAgent yes
  StrictHostKeyChecking no
  Hostname 10.0.0.5
  User ec2_user
  IdentityFile /data/home/username/.ssh/ec2_keys/test.pem
  ProxyJump bastion
# -->

```
