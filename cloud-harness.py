#!/usr/bin/env python
# -*- coding: cp1252 -*-

'''
Version: 0.1
Author: Anton Belodedenko (anton@blinkbox.com)
Date: 16/06/2015
Name: Cloud Harness
Git: https://github.com/ab77/cloud-harness

Synopsis:
Python wrapper for cloud service provider APIs/SDKs, supporting:
- Azure Service Management using [Microsoft Azure Python SDK/API](https://github.com/Azure/azure-sdk-for-python)
'''

import time, sys, os, argparse, logging, json, pprint, ConfigParser, hashlib, string, inspect
from datetime import date, timedelta, datetime
from calendar import timegm
from random import SystemRandom, randint
from requests import Session
from xml.etree.ElementTree import Element, SubElement, tostring
from base64 import b64encode
from urlparse import urlsplit, urlunsplit, parse_qs
from urllib import quote_plus

try:
    from azure import *
    from azure.servicemanagement import *
    from azure.storage import AccessPolicy
    from azure.storage.sharedaccesssignature import SharedAccessPolicy, SharedAccessSignature
except ImportError:
    sys.stderr.write('ERROR: Python module "azure" not found, please run "pip install azure".\n')
    sys.exit(1)

def mkdate(dt, format):
    return datetime.strftime(dt, format)

def args():
    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers()    
    azure = sp.add_parser('azure')
    azure.add_argument('provider', action='store_const', const='azure', help=argparse.SUPPRESS)
    azure.add_argument('--action', type=str, nargs=1, required=False, default=[AzureCloudClass.default_action], choices=[a['action'] for a in AzureCloudClass.actions], help='action (default: %s)' % AzureCloudClass.default_action)
    azure.add_argument('--subscription_id', type=str, nargs=1, required=False, default=[AzureCloudClass.default_subscription_id], help='Azure subscription ID (default: %s)' % AzureCloudClass.default_subscription_id)
    azure.add_argument('--certificate_path', type=str, nargs=1, required=False, default=[AzureCloudClass.default_certificate_path], help='Azure management certificate (default: %s)' % AzureCloudClass.default_certificate_path)
    azure.add_argument('--start_date', type=str, nargs=1, default=mkdate(AzureCloudClass.default_start_date, '%Y-%m-%d'), help='start date for list_subscription_operations (default: %s)' % mkdate(AzureCloudClass.default_start_date, '%Y-%m-%d'))
    azure.add_argument('--end_date', type=str, nargs=1, default=mkdate(AzureCloudClass.default_end_date, '%Y-%m-%d'), help='end date for subscription_operations (default: %s)' % mkdate(AzureCloudClass.default_end_date, '%Y-%m-%d'))
    azure.add_argument('--service', type=str, nargs=1, required=False, help='hosted service name')
    azure.add_argument('--account', type=str, nargs=1, required=False, default=[BaseCloudHarnessClass.default_storage_account], help='storage account name (default: %s)' % [BaseCloudHarnessClass.default_storage_account])
    azure.add_argument('--container', type=str, nargs=1, required=False, default=[BaseCloudHarnessClass.default_storage_container], help='storage container name (default: %s)' % [BaseCloudHarnessClass.default_storage_container])
    azure.add_argument('--group', type=str, nargs=1, required=False, help='affinity group name')
    azure.add_argument('--label', type=str, nargs=1, required=False, help='affinity group, disk or role name label')
    azure.add_argument('--description', type=str, nargs=1, required=False, help='affinity group description')
    azure.add_argument('--name', type=str, nargs=1, required=False, help='VM (role) or DNS server name')
    azure.add_argument('--ipaddr', type=str, nargs=1, required=False, help='DNS server IP address')
    azure.add_argument('--image', type=str, nargs=1, required=False, help='OS or data disk image blob name')
    azure.add_argument('--disk', type=str, nargs=1, required=False, help='disk name')
    azure.add_argument('--delete_vhd', action='store_true', required=False, help='delete or keep VHD')
    azure.add_argument('--async', action='store_true', required=False, help='asynchronous operation')
    azure.add_argument('--thumbprint', type=str, nargs=1, required=False, help='certificate thumbprint')    
    azure.add_argument('--request_id', type=str, nargs=1, required=False, help='request ID')    
    azure.add_argument('--status', type=str, nargs=1, required=False, default=[AzureCloudClass.default_status], choices=['Succeeded', 'InProgress', 'Failed'], help='wait for operation status (default %r)' % AzureCloudClass.default_status)
    azure.add_argument('--wait', type=int, nargs=1, required=False, default=[AzureCloudClass.default_wait], help='operation wait time (default %i)' % AzureCloudClass.default_wait)
    azure.add_argument('--timeout', type=int, nargs=1, required=False, default=[AzureCloudClass.default_timeout], help='operation timeout (default %i)' % AzureCloudClass.default_timeout)
    azure.add_argument('--deployment', type=str, nargs=1, required=False, help='deployment name')
    azure.add_argument('--slot', type=str, nargs=1, required=False, default=[AzureCloudClass.default_deployment_slot], help='deployment slot (default %s)' % AzureCloudClass.default_deployment_slot)
    azure.add_argument('--size', type=str, nargs=1, required=False, default=[AzureCloudClass.default_size], help='VM size (default %s)' % AzureCloudClass.default_size)
    azure.add_argument('--disk_size', type=int, nargs=1, required=False, default=[AzureCloudClass.default_disk_size], help='disk size in GB (default %s)' % AzureCloudClass.default_disk_size)
    azure.add_argument('--host_caching', type=str, nargs=1, required=False, default=[AzureCloudClass.default_host_caching], choices=['ReadOnly', 'None', 'ReadOnly', 'ReadWrite'], help='wait for operation status (default %r)' % AzureCloudClass.default_host_caching)
    azure.add_argument('--username', type=str, nargs=1, required=False, default=[AzureCloudClass.default_user_name], help='username for VM deployments (default %s)' % AzureCloudClass.default_user_name)
    azure.add_argument('--password', type=str, nargs=1, required=False, help='password for VM deployments')
    azure.add_argument('--pwd_expiry', type=int, nargs=1, required=False, default=[AzureCloudClass.default_pwd_expiry], help='VMAccess password expiry (default: %i days)' % AzureCloudClass.default_pwd_expiry)
    azure.add_argument('--disable_pwd_auth', action='store_true', required=False, help='disable Linux password authentication')
    azure.add_argument('--ssh_auth', action='store_true', required=False, help='Linux SSH key authentication')
    azure.add_argument('--readonly', action='store_true', required=False, help='limit to read-only operations')
    azure.add_argument('--ssh_public_key_cert', type=str, nargs=1, required=False, default=[AzureCloudClass.default_ssh_public_key_cert], help='Linux SSH certificate with public key path (default %s)' % AzureCloudClass.default_ssh_public_key_cert)
    azure.add_argument('--custom_data_file', type=str, nargs=1, required=False, help='custom data file')
    azure.add_argument('--algorithm', type=str, nargs=1, default=[AzureCloudClass.default_algorithm], required=False, help='Thumprint algorithm (default %s)' % AzureCloudClass.default_algorithm)
    azure.add_argument('--os', type=str, nargs=1, required=False, choices=['Windows', 'Linux'], help='OS type')
    azure.add_argument('--availset', type=str, nargs=1, required=False, help='availability set name')
    azure.add_argument('--network', type=str, nargs=1, required=False, help='virtual network name')
    azure.add_argument('--subnet', type=str, nargs=1, required=False, help='subnet name')
    azure.add_argument('--lun', type=str, nargs=1, required=False, help='logical (disk) unit number (LUN)')
    azure.add_argument('--location', type=str, nargs=1, required=False, help='affinity group location')
    azure.add_argument('--publisher', type=str, nargs=1, required=False, default=[AzureCloudClass.default_publisher], help='resource extension publisher name (default: %s)' % AzureCloudClass.default_publisher)
    azure.add_argument('--extension', type=str, nargs=1, required=False, default=[AzureCloudClass.default_extension], help='resource extension name (default: %s)' % AzureCloudClass.default_extension)
    azure.add_argument('--vmaop', type=str, nargs=1, required=False, default=[AzureCloudClass.default_vmaop], choices=['ResetRDPConfig', 'ResetSSHKey', 'ResetSSHKeyAndPassword', 'ResetPassword', 'DeleteUser', 'ResetSSHConfig'], help='VMAccess operation (default: %s)' % AzureCloudClass.default_vmaop)
    azure.add_argument('--patching_disabled', action='store_true', required=False, help='OSPatching disable patching')
    azure.add_argument('--patching_stop', action='store_true', required=False, help='OSPatching stop patching')
    azure.add_argument('--patching_reboot_after', type=str, nargs=1, required=False, default=[AzureCloudClass.default_patching_reboot_after], choices=['Auto', 'Required', 'NotRequired'], help='OSPatching reboot after patching (default: %s)' % AzureCloudClass.default_patching_reboot_after)
    azure.add_argument('--patching_interval', type=int, nargs=1, required=False, default=[AzureCloudClass.default_patching_interval], help='OSPatching interval (default: %i)' % AzureCloudClass.default_patching_interval)
    azure.add_argument('--patching_day', type=str, nargs=1, required=False, default=[AzureCloudClass.default_patching_day], help='OSPatching patching day (default: %s)' % AzureCloudClass.default_patching_day)
    azure.add_argument('--patching_starttime', type=str, nargs=1, required=False, default=[AzureCloudClass.default_patching_starttime], help='OSPatching patching start time HH:MM (default: one off)')
    azure.add_argument('--patching_category', type=str, nargs=1, required=False, default=[AzureCloudClass.default_patching_category], choices=['ImportantAndRecommended', 'Important'], help='OSPatching patching catgory (default: %s)' % AzureCloudClass.default_patching_category)
    azure.add_argument('--patching_duration', type=str, nargs=1, required=False, default=[AzureCloudClass.default_patching_duration], help='OSPatching patching duration (default: %s)' % AzureCloudClass.default_patching_duration)
    azure.add_argument('--patching_local', action='store_true', required=False, help='OSPatching patching local')
    azure.add_argument('--patching_oneoff', action='store_true', required=False, help='OSPatching patching one-off')
    args = parser.parse_args()
    logger(message=str(args))
    return args

def logger(message=None):
    if BaseCloudHarnessClass.debug: sys.stderr.write('DEBUG %s\n' % repr(message))
    if BaseCloudHarnessClass.log: logging.info('%s\n' % repr(message))         

class BaseCloudHarnessClass():
    debug = True
    log = True
    proxy = True
    ssl_verify = False
    proxy_host = 'localhost'
    proxy_port = 8888
    log_file = '%s' % os.path.basename(__file__).replace('py', 'log')
    config_file = '%s' % os.path.basename(__file__).replace('py', 'conf')
    cp = ConfigParser.SafeConfigParser()        
    try:
        with open(config_file) as cf:
            cp.readfp(cf)
    except IOError:
        pass

    try:
        default_subscription_id = dict(cp.items('AzureConfig'))['default_subscription_id']
        default_certificate_path = dict(cp.items('AzureConfig'))['default_certificate_path']
        default_chef_server_url = dict(cp.items('ChefClient'))['default_chef_server_url']
        default_chef_validation_client_name = dict(cp.items('ChefClient'))['default_chef_validation_client_name']
        default_chef_validation_key_file = dict(cp.items('ChefClient'))['default_chef_validation_key_file']
        default_chef_run_list = dict(cp.items('ChefClient'))['default_chef_run_list']
        default_chef_autoupdate_client = dict(cp.items('ChefClient'))['default_chef_autoupdate_client']
        default_chef_delete_config = dict(cp.items('ChefClient'))['default_chef_delete_config']
        default_chef_ssl_verify_mode = dict(cp.items('ChefClient'))['default_chef_ssl_verify_mode']
        default_chef_verify_api_cert = dict(cp.items('ChefClient'))['default_chef_verify_api_cert']        
        default_windows_customscript_name = dict(cp.items('CustomScriptExtensionForWindows'))['default_windows_customscript_name']
        default_linux_customscript_name = dict(cp.items('CustomScriptExtensionForLinux'))['default_linux_customscript_name']
        default_remote_subnets = cp.items('DefaultEndpointACL')
        default_ssh_public_key_cert = dict(cp.items('LinuxConfiguration'))['default_ssh_public_key_cert']       
        default_ssh_public_key = dict(cp.items('LinuxConfiguration'))['default_ssh_public_key']
        default_linux_custom_data_file = dict(cp.items('LinuxConfiguration'))['default_linux_custom_data_file']
        default_windows_custom_data_file = dict(cp.items('WindowsConfiguration'))['default_windows_custom_data_file']
        default_storage_account = dict(cp.items('AzureConfig'))['default_storage_account']
        default_storage_container = dict(cp.items('AzureConfig'))['default_storage_container']
        default_patching_healthy_test_script = dict(cp.items('OSPatchingExtensionForLinux'))['default_patching_healthy_test_script']        
        default_patching_idle_test_script = dict(cp.items('OSPatchingExtensionForLinux'))['default_patching_idle_test_script']
    except (KeyError, ConfigParser.NoSectionError):
        default_chef_server_url = None
        default_chef_validation_client_name = None
        default_chef_validation_key_file = None
        default_chef_run_list = None
        default_windows_customscript_name = None
        default_linux_customscript_name = None
        default_remote_subnets = None
        default_ssh_public_key_cert = None
        default_ssh_public_key = None
        default_storage_account = None
        default_storage_container = None
        default_chef_autoupdate_client = None
        default_chef_delete_config = None
        default_chef_verify_api_cert = None
        default_chef_ssl_verify_mode = None
        default_patching_healthy_test_script = None
        default_patching_idle_test_script = None
        default_linux_custom_data_file = None
        default_windows_custom_data_file = None
        pass
    
class AzureCloudClass(BaseCloudHarnessClass):
    default_action = 'list_hosted_services'
    actions = [{'action': 'x_ms_version', 'params': [], 'collection': False},
               {'action': 'host', 'params': [], 'collection': False},
               {'action': 'cert_file', 'params': [], 'collection': False},
               {'action': 'content_type', 'params': [], 'collection': False},
               {'action': 'timeout', 'params': [], 'collection': False},
               {'action': 'sub_id', 'params': [], 'collection': False},
               {'action': 'request_session', 'params': [], 'collection': False},
               {'action': 'requestid', 'params': [], 'collection': False},
               {'action': 'list_affinity_groups', 'params': [], 'collection': True},
               {'action': 'list_disks', 'params': [], 'collection': True},
               {'action': 'list_hosted_services', 'params': [], 'collection': True},
               {'action': 'list_locations', 'params': [], 'collection': True},
               {'action': 'list_management_certificates', 'params': [], 'collection': True},
               {'action': 'list_operating_system_families', 'params': [], 'collection': True},
               {'action': 'list_os_images', 'params': [], 'collection': True},
               {'action': 'list_reserved_ip_addresses', 'params': [], 'collection': True},
               {'action': 'list_resource_extension_versions', 'params': [], 'collection': False},
               {'action': 'list_resource_extensions', 'params': [], 'collection': True},
               {'action': 'list_role_sizes', 'params': [], 'collection': True},
               {'action': 'list_service_certificates', 'params': ['service'], 'collection': False},
               {'action': 'list_storage_accounts', 'params': [], 'collection': True},
               {'action': 'list_subscription_operations', 'params': [], 'collection': False},
               {'action': 'list_subscriptions', 'params': [], 'collection': True},
               {'action': 'list_virtual_network_sites', 'params': ['action'], 'collection': True},
               {'action': 'list_vm_images', 'params': [], 'collection': True},
               {'action': 'get_certificate_from_publish_settings', 'params': [], 'collection': False},
               {'action': 'get_storage_account_properties', 'params': [], 'collection': False},
               {'action': 'get_deployment_by_slot', 'params': [], 'collection': False},
               {'action': 'get_deployment_by_name', 'params': [], 'collection': False},
               {'action': 'get_role', 'params': [], 'collection': False},
               {'action': 'get_data_disk', 'params': [], 'collection': False},
               {'action': 'get_disk', 'params': [], 'collection': False},
               {'action': 'get_hosted_service_properties', 'params': [], 'collection': False},
               {'action': 'get_management_certificate', 'params': [], 'collection': False},
               {'action': 'get_operation_status', 'params': [], 'collection': False},
               {'action': 'get_os_image', 'params': [], 'collection': False},
               {'action': 'get_reserved_ip_address', 'params': [], 'collection': False},
               {'action': 'get_service_certificate', 'params': [], 'collection': False},
               {'action': 'get_storage_account_keys', 'params': [], 'collection': False},
               {'action': 'get_subscription', 'params': [], 'collection': False},
               {'action': 'get_affinity_group_properties', 'params': [], 'collection': False},
               {'action': 'get_hosted_service_properties', 'params': [], 'collection': False},
               {'action': 'get_disk_by_role_name', 'params': [], 'collection': False},
               {'action': 'get_endpoint_acl', 'params': [], 'collection': False},
               {'action': 'check_hosted_service_name_availability', 'params': [], 'collection': False},
               {'action': 'check_storage_account_name_availability', 'params': [], 'collection': False},
               {'action': 'create_affinity_group', 'params': [], 'collection': False},
               {'action': 'create_virtual_machine_deployment', 'params': [], 'collection': False},
               {'action': 'delete_affinity_group', 'params': [], 'collection': False},
               {'action': 'update_affinity_group', 'params': [], 'collection': False},
               {'action': 'add_role', 'params': ['deployment', 'service', 'os', 'name', 'image', 'subnet', 'account'], 'collection': False},
               {'action': 'delete_role', 'params': [], 'collection': False},
               {'action': 'delete_disk', 'params': [], 'collection': False},
               {'action': 'delete_deployment', 'params': [], 'collection': False},
               {'action': 'delete_dns_server', 'params': [], 'collection': False},
               {'action': 'wait_for_operation_status', 'params': [], 'collection': False},
               {'action': 'perform_get', 'params': [], 'collection': False},
               {'action': 'perform_put', 'params': [], 'collection': False},
               {'action': 'perform_delete', 'params': [], 'collection': False},
               {'action': 'perform_post', 'params': [], 'collection': False},
               {'action': 'set_endpoint_acl', 'params': ['service', 'deployment', 'name', 'subnet'], 'collection': False},
               {'action': 'reboot_role_instance', 'params': [], 'collection': False},
               {'action': 'start_role', 'params': [], 'collection': False},
               {'action': 'start_roles', 'params': [], 'collection': False},
               {'action': 'restart_role', 'params': [], 'collection': False},
               {'action': 'shutdown_role', 'params': [], 'collection': False},
               {'action': 'shutdown_roles', 'params': [], 'collection': False},
               {'action': 'add_data_disk', 'params': ['service', 'deployment', 'name'], 'collection': False},
               {'action': 'add_disk', 'params': [], 'collection': False},
               {'action': 'add_dns_server', 'params': [], 'collection': False},
               {'action': 'add_management_certificate', 'params': [], 'collection': False},
               {'action': 'add_os_image', 'params': [], 'collection': False},
               {'action': 'add_service_certificate', 'params': [], 'collection': False},
               {'action': 'update_data_disk', 'params': [], 'collection': False},
               {'action': 'update_deployment_status', 'params': [], 'collection': False},
               {'action': 'update_disk', 'params': [], 'collection': False},
               {'action': 'update_dns_server', 'params': [], 'collection': False},
               {'action': 'update_hosted_service', 'params': [], 'collection': False},
               {'action': 'update_os_image', 'params': [], 'collection': False},
               {'action': 'update_role', 'params': ['deployment', 'service', 'name'], 'collection': False},
               {'action': 'update_storage_account', 'params': [], 'collection': False},
               {'action': 'update_vm_image', 'params': [], 'collection': False},
               {'action': 'capture_role', 'params': [], 'collection': False},
               {'action': 'capture_vm_image', 'params': [], 'collection': False},
               {'action': 'upgrade_deployment', 'params': [], 'collection': False},
               {'action': 'change_deployment_configuration', 'params': [], 'collection': False},
               {'action': 'rebuild_role_instance', 'params': [], 'collection': False},
               {'action': 'regenerate_storage_account_keys', 'params': [], 'collection': False},
               {'action': 'reimage_role_instance', 'params': [], 'collection': False},
               {'action': 'rollback_update_or_upgrade', 'params': [], 'collection': False},
               {'action': 'swap_deployment', 'params': [], 'collection': False},
               {'action': 'walk_upgrade_domain', 'params': [], 'collection': False},
               {'action': 'add_customscript_extension', 'params': [], 'collection': False},
               {'action': 'add_chefclient_extension', 'params': [], 'collection': False},
               {'action': 'add_vmaccess_extension', 'params': [], 'collection': False},
               {'action': 'add_ospatching_extension', 'params': [], 'collection': False},
               {'action': 'get_role_properties_xml', 'params': ['deployment', 'service', 'name'], 'collection': False}]

    default_end_date = datetime.now()
    default_start_date = default_end_date - timedelta(days=7)
    default_publisher = 'Microsoft.Compute'
    default_extension = 'CustomScriptExtension'
    default_deployment_slot = 'Production'
    default_size = 'Medium'
    default_disk_size = 30
    default_user_name = 'azureuser'
    default_status = 'Succeeded'
    default_async = False
    default_readonly = False
    default_disable_pwd_auth = False
    default_ssh_auth = False
    default_wait = 15
    default_timeout = 300    
    default_endpoints = {'Windows': [{'LocalPort': '5985',
                                      'Name': 'WinRM',
                                      'Port': str(randint(49152,65535)),
                                      'Protocol': 'tcp'},
                                     {'LocalPort': '5986',
                                      'Name': 'PowerShell',
                                      'Port': str(randint(49152,65535)),
                                      'Protocol': 'tcp'}],
                         'Linux': [{'LocalPort': '22',
                                    'Name': 'SSH',
                                    'Port': str(randint(49152,65535)),
                                    'Protocol': 'tcp'}]}
    default_algorithm = 'SHA1'
    default_chef_autoupdate_client = True
    default_chef_delete_config = False
    default_vmaop = 'ResetPassword'
    default_pwd_expiry = 365
    default_patching_reboot_after = 'Auto'
    default_patching_interval = 1
    default_patching_day = 'Everyday'
    default_patching_starttime = ''
    default_patching_category = 'ImportantAndRecommended'
    default_patching_duration = '03:00'
    default_host_caching = 'ReadWrite'
    
    def __init__(self, subscription_id=None, certificate_path=None):
        self.service = None
        self.group = None
        self.label = None
        self.description = None
        self.name = None
        self.ipaddr = None
        self.image = None
        self.disk = None
        self.thumbprint = None
        self.request_id = None
        self.deployment = None
        self.password = None
        self.os = None
        self.availset = None
        self.network = None
        self.subnet = None
        self.lun = None
        self.location = None
        self.subscription_id = subscription_id or self.default_subscription_id
        self.certificate_path = certificate_path or self.default_certificate_path
        self.default_acl = self.build_default_acl_dict()
        if not self.subscription_id or not self.certificate_path:
            logger('__init__() requires a subscription_id and certificate_path, None specified')
            sys.exit(1)
        else:
            self.sms = ServiceManagementService(self.subscription_id, self.certificate_path, request_session=self.set_proxy())

    def get_optional_params(self, **kwargs):
        key = kwargs['key']
        keys = kwargs['params'].__dict__.keys()
        default = kwargs['default']
        if key in keys and kwargs['params'].__dict__[key] is not None:
            if isinstance(kwargs['params'].__dict__[kwargs['key']], list):
                return kwargs['params'].__dict__[kwargs['key']][0]
            else:
                return kwargs['params'].__dict__[kwargs['key']]
        else:
            return default
        
    def verify_mandatory_params(self, **kwargs): 
        for param in [p['params'] for p in self.actions if p['action'] == kwargs['method']][0]:
            if param not in kwargs['params'].__dict__.keys() or kwargs['params'].__dict__[param] is None:
                logger('%s: not all required parameters %s validated, %s=%s' % (kwargs['method'],
                                                                                [p['params'] for p in self.actions if p['action'] == kwargs['method']][0],
                                                                                param,
                                                                                kwargs['params'].__dict__[param]))
                return False
        return True
            
    def add_role(self, *args, **kwargs):
        arg = args[0]
        try:
            if not self.verify_mandatory_params(method=inspect.stack()[0][3], params=arg):
                return False
            
            self.service = arg.service[0]
            self.deployment = arg.deployment[0]  
            self.name = arg.name[0]
            self.os = arg.os[0]
            self.image = arg.image[0]
            self.account = arg.account[0]
            self.subnet = arg.subnet[0]

            self.container = self.get_optional_params(key='container', params=arg, default='vhds')
            self.label = self.get_optional_params(key='label', params=arg, default=self.name)
            self.availset = self.get_optional_params(key='availset', params=arg, default=None)
            self.password = self.get_optional_params(key='password', params=arg, default=''.join(SystemRandom().choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for _ in range(11)))
            self.slot = self.get_optional_params(key='slot', params=arg, default=self.default_deployment_slot)            
            self.size = self.get_optional_params(key='size', params=arg, default=self.default_size)
            self.username = self.get_optional_params(key='username', params=arg, default=self.default_user_name)        
            self.eps = self.get_optional_params(key='eps', params=arg, default=self.default_endpoints)
            self.rextrs = self.get_optional_params(key='rextrs', params=arg, default=None)
            self.ssh_public_key_cert = self.get_optional_params(key='ssh_public_key_cert', params=arg, default=self.default_ssh_public_key_cert)
            self.async = self.get_optional_params(key='async', params=arg, default=self.default_async)
            self.readonly = self.get_optional_params(key='readonly', params=arg, default=self.default_readonly)                
            self.ssh_auth = self.get_optional_params(key='ssh_auth', params=arg, default=self.default_ssh_auth)                
            self.disable_pwd_auth = self.get_optional_params(key='disable_pwd_auth', params=arg, default=self.default_disable_pwd_auth)                
 
            if self.os == 'Windows':
                self.custom_data_file = self.get_optional_params(key='custom_data_file', params=arg, default=self.default_windows_custom_data_file)
                try:
                    self.custom_data = None                                                    
                    with open(self.custom_data_file, 'rb') as cf:
                        self.custom_data = b64encode(cf.read())
                except IOError:
                    logger('%s: unable to read %s' % (inspect.stack()[0][3], self.custom_data_file))
                    pass

            if self.os == 'Linux':
                self.custom_data_file = self.get_optional_params(key='custom_data_file', params=arg, default=self.default_linux_custom_data_file)
                try:
                    self.custom_data = None                                                    
                    with open(self.custom_data_file, 'rb') as cf:
                        self.custom_data = cf.read()
                except IOError:
                    logger('%s: unable to read %s' % (inspect.stack()[0][3], self.custom_data_file))
                    pass                                                                        

            net_config = ConfigurationSet()
            net_config.configuration_set_type = 'NetworkConfiguration'
            subnet = Subnet()
            subnet.name = self.subnet           
            subnets = Subnets()
            subnets.subnets.append(subnet.name)
            net_config.subnet_names = subnets
           
            endpoints = []                        
            if self.os in ['Windows']:
                self.os_config = WindowsConfigurationSet(computer_name=self.name,
                                                         admin_password=self.password,
                                                         reset_password_on_first_logon=None,
                                                         enable_automatic_updates=None,
                                                         time_zone=None,
                                                         admin_username=self.username,
                                                         custom_data=self.custom_data)
                self.os_config.domain_join = None
                self.os_config.win_rm = None

                for ep in self.eps[self.os]:
                    endpoints.append(ConfigurationSetInputEndpoint(name=ep['Name'],
                                                                   protocol=ep['Protocol'],
                                                                   port=ep['Port'],
                                                                   local_port=ep['LocalPort'],
                                                                   load_balanced_endpoint_set_name=None,
                                                                   enable_direct_server_return=False))                    
                for endpoint in endpoints:
                    net_config.input_endpoints.input_endpoints.append(endpoint)

            endpoints = []                
            if self.os in ['Linux']:
                if self.disable_pwd_auth:
                    self.password = None
                    self.ssh_auth = True
                    
                self.os_config = LinuxConfigurationSet(host_name=self.name,
                                                       user_name=self.username,
                                                       user_password=self.password,
                                                       disable_ssh_password_authentication=self.ssh_auth,
                                                       custom_data=self.custom_data)                    
                if self.ssh_auth:
                    h = hashlib.sha1()
                    try:
                        with open(self.ssh_public_key_cert, 'rb') as cf:
                            h.update(cf.read())
                    except IOError:
                        logger('%s: unable to read %s' % (inspect.stack()[0][3],
                                                          self.ssh_public_key_cert))
                        return False                        
                    ssh = SSH()
                    pks = PublicKeys()
                    pk = PublicKey()
                    pk.path = '/home/%s/.ssh/authorized_keys' % self.username
                    pk.fingerprint = h.hexdigest().upper()
                    pks.public_keys.append(pk)
                    ssh.public_keys = pks
                    self.os_config.ssh = ssh

                for ep in self.eps[self.os]:
                    endpoints.append(ConfigurationSetInputEndpoint(name=ep['Name'],
                                                                   protocol=ep['Protocol'],
                                                                   port=ep['Port'],
                                                                   local_port=ep['LocalPort'],
                                                                   load_balanced_endpoint_set_name=None,
                                                                   enable_direct_server_return=False))
                for endpoint in endpoints:
                    net_config.input_endpoints.input_endpoints.append(endpoint)
                
            self.net_config = net_config            
            ts = mkdate(datetime.now(), '%Y-%m-%d-%H-%M-%S-%f')            
            self.media_link = 'https://%s.blob.core.windows.net/%s/%s-%s-%s-0.vhd' % (self.account,
                                                                                      self.container,
                                                                                      self.service,
                                                                                      self.name,
                                                                                      ts)
            self.disk_config = OSVirtualHardDisk(source_image_name=self.image,
                                                 media_link=self.media_link,
                                                 host_caching=None,
                                                 disk_label=None,
                                                 disk_name=None,
                                                 os=None,
                                                 remote_source_image_link=None)
            pprint.pprint(self.__dict__)
            if not self.readonly:
                try:
                    result = self.sms.add_role(self.service, self.deployment, self.name,
                                               self.os_config, self.disk_config, network_config=self.net_config,
                                               availability_set_name=self.availset, data_virtual_hard_disks=None, role_size=self.size,
                                               role_type='PersistentVMRole', resource_extension_references=self.rextrs, provision_guest_agent=True,
                                               vm_image_name=None, media_location=None)
                    d = dict()
                    operation = self.sms.get_operation_status(result.request_id)
                    d['result'] = result.__dict__
                    d['operation'] = operation.__dict__
                    if not self.async:
                        pprint.pprint(d)
                        return self.wait_for_operation_status(result.request_id)
                    else:
                        return d
                except (WindowsAzureConflictError) as e:
                    logger('%s: operation in progress or resource exists, try again..' % inspect.stack()[0][3])
                    return False
            else:
                logger('%s: limited to read-only operations' % inspect.stack()[0][3])
        except Exception as e:
            logger(message=repr(e))
            return False

    def add_data_disk(self, *args, **kwargs):
        arg = args[0]
        try:
            if not self.verify_mandatory_params(method=inspect.stack()[0][3], params=arg):
                return False
            
            self.service = arg.service[0]
            self.deployment = arg.deployment[0]  
            self.name = arg.name[0]
            self.lun = self.get_optional_params(key='lun',
                                                params=arg,
                                                default=len(self.get_disk_by_role_name(service=self.service,
                                                                                       deployment=self.deployment,
                                                                                       name=self.name)))
            self.image = self.get_optional_params(key='image', params=arg, default=None)
            self.disk = self.get_optional_params(key='disk', params=arg, default=None)
            self.label = self.get_optional_params(key='disk_label', params=arg, default=None)
            self.account = self.get_optional_params(key='account', params=arg, default=self.default_storage_account)
            self.container = self.get_optional_params(key='container', params=arg, default='vhds')       
            self.host_caching = self.get_optional_params(key='host_caching', params=arg, default=self.default_host_caching)
            self.disk_size = self.get_optional_params(key='disk_size', params=arg, default=self.default_disk_size)            
            self.async = self.get_optional_params(key='async', params=arg, default=self.default_async)
            self.readonly = self.get_optional_params(key='readonly', params=arg, default=self.default_readonly)

            ts = mkdate(datetime.now(), '%Y-%m-%d-%H-%M-%S-%f')
            if self.image:
                self.media_link = None
                self.source_media_link = 'https://%s.blob.core.windows.net/%s/%s' % (self.account,
                                                                                     self.container,
                                                                                     self.image)
            else:
                self.source_media_link = None
                self.media_link = 'https://%s.blob.core.windows.net/%s/%s-%s-%s-%s.vhd' % (self.account,
                                                                                           self.container,
                                                                                           self.service,
                                                                                           self.disk,
                                                                                           ts,
                                                                                           self.lun)   
            pprint.pprint(self.__dict__)
            if not self.readonly:
                try:
                    result = self.sms.add_data_disk(self.service, self.deployment, self.name, self.lun,
                                                    host_caching=self.host_caching,
                                                    media_link=self.media_link,
                                                    disk_label=self.label,
                                                    disk_name=self.disk,
                                                    logical_disk_size_in_gb=self.disk_size,
                                                    source_media_link=self.source_media_link)
                    d = dict()
                    operation = self.sms.get_operation_status(result.request_id)
                    d['result'] = result.__dict__
                    d['operation'] = operation.__dict__
                    if not self.async:
                        pprint.pprint(d)
                        return self.wait_for_operation_status(result.request_id)
                    else:
                        return d
                except (WindowsAzureConflictError) as e:
                    logger('%s: operation in progress or resource exists, try again..' % inspect.stack()[0][3])
                    return False
            else:
                logger('%s: limited to read-only operations' % inspect.stack()[0][3])
        except Exception as e:
            logger(message=repr(e))
            return False
        
    def add_disk(self, **kwargs):
        pass
        
    def add_dns_server(self, service=None, deployment=None, name=None, ipaddr=None):
        try:
            if service and deployment and name and ipaddr:
                self.service = service
                self.deployment = deployment
                self.name = name
                self.ipaddr = ipaddr
                result = self.sms.add_dns_server(self.service, self.deployment, self.name, self.ipaddr)        
                if result is not None:
                    d = dict()
                    operation = self.sms.get_operation_status(result.request_id)
                    d['result'] = result.__dict__
                    d['operation'] = operation.__dict__
                    return d
                else:
                    return False
            else:
               logger('add_dns_server() requires service, deployment, DNS server names and IP address, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
    
    def add_management_certificate(self):
        pass
    
    def add_os_image(self):
        pass
    
    def add_service_certificate(self):
        pass
    
    def build_default_acl_dict(self):
        if self.default_remote_subnets:
            l = []
            for subnet in self.default_remote_subnets:
                d = dict()
                d['RemoteSubnet'] = subnet[1]
                d['Description'] = subnet[0]
                l.append(d)
            return l
        else:
            return None

    def build_resource_extensions_xml_from_dict(self, extensions=None):
        self.extensions = (extensions if extensions else None)
        if self.extensions:
            rers = ResourceExtensionReferences()
            for ext in self.extensions:
                rer = ResourceExtensionReference()
                rer.reference_name = ext['Name']
                rer.publisher = ext['Publisher']
                rer.name = ext['Name']
                rer.version = ext['Version']
                repvs = ResourceExtensionParameterValues()
                for param in ext['Parameters']:
                    repv = ResourceExtensionParameterValue()
                    repv.key = param['Key']
                    repv.type = param['Type']
                    repv.value = param['Value']
                    repvs.resource_extension_parameter_values.append(repv)
                rer.resource_extension_parameter_values = repvs
                rer.state = ext['State']
                rers.resource_extension_references.append(rer)
            rextrs = rers
            return rextrs
        else:
            return None

    def build_resource_extension_dict(self, os=None, extension=None, publisher=None,
                                      version=None, pub_config=None, pri_config=None,
                                      pub_config_key=None, pri_config_key=None):
        self.os = (os if os else self.os)
        self.extension = (extension if extension else self.extension)
        self.publisher = (publisher if publisher else self.publisher)
        self.version = (version if version else self.version)
        if self.os and self.extension and self.publisher and self.version:
            rext = {self.os: [{'Name': self.extension,
                               'ReferenceName': self.extension,
                               'Publisher': self.publisher,
                               'Version': self.version,
                               'State': 'Enable',
                               'Parameters': []}]}
            if pub_config and pub_config_key:
                if isinstance(pub_config, dict):
                    pub_config = b64encode(json.dumps(pub_config))
                else:
                    pub_config = b64encode(pub_config)                
                rext[self.os][0]['Parameters'].append({'Key': pub_config_key,
                                                       'Type': 'Public',
                                                       'Value': pub_config})                

            if pri_config and pri_config_key:
                if isinstance(pri_config, dict):
                    pri_config = b64encode(json.dumps(pri_config))
                else:
                    pri_config = b64encode(pri_config)
                rext[self.os][0]['Parameters'].append({'Key': pri_config_key,
                                                       'Type': 'Private',
                                                       'Value': pri_config})                    
            return rext
        else:
            return None

    def build_chefclient_resource_extension(self, chef_server_url=None, chef_validation_client_name=None,
                                            chef_run_list=None, chef_validation_key_file=None, os=None,
                                            chef_autoupdate_client=None, chef_delete_config=None,
                                            chef_ssl_verify_mode=None, chef_verify_api_cert=None):
        self.chef_server_url = (chef_server_url if chef_server_url else self.default_chef_server_url)
        self.chef_validation_client_name = (chef_validation_client_name if chef_validation_client_name else self.default_chef_validation_client_name)
        self.chef_run_list = (chef_run_list if chef_run_list else self.default_chef_run_list)
        self.chef_validation_key_file = (chef_validation_key_file if chef_validation_key_file else self.default_chef_validation_key_file)
        self.chef_autoupdate_client = (chef_autoupdate_client if chef_autoupdate_client else str(self.default_chef_autoupdate_client).lower())
        self.chef_delete_config = (chef_delete_config if chef_delete_config else str(self.default_chef_delete_config).lower())
        self.chef_ssl_verify_mode = (chef_ssl_verify_mode if chef_ssl_verify_mode else self.default_chef_ssl_verify_mode)
        self.chef_verify_api_cert = (chef_verify_api_cert if chef_verify_api_cert else str(self.default_chef_verify_api_cert).lower())
        self.os = (os if os else self.os)
        try:
            if self.os and self.chef_server_url and self.chef_validation_client_name and self.chef_validation_key_file:             
                pub_config = dict()
                pri_config = dict()
                pub_config_key = 'ChefClientPublicConfigParameter'
                pri_config_key = 'ChefClientPrivateConfigParameter'
                self.publisher = 'Chef.Bootstrap.WindowsAzure'
                pub_config = '{"runlist":\"%s\",' \
                             '"autoUpdateClient":"%s",' \
                             '"deleteChefConfig":"%s",' \
                             '"client_rb":"\nchef_server_url\t\\"%s\\"\n' \
                             'validation_client_name\t\\"%s\\"\n' \
                             'node_name\t\\"%s\\"\n' \
                             'ssl_verify_mode\t%s\n' \
                             'verify_api_cert\t%s"}' % (self.chef_run_list,
                                                        self.chef_autoupdate_client,
                                                        self.chef_delete_config,
                                                        self.chef_server_url,
                                                        self.chef_validation_client_name,
                                                        self.name,
                                                        self.chef_ssl_verify_mode,
                                                        self.chef_verify_api_cert)
                try:
                    with open(self.chef_validation_key_file, 'rb') as f:
                        pri_config = '{"validation_key":"%s"}' % f.read()
                except IOError:
                    pri_config['validation_key'] = None
                    pass

                if self.os == 'Windows':
                    self.extension = 'ChefClient'
                    rexts = self.list_resource_extension_versions(publisher=self.publisher, extension=self.extension)
                    version = None
                    for rext in rexts:
                        version = rext['version']                
                    self.version = version.split('.')[0] + '.*'
                    rext = self.build_resource_extension_dict(os=self.os, extension=self.extension, publisher=self.publisher, version=self.version,
                                                              pub_config_key=pub_config_key, pri_config_key=pub_config_key,
                                                              pub_config=pub_config, pri_config=pri_config)
                if self.os == 'Linux':
                    self.extension = 'LinuxChefClient'
                    rexts = self.list_resource_extension_versions(publisher=self.publisher, extension=self.extension)
                    version = None
                    for rext in rexts:
                        version = rext['version']
                    self.version = version.split('.')[0] + '.*'
                    rext = self.build_resource_extension_dict(os=self.os, extension=self.extension, publisher=self.publisher, version=self.version,
                                                              pub_config_key=pub_config_key, pri_config_key=pub_config_key,
                                                              pub_config=pub_config, pri_config=pri_config)
                return self.build_resource_extensions_xml_from_dict(extensions=rext[self.os])
            else:
                logger(pprint.pprint(self.__dict__))
                logger('not all required parameters present for %s' % inspect.stack()[0][3])
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False             

    def build_customscript_resource_extension(self, script=None, os=None,
                                              account=None, container=None):
        try:            
            self.os = (os if os else self.os)
            self.account = (account if account else self.default_storage_account)
            self.container = (container if container else self.default_storage_container)
            if self.os and self.container and self.account:                
                pub_config = dict()
                pub_config_key = 'CustomScriptExtensionPublicConfigParameter'
                if self.os == 'Windows':
                    self.script = (script if script else self.default_windows_customscript_name)
                    pub_config['fileUris'] = ['%s' % self.generate_signed_blob_url(account=self.account,
                                                                                   container=self.container,
                                                                                   script=self.script)]
                    self.extension = 'CustomScriptExtension'
                    self.publisher = 'Microsoft.Compute'
                    rexts = self.list_resource_extension_versions(publisher=self.publisher, extension=self.extension)
                    version = None
                    for rext in rexts:
                        version = rext['version']                
                    self.version = version.split('.')[0] + '.*'
                    pub_config['commandToExecute'] = 'powershell.exe -ExecutionPolicy Unrestricted -File %s' % self.script
                    pub_config['timestamp'] = '%s' % timegm(time.gmtime())                    
                    rext = self.build_resource_extension_dict(os=self.os, extension=self.extension, publisher=self.publisher, version=self.version,
                                                              pub_config_key=pub_config_key, pub_config=pub_config)
                if self.os == 'Linux':
                    pri_config_key = 'CustomScriptExtensionPrivateConfigParameter'
                    pri_config = dict()
                    self.script = (script if script else self.default_linux_customscript_name)
                    self.extension = 'CustomScriptForLinux'
                    self.publisher = 'Microsoft.OSTCExtensions'
                    rexts = self.list_resource_extension_versions(publisher=self.publisher, extension=self.extension)
                    version = None
                    for rext in rexts:
                        version = rext['version']          
                    self.version = version.split('.')[0] + '.*' 
                    pub_config['fileUris'] = ['%s' % self.generate_signed_blob_url(account=self.account,
                                                                                   container=self.container,
                                                                                   script=self.script)]               
                    pub_config['commandToExecute'] = './%s' % self.script
                    pub_config['timestamp'] = '%s' % timegm(time.gmtime())
                    pri_config['storageAccountName'] = self.account
                    pri_config['storageAccountKey'] = self.get_storage_account_keys(account=self.account)['storage_service_keys']['primary']
                    rext = self.build_resource_extension_dict(os=self.os, extension=self.extension, publisher=self.publisher, version=self.version,
                                                              pub_config_key=pub_config_key, pub_config=pub_config,
                                                              pri_config_key=pri_config_key, pri_config=pri_config)
                return self.build_resource_extensions_xml_from_dict(extensions=rext[self.os])
            else:
                logger(pprint.pprint(self.__dict__))
                logger('not all required parameters present for %s' % inspect.stack()[0][3])
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def build_vmaccess_resource_extension(self, username=None, os=None, reset_ssh=True,
                                          password=None, ssh_public_key=None, vmaop=None,
                                          pwd_expiry=None):
        self.reset_ssh = reset_ssh
        self.os = (os if os else self.os)
        self.username = (username if username else self.default_user_name)
        self.password = (password if password else self.password)
        self.vmaop = (vmaop if vmaop else self.default_vmaop)
        self.ssh_public_key = (ssh_public_key if ssh_public_key else self.default_ssh_public_key)
        self.pwd_expiry = (pwd_expiry if pwd_expiry else self.default_pwd_expiry)
        try:   
            if self.os:
                pub_config = dict()
                pri_config = dict() 
                if self.os == 'Windows':                   
                    pub_config_key = 'VMAccessAgentPublicConfigParameter'
                    pri_config_key = 'VMAccessAgentPrivateConfigParameter'
                    self.extension = 'VMAccessAgent'
                    self.publisher = 'Microsoft.Compute'
                    rexts = self.list_resource_extension_versions(publisher=self.publisher, extension=self.extension)
                    version = None
                    for rext in rexts:
                        version = rext['version']          
                    self.version = version.split('.')[0] + '.*'
                    pub_config['timestamp'] = '%s' % timegm(time.gmtime())

                    if self.vmaop == 'ResetRDPConfig':
                        pass                    

                    elif self.vmaop == 'ResetPassword':
                        if self.password:
                            pub_config['UserName'] = self.username
                            pri_config['Password'] = self.password
                            pri_config['expiration'] = mkdate(datetime.now() + timedelta(days=self.pwd_expiry), '%Y-%m-%d')
                        else:                            
                            logger(pprint.pprint(self.__dict__))
                            logger('VMAccess operation %s requires a new password' % self.vmaop)
                            sys.exit(1)
                    else:
                        logger(pprint.pprint(self.__dict__))
                        logger('%s is not a supported VMAccess operation' % self.vmaop)
                        sys.exit(1)
                    rext = self.build_resource_extension_dict(os=self.os, extension=self.extension, publisher=self.publisher, version=self.version,
                                                              pub_config_key=pub_config_key, pub_config=pub_config,
                                                              pri_config_key=pri_config_key, pri_config=pri_config)
                
                if self.os == 'Linux':
                    pub_config_key = 'VMAccessForLinuxPublicConfigParameter'
                    pri_config_key = 'VMAccessForLinuxPrivateConfigParameter'
                    self.extension = 'VMAccessForLinux'
                    self.publisher = 'Microsoft.OSTCExtensions'
                    rexts = self.list_resource_extension_versions(publisher=self.publisher, extension=self.extension)
                    version = None
                    for rext in rexts:
                        version = rext['version']          
                    self.version = version.split('.')[0] + '.*'
                    pub_config['timestamp'] = '%s' % timegm(time.gmtime())
                    with open(self.ssh_public_key, 'rb') as cf:
                        ssh_cert = cf.read()
                        
                    if self.vmaop == 'ResetSSHKey':
                        pri_config['username'] = self.username
                        pri_config['ssh_key'] = ssh_cert                        

                    elif self.vmaop == 'ResetPassword':
                        if self.password:
                            pri_config['username'] = self.username
                            pri_config['password'] = self.password
                            pri_config['expiration'] = mkdate(datetime.now() + timedelta(days=self.pwd_expiry), '%Y-%m-%d')
                        else:                            
                            logger(pprint.pprint(self.__dict__))
                            logger('VMAccess operation %s requires a new password' % self.vmaop)
                            sys.exit(1)

                    elif self.vmaop == 'ResetSSHKeyAndPassword':
                        if self.password:
                            pri_config['username'] = self.username
                            pri_config['password'] = self.password
                            pri_config['ssh_key'] = ssh_cert
                        else:                            
                            logger(pprint.pprint(self.__dict__))
                            logger('VMAccess operation %s requires a new password' % self.vmaop)
                            sys.exit(1)

                    elif self.vmaop == 'DeleteUser':
                        pri_config['remove_user'] = self.username

                    elif self.vmaop == 'ResetSSHConfig':
                        pri_config['reset_ssh'] = self.reset_ssh

                    else:
                        logger(pprint.pprint(self.__dict__))
                        logger('%s is not a supported VMAccess operation' % self.vmaop)
                        sys.exit(1)
                    rext = self.build_resource_extension_dict(os=self.os, extension=self.extension, publisher=self.publisher, version=self.version,
                                                              pri_config_key=pri_config_key, pri_config=pri_config)
                return self.build_resource_extensions_xml_from_dict(extensions=rext[self.os])
            else:
                logger(pprint.pprint(self.__dict__))
                logger('not all required parameters present for %s' % inspect.stack()[0][3])
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def build_ospatching_resource_extension(self, os=None, patching_disabled=False, patching_stop=False,
                                            patching_reboot_after=None, patching_interval=None, patching_day=None,
                                            patching_starttime=None, patching_category=None, patching_duration=None,
                                            account=None, patching_healthy_test_script=None, patching_idle_test_script=None,
                                            patching_local=False, patching_oneoff=False):
        self.os = (os if os else self.os)
        self.account = (account if account else self.default_storage_account)
        self.patching_disabled = patching_disabled
        self.patching_stop = patching_stop
        self.patching_local = patching_local
        self.patching_oneoff = patching_oneoff
        self.patching_reboot_after = (patching_reboot_after if patching_reboot_after else self.default_patching_reboot_after)
        self.patching_interval = (patching_interval if patching_interval else self.default_patching_interval)
        self.patching_day = (patching_day if patching_day else self.default_patching_day)
        self.patching_starttime = (patching_starttime if patching_starttime else self.default_patching_starttime)
        self.patching_category = (patching_category if patching_category else self.default_patching_category)
        self.patching_duration = (patching_duration if patching_duration else self.default_patching_duration)
        self.patching_healthy_test_script = (patching_healthy_test_script if patching_healthy_test_script else self.default_patching_healthy_test_script)
        self.patching_idle_test_script = (patching_idle_test_script if patching_idle_test_script else self.default_patching_idle_test_script)
        try:   
            if self.os:                
                if self.os == 'Windows':
                    logger(pprint.pprint(self.__dict__))
                    logger('%s is not supported in Windows' % inspect.stack()[0][3])
                    sys.exit(1)
                
                if self.os == 'Linux':
                    pub_config = dict()
                    pri_config = dict() 
                    pub_config_key = 'OSPatchingForLinuxPublicConfigParameter'                   
                    pri_config_key = 'OSPatchingForLinuxPrivateConfigParameter'
                    self.extension = 'OSPatchingForLinux'
                    self.publisher = 'Microsoft.OSTCExtensions'
                    rexts = self.list_resource_extension_versions(publisher=self.publisher, extension=self.extension)
                    version = None
                    for rext in rexts:
                        version = rext['version']          
                    self.version = version.split('.')[0] + '.*'
                    pub_config['timestamp'] = '%s' % timegm(time.gmtime())
                    pub_config['disabled'] = self.patching_disabled
                    pub_config['stop'] = self.patching_stop
                    pub_config['rebootAfterPatch'] = self.patching_reboot_after
                    pub_config['intervalOfWeeks'] = self.patching_interval
                    pub_config['dayOfWeek'] = self.patching_day
                    pub_config['startTime'] = self.patching_starttime
                    pub_config['category'] = self.patching_category
                    pub_config['installDuration'] = self.patching_duration
                    pub_config['idleTestScript'] = self.patching_idle_test_script
                    pub_config['healthyTestScript'] = self.patching_healthy_test_script
                    pub_config['vmStatusTest'] = {'local': self.patching_local,
                                                  'idleTestScript': self.patching_idle_test_script,
                                                  'healthyTestScript': self.patching_healthy_test_script}
                    pub_config['oneoff'] = self.patching_oneoff
                    pri_config['storageAccountName'] = self.account
                    pri_config['storageAccountKey'] = self.get_storage_account_keys(account=self.account)['storage_service_keys']['primary']
                    rext = self.build_resource_extension_dict(os=self.os, extension=self.extension, publisher=self.publisher, version=self.version,
                                                              pub_config_key=pub_config_key, pub_config=pub_config,
                                                              pri_config_key=pri_config_key, pri_config=pri_config)
                return self.build_resource_extensions_xml_from_dict(extensions=rext[self.os])
            else:
                logger(pprint.pprint(self.__dict__))
                logger('not all required parameters present for %s' % inspect.stack()[0][3])
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def build_dsc_resource_extension(self):
        pass

    def build_docker_resource_extension(self):
        pass
    
    def build_logcollector_resource_extension(self):
        pass
    
    def build_vsreleasemanager_resource_extension(self):
        pass
    
    def build_vsremotedebug_resource_extension(self):
        pass
    
    def build_octopusdeploy_resource_extension(self):
        pass
    
    def build_puppet_resource_extension(self):
        pass
    
    def build_bginfo_resource_extension(self):
        pass
    
    def build_monitoringagent_resource_extension(self):
        pass
    
    def build_sqlagent_resource_extension(self):
        pass
    
    def build_antimalware_resource_extension(self):
        pass
    
    def cert_file(self):
        return self.sms.cert_file
    
    def content_type(self):
        return self.sms.content_type

    def check_hosted_service_name_availability(self, service=None):
        if service:
            self.service = service
            result = self.sms.check_hosted_service_name_availability(self.service)
            return result.__dict__
        else:
            logger('check_hosted_service_name_availability() requires a service name, None specified')

    def check_storage_account_name_availability(self, account=None):
        try:
            if account:
                self.account = account
                result = self.sms.check_storage_account_name_availability(self.account)
                return result.__dict__
            else:
                logger('check_storage_account_name_availability() requires a storage account name, None specified')
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
        
    def create_affinity_group(self, group=None, label=None, description=None, location=None):
        try: 
            if group and label and location:
                self.group = group
                self.label = label
                self.description = description
                self.location = location
                result = self.sms.create_affinity_group(name=self.group,
                                                        label=self.label,
                                                        location=self.location,
                                                        description=self.description)
                return True
            else:
                logger('create_affinity_group() requires a name, label and location, None specified')
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def create_virtual_machine_deployment(self, deployment=None, service=None, slot=None,
                 label=None, size=None, os=None, availset=None,
                 network=None, rextrs=None, name=None,
                 username=None, password=None, image=None,
                 subnet=None, account=None, eps=None, async=None):
        pass

    def capture_role(self):
        pass
    
    def capture_vm_image(self):
        pass

    def create_deployment(self):
        pass

    def create_hosted_service(self, service=None, label=None, description=None,
                              location=None, affinity_group=None, extended_properties=None):
        pass
    
    def create_reserved_ip_address(self):
        pass
    
    def create_storage_account(self):
        pass
    
    def create_vm_image(self):
        pass

    def delete_affinity_group(self, group=None):
        if group:
            self.group = group
            try:
                result = self.sms.delete_affinity_group(self.group)
            except Exception as e:
                logger(message=repr(e))
                return False
            return True
        else:
            logger('delete_affinity_group() requires a group name, None specified')

    def delete_role(self, service=None, deployment=None,
                    async=None, name=None):
        try:
            if service and deployment and name:
                self.service = service                
                self.deployment = deployment
                self.name = name
                self.async = async
                result = self.sms.delete_role(self.service, self.deployment, self.name)
                if result is not None:
                    d = dict()
                    operation = self.sms.get_operation_status(result.request_id)
                    d['result'] = result.__dict__
                    d['operation'] = operation.__dict__
                    if not self.async:
                        pprint.pprint(d)
                        return self.wait_for_operation_status(result.request_id)
                    else:
                        return d
                else:
                    return False
            else:
               logger('delete_role() requires service, deployment and role names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False    

    def delete_disk(self, disk, delete_vhd=None):
        try:
            if disk:
                self.disk = disk
                self.delete_vhd = delete_vhd
                result = self.sms.delete_disk(self.disk, delete_vhd=self.delete_vhd)
                return True
            else:
               logger('delete_disk() requires a disk name, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
    
    def delete_dns_server(self, service=None, deployment=None, name=None):
        try:
            if service and deployment and name:
                self.service = service
                self.deployment = deployment
                self.name = name
                result = self.sms.delete_dns_server(self.service, self.deployment, self.name)        
                if result is not None:
                    d = dict()
                    operation = self.sms.get_operation_status(result.request_id)
                    d['result'] = result.__dict__
                    d['operation'] = operation.__dict__
                    return d
                else:
                    return False
            else:
               logger('delete_dns_server() requires service, deployment and DNS server names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
    
    def delete_hosted_service(self):
        pass
    
    def delete_management_certificate(self):
        pass
    
    def delete_os_image(self):
        pass
    
    def delete_reserved_ip_address(self):
        pass
    
    def delete_role_instances(self):
        pass
    
    def delete_service_certificate(self):
        pass
    
    def delete_storage_account(self):
        pass
    
    def delete_vm_image(self):
        pass
    
    def delete_data_disk(self):
        pass
    
    def delete_deployment(self, service=None, deployment=None, delete_vhd=None):
        try:
            if service and deployment:
                self.service = service
                self.deployment = deployment
                self.delete_vhd = delete_vhd
                result = self.sms.delete_deployment(self.service, self.deployment, delete_vhd=self.delete_vhd)
                return True
            else:
               logger('delete_deployment() requires service and deployment names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def generate_signed_blob_url(self, account=None, container=None, script=None):
        try:
            self.account = (account if account else self.default_storage_account)
            self.container = (container if container else self.default_storage_container)
            self.script = (script if script else self.default_windows_customscript_name)            
            if container and script and account:
                key = self.get_storage_account_keys(account=account)['storage_service_keys']['primary']       
                sas = SharedAccessSignature(account_name=self.account,account_key=key)
                ap = AccessPolicy()
                ap.expiry = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%S:%MZ')
                ap.permission = 'r'
                sap = SharedAccessPolicy(ap)
                path = '/%s/%s' % (container, script)                
                query = sas.generate_signed_query_string(path, 'b', sap)
                url = 'https://%s.blob.core.windows.net%s?%s' % (self.account,
                                                                 path,
                                                                 query)
                return self.urlencode_sig_query_string_part(url)               
            else:
               logger('generate_signed_blob_url() requires an account, container and script names, None specified or found in the configuration file')
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None

    def get_certificate_from_publish_settings(self):
        subscription_id = get_certificate_from_publish_settings(publish_settings_path='MyAccount.PublishSettings',
                                                                path_to_write_certificate=self.default_certificate_path,
                                                                subscription_id=self.subscription_id)
        return subscription_id

    def get_storage_account_properties(self, account=None):        
        try:            
            if account:
                self.account = account
                account = self.sms.get_storage_account_properties(self.account)
                d = account.__dict__
                d['storage_service_properties'] = account.storage_service_properties.__dict__
                return d
            else:
                logger('get_storage_account_properties() requires a storage account name, None specified')
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None

    def get_affinity_group_properties(self, group=None):
        try:            
            if group:
                self.group = group
                group = self.sms.get_affinity_group_properties(self.group)
                d = group.__dict__
                d['hosted_services'] = group.hosted_services.__dict__
                d['storage_services'] = group.storage_services.__dict__
                return d
            else:
                logger('get_affinity_group_properties() requires a group name, None specified')
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None

    def get_endpoint_acl(self, subscription_id=None, service=None, deployment=None, name=None):
        try:
            if service and deployment and name:
                self.service = service                
                self.deployment = deployment
                self.name = name
                self.subscription_id = subscription_id
                if not self.subscription_id: self.subsciption_id = self.default_subscription_id
                path = '/%s/services/hostedservices/%s/deployments/%s/roles/%s' % (self.subscription_id,
                                                                                   self.service,
                                                                                   self.deployment,
                                                                                   self.name)
                return self.perform_get(path)
            else:
               logger('get_endpoint_acl() requires service, deployment and role names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None

    def get_deployment_by_name(self, service=None, deployment=None):
        try:
            if service and deployment:
                self.service = service
                self.deployment = deployment            
                deployment = self.sms.get_deployment_by_name(self.service, self.deployment)
                d = deployment.__dict__    
                return d
            else:
               logger('get_deployment_by_name() requires service and deployment names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None    
    
    def get_deployment_by_slot(self, service=None, slot=None):
        try:
            if service:
                self.service = service
                if not slot: slot = self.default_deployment_slot
                self.slot = slot                
                deployment = self.sms.get_deployment_by_slot(self.service, self.slot)
                d = deployment.__dict__    
                return d
            else:
               logger('get_deployment_by_slot() requires a service name, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None
        
    def get_role(self, service=None, deployment=None, name=None):
        try:
            if service and deployment and name:
                self.service = service                
                self.deployment = deployment
                self.name = name
                role = self.sms.get_role(self.service, self.deployment, self.name)
                d = role.__dict__
                d['configuration_sets'] = [el.__dict__ for el in role.configuration_sets if el]
                return d
            else:
               logger('get_role() requires service, deployment and role names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None

    def get_data_disk(self, service=None, deployment=None, name=None, lun=None):
        try:
            if service and deployment and name:
                self.service = service                
                self.deployment = deployment
                self.name = name
                self.lun = lun
                disk = self.sms.get_data_disk(self.service, self.deployment, self.name, self.lun)
                d = disk.__dict__
                return d
            else:
               logger('get_data_disk() requires service, deployment and role names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None
    
    def get_disk(self, disk=None):
        try:
            if disk:
                self.disk = disk                
                role = self.sms.get_disk(self.disk)
                d = role.__dict__
                return d
            else:
               logger('get_disk() requires a disk name, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None

    def get_hosted_service_properties(self, service, embed_detail=False):
        try:
            if service:
                self.service = service                
                service = self.sms.get_hosted_service_properties(self.service)
                d = service.__dict__
                return d
            else:
               logger('get_hosted_service_properties() requires a service name, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None

    def get_management_certificate(self, thumbprint=None):
        try:
            if thumbprint:
                self.thumbprint = thumbprint                
                thumbprint = self.sms.get_management_certificate(self.thumbprint)
                d = thumbprint.__dict__
                return d
            else:
               logger('get_management_certificate() requires a certificate thumbprint, None specified')
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None
        
    def get_operation_status(self, request_id=None):
        try:
            if request_id:
                self.request_id = request_id                
                operation = self.sms.get_operation_status(self.request_id)
                d = operation.__dict__
                if d['error']: d['error'] = operation.error.__dict__
                return d
            else:
                logger('get_operation_status() requires a request ID, None specified')
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None        

    def get_os_image(self):
        pass

    def get_reserved_ip_address(self):
        pass

    def get_service_certificate(self, service=None, algorithm=None, thumbprint=None):
        try:
            self.service = (service if service else None)
            self.algorithm = (algorithm if algorithm else self.default_algorithm)
            self.thumbprint = (thumbprint if thumbprint else None)            
            if self.service and self.algorithm and self.thumbprint:
                result = self.sms.get_service_certificate(self.service, self.algorithm, self.thumbprint)
                return result.__dict__
            else:
                logger('get_service_certificate() requires service, algorithm and thumbprint, None specified')
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None
        
    def get_storage_account_keys(self, account=None):
        try:
            self.account = (account if account else None)          
            if self.account:
                result = self.sms.get_storage_account_keys(self.account)
                d = result.__dict__
                d['storage_service_keys'] = result.storage_service_keys.__dict__
                return d
            else:
                logger('get_storage_account_keys() requires a storage account name, None specified')
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None

    def get_subscription(self):
        pass

    def get_disk_by_role_name(self, service=None, deployment=None, name=None):
        try:
            if name:
                self.service = service                
                self.deployment = deployment
                self.name = name
                disks = self.list_disks()
                try:
                    d = [k for k in disks if k is not None and k['attached_to']['role_name'] == self.name and k['attached_to']['deployment_name'] == self.deployment and k['attached_to']['hosted_service_name'] == self.service]
                except TypeError:
                    d = None
                    pass
                if d is not None:
                    return d
                else:
                    return None
            else:
               logger('get_disk_by_role_name() requires service, deployment and role names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def host(self):
        return self.sms.host

    def list_resource_extension_versions(self, *args, **kwargs):
        arg = args[0]
        try:
            if not self.verify_mandatory_params(method=inspect.stack()[0][3], params=arg):
                return False

            self.publisher = self.get_optional_params(key='publisher', params=arg, default=self.default_publisher)           
            self.extension = self.get_optional_params(key='extension', params=arg, default=self.default_extension)           

            pprint.pprint(self.__dict__)
            versions = self.sms.list_resource_extension_versions(self.publisher, self.extension)
            l = []
            for version in versions:
                l.append(self.dict_from_response_obj(version))
            return l
        except Exception as e:
            logger(message=repr(e))
            return False
       
    def list_service_certificates(self, *args, **kwargs):
        arg = args[0]
        try:
            if not self.verify_mandatory_params(method=inspect.stack()[0][3], params=arg):
                return False

            self.service = arg.service[0]
            pprint.pprint(self.__dict__)            
            certificates = self.sms.list_service_certificates(self.service)
            l = []
            for certificate in certificates:
                l.append(self.dict_from_response_obj(certificate))
            return l
        except Exception as e:
            logger(message=repr(e))
            return False

    def list_subscription_operations(self, *args, **kwargs):
        arg = args[0]
        try:
            if not self.verify_mandatory_params(method=inspect.stack()[0][3], params=arg):
                return False

            self.start_date = self.get_optional_params(key='start_date', params=arg, default=self.default_start_date)           
            self.end_date = self.get_optional_params(key='end_date', params=arg, default=self.default_end_date)
            
            pprint.pprint(self.__dict__)
            operations = self.sms.list_subscription_operations(self.start_date, self.end_date)
            l = []        
            for operation in operations.subscription_operations:
                l.append(self.dict_from_response_obj(operation))
            return l    
        except Exception as e:
            logger(message=repr(e))
            return False

    def dict_from_response_obj(self, *args, **kwargs):
        
        def recurse_dict(d):
            for k, v in d.iteritems():
                if isinstance(v, dict):
                    recurse_dict(v)
            else:
                return v

        obj = args[0]

        if not isinstance(obj, dict):
            obj = self.dict_from_response_obj(obj.__dict__)

        for k, v in obj.iteritems():
            if '__dict__' in dir(v):
                obj[k] = v.__dict__
                obj = self.dict_from_response_obj(obj)
            if isinstance(v, dict):
                obj[k] = recurse_dict(v)            
            if isinstance(v, list):
                l = []
                for el in v:
                    if isinstance(el, unicode):
                        l.append(el)
                    elif not isinstance(el, dict):                        
                        l.append(el.__dict__)                        
                        obj[k] = l
        return obj
    
    def list_collection(self, *args, **kwargs):
        try:
            arg = args[0]
            if not self.verify_mandatory_params(method=arg.action[0], params=arg):
                return False

            self.action = arg.action[0]

            pprint.pprint(self.__dict__)
            method = getattr(self.sms, self.action)
            results = method()
            l = []
            for item in results:
                l.append(self.dict_from_response_obj(item))
            return l
        except Exception as e:
            logger(message=repr(e))
            return False        

    def perform_get(self, path=None):
        try:
            if path:
                self.path = path
                response = self.sms.perform_get(self.path, x_ms_version=self.sms.x_ms_version)        
                if response is not None:
                    return response.__dict__
                else:
                    return None
            else:
               logger('perform_get() requires URL path, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def get_role_properties_xml(self, **kwargs):
        try:
            if not self.verify_mandatory_params(method='get_role_properties_xml', params=kwargs):
                return False
            
            self.service = kwargs['service']
            self.deployment = kwargs['deployment']     
            self.name = kwargs['name']
            self.path = '/%s/services/hostedservices/%s/deployments/%s/roles/%s' % (self.default_subscription_id,
                                                                                    self.service,
                                                                                    self.deployment,
                                                                                    self.name)
            response = self.sms.perform_get(self.path, x_ms_version=self.sms.x_ms_version)
            if response is not None:
                return response.__dict__
            else:
                return None
        except Exception as e:
            logger(message=repr(e))
            return False        

    def perform_delete(self, path=None):
        try:
            if path:
                self.path = path
                response = self.sms.perform_delete(self.path, x_ms_version=self.sms.x_ms_version)        
                if response is not None:
                    return response.__dict__
                else:
                    return None
            else:
               logger('perform_delete() requires URL path, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
    
    def perform_post(self, path=None, body=None):
        try:
            if path and body:
                self.path = path
                response = self.sms.perform_post(self.path, self.body, x_ms_version=self.sms.x_ms_version)        
                if response is not None:
                    return response.__dict__
                else:
                    return None
            else:
               logger('perform_post() requires URL path and body, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
    
    def perform_put(self, path=None, body=None):
        try:
            if path and body:
                self.path = path
                self.body = body
                response = self.sms.perform_put(self.path, self.body, x_ms_version=self.sms.x_ms_version)        
                if response is not None:
                    return response.__dict__
                else:
                    return None
            else:
               logger('perform_put() requires URL path and body, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def rebuild_role_instance(self):
        pass
    
    def regenerate_storage_account_keys(self):
        pass
    
    def reimage_role_instance(self):
        pass
    
    def rollback_update_or_upgrade(self):
        pass
    
    def reboot_role_instance(self, service=None, deployment=None, name=None):
        try:
            if service and deployment and name:
                self.service = service
                self.deployment = deployment
                self.name = name
                result = self.sms.reboot_role_instance(self.service, self.deployment, self.name)
                d = dict()
                operation = self.sms.get_operation_status(result.request_id)
                d['result'] = result.__dict__
                d['operation'] = operation.__dict__
                return d
            else:
               logger('reboot_role_instance() requires service, deployment and role names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
    
    def start_role(self, service=None, deployment=None, name=None):
        try:
            if service and deployment and name:
                self.service = service
                self.deployment = deployment
                self.name = name
                result = self.sms.start_role(self.service, self.deployment, self.name)
                d = dict()
                operation = self.sms.get_operation_status(result.request_id)
                d['result'] = result.__dict__
                d['operation'] = operation.__dict__
                return d
            else:
               logger('start_role() requires service, deployment and role names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
    
    def start_roles(self, service=None, deployment=None, names=None):
        try:
            if service and deployment and names:
                self.service = service
                self.deployment = deployment
                self.names = names
                result = self.sms.start_roles(self.service, self.deployment, self.names)
                d = dict()
                operation = self.sms.get_operation_status(result.request_id)
                d['result'] = result.__dict__
                d['operation'] = operation.__dict__
                return d
            else:
               logger('start_roles() requires service, deployment names and role names iterable, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
                             
    def restart_role(self, service=None, deployment=None, name=None):
        try:
            if service and deployment and name:
                self.service = service
                self.deployment = deployment
                self.name = name
                result = self.sms.restart_role(self.service, self.deployment, self.name)
                d = dict()
                operation = self.sms.get_operation_status(result.request_id)
                d['result'] = result.__dict__
                d['operation'] = operation.__dict__
                return d
            else:
               logger('restart_role() requires service, deployment and role names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def request_session(self):
        return self.sms.request_session
    
    def requestid(self):        
        return self.sms.requestid

    def set_proxy(self):
        if self.proxy:
            s = Session()
            s.cert = self.default_certificate_path
            s.verify = self.ssl_verify
            s.proxies = {'http' : 'http://%s:%i' % (self.proxy_host, self.proxy_port),
                         'https': 'https://%s:%i' % (self.proxy_host, self.proxy_port)}
            return s
        else:
            return None

    def sub_id(self):
        return self.sms.subscription_id
    
    def shutdown_role(self, service=None, deployment=None, name=None):
        try:
            if service and deployment and name:
                self.service = service
                self.deployment = deployment
                self.name = name
                result = self.sms.shutdown_role(self.service, self.deployment, self.name)
                d = dict()
                operation = self.sms.get_operation_status(result.request_id)
                d['result'] = result.__dict__
                d['operation'] = operation.__dict__
                return d
            else:
               logger('shutdown_role() requires service, deployment and role names, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
                             
    def shutdown_roles(self, service=None, deployment=None, names=None):
        try:
            if service and deployment and names:
                self.service = service
                self.deployment = deployment
                self.names = names
                result = self.sms.shutdown_roles(self.service, self.deployment, self.names)
                d = dict()
                operation = self.sms.get_operation_status(result.request_id)
                d['result'] = result.__dict__
                d['operation'] = operation.__dict__
                return d
            else:
               logger('shutdown_roles() requires service, deployment names and role names iterable, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
   
    def swap_deployment(self):
        pass

    def set_endpoint_acl(self, *args, **kwargs):
        arg = args[0]
        try:
            if not self.verify_mandatory_params(method=inspect.stack()[0][3], params=arg):
                return False
            
            self.service = arg.service[0]
            self.deployment = arg.deployment[0]  
            self.name = arg.name[0]
            self.os = self.get_os_for_role(name=self.name, service=self.service, deployment=self.deployment)
            self.subnet = arg.subnet[0]
            
            self.readonly = self.get_optional_params(key='readonly', params=arg, default=self.default_readonly)
            self.acls = self.get_optional_params(key='acls', params=arg, default=self.default_acl)
            self.eps = self.get_optional_params(key='eps', params=arg, default=self.default_endpoints[self.os])
            
            ep_xml_template = \
            '''
            <PersistentVMRole xmlns="http://schemas.microsoft.com/windowsazure">
                    <RoleName>%s</RoleName>
                    <RoleType>PersistentVMRole</RoleType>
                    <ConfigurationSets>
                            <ConfigurationSet>
                                    <ConfigurationSetType>NetworkConfiguration</ConfigurationSetType>
                                    %s
                                    <SubnetNames>
                                            <SubnetName>%s</SubnetName>
                                    </SubnetNames>
                            </ConfigurationSet>
                    </ConfigurationSets>
                    <ResourceExtensionReferences />
                    <DataVirtualHardDisks />
                    <OSVirtualHardDisk />
                    <RoleSize>Small</RoleSize>
                    <ProvisionGuestAgent>true</ProvisionGuestAgent>
            </PersistentVMRole>
            ''' % (self.name,
                   self.xml_endpoint_fragment_from_dict(self.eps, self.acls),
                   self.subnet)
            
            path = '/%s/services/hostedservices/%s/deployments/%s/roles/%s' % (self.subscription_id,
                                                                               self.service,
                                                                               self.deployment,
                                                                               self.name)
            pprint.pprint(self.__dict__)
            if not self.readonly:                        
                return self.perform_put(path, ep_xml_template)
            else:
                logger('%s: limited to read-only operations' % inspect.stack()[0][3])                
        except Exception as e:
            logger(message=repr(e))
            return False

    def timeout(self):
        return self.sms.timeout
    
    def upgrade_deployment(self):
        pass
    
    def change_deployment_configuration(self):
        pass

    def update_affinity_group(self, group=None, label=None, description=None):
        try:            
            if group and label:
                self.group = group
                self.label = label
                self.description = description
                group = self.sms.update_affinity_group(self.group,
                                                       self.label,
                                                       self.description)
                return True
            else:
                logger('update_affinity_group() requires a group name and label, None specified')
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False
    
    def update_data_disk(self):
        pass

    def update_deployment_status(self):
        pass

    def update_disk(self):
        pass

    def update_dns_server(self):
        pass

    def update_hosted_service(self):
        pass

    def update_os_image(self):
        pass

    def get_os_for_role(self, deployment=None, service=None, name=None):
        try:
            self.deployment = deployment
            self.service = service                
            self.name = name
            if self.deployment and self.service and self.name:
                role = self.get_role(service=self.service, deployment=self.deployment, name=self.name)
                if role:
                    return role['os_virtual_hard_disk'].__dict__['os']
                else:
                    return None
            else:
                logger('get_os_for_role() requires deployment, service and role names, None specified')
                sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return None

    def update_role(self, *args, **kwargs):
        arg = args[0]
        try:
            if not self.verify_mandatory_params(method=inspect.stack()[0][3], params=arg):
                return False
            
            self.service = arg.service[0]
            self.deployment = arg.deployment[0]  
            self.name = arg.name[0]
            
            role = self.get_role(service=self.service, deployment=self.deployment, name=self.name)
            if role:
                pprint.pprint(role)
                self.os = self.get_os_for_role(service=self.service, deployment=self.deployment, name=self.name)
                self.size = self.get_optional_params(key='size', params=arg, default=role['role_size'])
                self.availset = self.get_optional_params(key='availset', params=arg, default=role['availability_set_name'])
                self.subnet = self.get_optional_params(key='subnet', params=arg, default=role['configuration_sets'][0]['subnet_names'][0])
                self.eps = self.get_optional_params(key='eps', params=arg, default=role['configuration_sets'][0]['input_endpoints'])
                self.rextrs = self.get_optional_params(key='rextrs', params=arg, default=None)
                self.os_disk = self.get_optional_params(key='os_disk', params=arg, default=role['os_virtual_hard_disk'])
                self.data_disk = self.get_optional_params(key='data_disk', params=arg, default=role['data_virtual_hard_disks'])
                self.async = self.get_optional_params(key='async', params=arg, default=self.default_async)
                self.readonly = self.get_optional_params(key='readonly', params=arg, default=self.default_readonly)                
            else:
                logger('%s: unable to retrieve properties for role %s' % (inspect.stack()[0][3], self.name))
                return False
           
            net_config = ConfigurationSet()
            net_config.configuration_set_type = 'NetworkConfiguration'
            subnet = Subnet()
            subnet.name = self.subnet
            subnets = Subnets()
            subnets.subnets.append(subnet.name)
            net_config.subnet_names = subnets
            eps = ConfigurationSetInputEndpoints()                
            eps = self.eps

            # -- unpack ACLs
            # TBC
            
            net_config.input_endpoints = eps
            self.net_config = net_config

            pprint.pprint(self.__dict__)

            if not self.readonly:
                try:
                    result = self.sms.update_role(self.service, self.deployment, self.name,
                                                  os_virtual_hard_disk=self.os_disk, network_config=self.net_config, availability_set_name=self.availset,
                                                  data_virtual_hard_disks=self.data_disk, role_size=self.size, role_type='PersistentVMRole',
                                                  resource_extension_references=self.rextrs, provision_guest_agent=True)
                    d = dict()
                    operation = self.sms.get_operation_status(result.request_id)
                    d['result'] = result.__dict__
                    d['operation'] = operation.__dict__
                    if not self.async:
                        pprint.pprint(d)
                        return self.wait_for_operation_status(result.request_id)
                    else:
                        return d
                except (WindowsAzureConflictError) as e:
                    logger('%s: operation in progress or resource exists, try again..' % inspect.stack()[0][3])
                    return False
            else:
                logger('%s: limited to read-only operations' % inspect.stack()[0][3])
        except Exception as e:
            logger(message=repr(e))
            return False
        
    def update_storage_account(self):
        pass

    def update_vm_image(self):
        pass

    def urlencode_sig_query_string_part(self, url):
        enc_sig = quote_plus(parse_qs(url)['sig'][0])
        enc_se = quote_plus(parse_qs(url)['se'][0])
        t = urlsplit(url)
        ql = []
        for q in t.query.split('&'):
            if q.startswith('sig='):
                ql.append('sig=' + enc_sig)                
            elif q.startswith('se='):
                ql.append('se=' + enc_se)
            else:
                ql.append(q)

        pl = [t.scheme, t.netloc, t.path, '&'.join(ql), '']
        return urlunsplit(pl)
    
    def wait_for_operation_status(self, request_id=None, status=None, timeout=None, wait=None):
        try:
            if request_id:
                self.request_id = request_id
                self.status = status
                self.wait = wait
                self.timeout = timeout
                if status is None: self.status = self.default_status
                if wait is None: self.wait = self.default_wait
                if timeout is None: self.timeout = self.default_timeout
                result = self.sms.wait_for_operation_status(self.request_id,
                                                            wait_for_status=self.status,
                                                            timeout=self.timeout,
                                                            sleep_interval=self.wait)
                if result is not None:
                    return result.__dict__
                else:
                    return False
            else:
               logger('wait_for_operation_status() requires a request ID, None specified') 
               sys.exit(1)
        except Exception as e:
            logger(message=repr(e))
            return False

    def walk_upgrade_domain(self, service=None, deployment=None, upgrade_domain=None):
        pass

    def x_ms_version(self):
        return self.sms.x_ms_version

    def xml_endpoint_fragment_from_dict(self, eps=None, acls=None):
        if eps:
            root = Element('InputEndpoints')
            for ep_el in eps:
                ep = SubElement(root, 'InputEndpoint')
                local_port = SubElement(ep, 'LocalPort')
                local_port.text = ep_el['LocalPort']
                name = SubElement(ep, 'Name')
                name.text = ep_el['Name']
                port = SubElement(ep, 'Port')
                port.text = ep_el['Port']
                protocol = SubElement(ep, 'Protocol')
                protocol.text = ep_el['Protocol']
                if acls:
                    ep_acl = SubElement(ep, 'EndpointAcl')
                    rules = SubElement(ep_acl, 'Rules')
                    i = 100
                    for acl_el in acls:
                        rule = SubElement(rules, 'Rule')
                        order = SubElement(rule, 'Order')
                        order.text = str(i)
                        action = SubElement(rule, 'Action')
                        action.text = 'permit'
                        subnet = SubElement(rule, 'RemoteSubnet')
                        subnet.text = acl_el['RemoteSubnet']
                        description = SubElement(rule, 'Description')
                        description.text = acl_el['Description']
                        i = i + 1                
            return tostring(root)
        else:
            return None

if __name__ == '__main__':
    if BaseCloudHarnessClass.log: logging.basicConfig(filename=BaseCloudHarnessClass.log_file, format='%(asctime)s %(message)s', level=logging.INFO)
    arg = args()
    if arg.provider in ['azure']:
        az = AzureCloudClass(subscription_id=arg.subscription_id[0], certificate_path=arg.certificate_path[0])

        for action in az.actions:            
            if action['action'] == arg.action[0] and action['collection']:
                pprint.pprint(az.list_collection(arg))
                sys.exit(0)
        
        if arg.action[0] in ['x_ms_version']: pprint.pprint(az.x_ms_version())
        elif arg.action[0] in ['host']: pprint.pprint(az.host())
        elif arg.action[0] in ['cert_file']: pprint.pprint(az.cert_file())
        elif arg.action[0] in ['content_type']: pprint.pprint(az.content_type())
        elif arg.action[0] in ['timeout']: pprint.pprint(az.timeout())
        elif arg.action[0] in ['sub_id']: pprint.pprint(az.sub_id())
        elif arg.action[0] in ['request_session']: pprint.pprint(az.request_session())
        elif arg.action[0] in ['requestid']: pprint.pprint(az.requestid())
        elif arg.action[0] in ['get_certificate_from_publish_settings']: az.get_certificate_from_publish_settings()
        elif arg.action[0] in ['list_resource_extension_versions']: pprint.pprint(az.list_resource_extension_versions(arg))
        elif arg.action[0] in ['list_service_certificates']: pprint.pprint(az.list_service_certificates(arg))
        elif arg.action[0] in ['list_subscription_operations']: pprint.pprint(az.list_subscription_operations(arg))
        elif arg.action[0] in ['check_hosted_service_name_availability']: pprint.pprint(az.check_hosted_service_name_availability(service=(arg.service[0] if arg.service else None)))
        elif arg.action[0] in ['check_storage_account_name_availability']: pprint.pprint(az.check_storage_account_name_availability(account=(arg.account[0] if arg.account else None)))
        elif arg.action[0] in ['create_affinity_group']: pprint.pprint(az.create_affinity_group(group=(arg.group[0] if arg.group else None),
                                                                                                label=(arg.label[0] if arg.label else None),
                                                                                                description=(arg.description[0] if arg.description else None),
                                                                                                location=(arg.location[0] if arg.location else None)))
        elif arg.action[0] in ['delete_affinity_group']: pprint.pprint(az.delete_affinity_group(group=(arg.group[0] if arg.group else None)))
        elif arg.action[0] in ['get_affinity_group_properties']: pprint.pprint(az.get_affinity_group_properties(group=(arg.group[0] if arg.group else None)))
        elif arg.action[0] in ['update_affinity_group']: pprint.pprint(az.update_affinity_group(group=(arg.group[0] if arg.group else None),
                                                                                                label=(arg.label[0] if arg.label else None),
                                                                                                description=(arg.description[0] if arg.description else None)))
        elif arg.action[0] in ['create_virtual_machine_deployment']: pprint.pprint(az.create_virtual_machine_deployment(deployment=(arg.deployment[0] if arg.deployment else None),
                                                                                                                        service=(arg.service[0] if arg.service else None),
                                                                                                                        slot=(arg.slot[0] if arg.slot else None),
                                                                                                                        label=(arg.label[0] if arg.label else None),
                                                                                                                        size=(arg.size[0] if arg.size else None),
                                                                                                                        os=(arg.os[0] if arg.os else None),
                                                                                                                        image=(arg.image[0] if arg.image else None),
                                                                                                                        availset=(arg.availset[0] if arg.availset else None),                                                                                                                        
                                                                                                                        network=(arg.network[0] if arg.network else None),
                                                                                                                        name=(arg.name[0] if arg.name else None),
                                                                                                                        username=(arg.username[0] if arg.username else None),
                                                                                                                        password=(arg.password[0] if arg.password else None),
                                                                                                                        subnet=(arg.subnet[0] if arg.subnet else None),
                                                                                                                        account=(arg.account[0] if arg.account else None)))
        elif arg.action[0] in ['add_role']: pprint.pprint(az.add_role(arg))
        elif arg.action[0] in ['get_storage_account_properties']: pprint.pprint(az.get_storage_account_properties(account=(arg.account[0] if arg.account else None)))
        elif arg.action[0] in ['get_deployment_by_slot']: pprint.pprint(az.get_deployment_by_slot(service=(arg.service[0] if arg.service else None),
                                                                                                  slot=(arg.slot[0] if arg.slot else None)))
        elif arg.action[0] in ['get_deployment_by_name']: pprint.pprint(az.get_deployment_by_name(service=(arg.service[0] if arg.service else None),
                                                                                                  deployment=(arg.deployment[0] if arg.deployment else None)))
        elif arg.action[0] in ['get_role']: pprint.pprint(az.get_role(service=(arg.service[0] if arg.service else None),
                                                                      deployment=(arg.deployment[0] if arg.deployment else None),
                                                                      name=(arg.name[0] if arg.name else None)))
        elif arg.action[0] in ['get_data_disk']: pprint.pprint(az.get_data_disk(service=(arg.service[0] if arg.service else None),
                                                                                deployment=(arg.deployment[0] if arg.deployment else None),
                                                                                name=(arg.name[0] if arg.name else None),
                                                                                lun=(arg.lun[0] if arg.lun else None)))
        elif arg.action[0] in ['get_disk']: pprint.pprint(az.get_disk(disk=(arg.disk[0] if arg.disk else None)))
        elif arg.action[0] in ['get_disk_by_role_name']: pprint.pprint(az.get_disk_by_role_name(service=(arg.service[0] if arg.service else None),
                                                                                                deployment=(arg.deployment[0] if arg.deployment else None),
                                                                                                name=(arg.name[0] if arg.name else None)))
        elif arg.action[0] in ['get_hosted_service_properties']: pprint.pprint(az.get_hosted_service_properties(service=(arg.service[0] if arg.service else None)))        
        elif arg.action[0] in ['get_management_certificate']: pprint.pprint(az.get_management_certificate(thumbprint=(arg.thumbprint[0] if arg.thumbprint else None)))        
        elif arg.action[0] in ['get_operation_status']: pprint.pprint(az.get_operation_status(request_id=(arg.request_id[0] if arg.request_id else None)))       
        elif arg.action[0] in ['delete_role']: pprint.pprint(az.delete_role(service=(arg.service[0] if arg.service else None),
                                                                            deployment=(arg.deployment[0] if arg.deployment else None),
                                                                            name=(arg.name[0] if arg.name else None),
                                                                            async=arg.async))
        elif arg.action[0] in ['delete_disk']: pprint.pprint(az.delete_disk(disk=(arg.disk[0] if arg.disk else None),
                                                                            delete_vhd=arg.delete_vhd))
        elif arg.action[0] in ['wait_for_operation_status']: pprint.pprint(az.wait_for_operation_status(request_id=(arg.request_id[0] if arg.request_id else None),
                                                                                                        status=(arg.status[0] if arg.status else None),
                                                                                                        wait=(arg.wait[0] if arg.wait else None),
                                                                                                        timeout=(arg.timeout[0] if arg.timeout else None)))
        elif arg.action[0] in ['set_endpoint_acl']: pprint.pprint(az.set_endpoint_acl(arg))
        elif arg.action[0] in ['get_endpoint_acl']: pprint.pprint(az.get_endpoint_acl(subscription_id=(arg.subscription_id[0] if arg.subscription_id else None),
                                                                                      service=(arg.service[0] if arg.service else None),
                                                                                      deployment=(arg.deployment[0] if arg.deployment else None),
                                                                                      name=(arg.name[0] if arg.name else None)))
        elif arg.action[0] in ['reboot_role_instance']: pprint.pprint(az.reboot_role_instance(service=(arg.service[0] if arg.service else None),
                                                                                              deployment=(arg.deployment[0] if arg.deployment else None),
                                                                                              name=(arg.name[0] if arg.name else None)))
        elif arg.action[0] in ['shutdown_role']: pprint.pprint(az.shutdown_role(service=(arg.service[0] if arg.service else None),
                                                                                deployment=(arg.deployment[0] if arg.deployment else None),
                                                                                name=(arg.name[0] if arg.name else None)))
        elif arg.action[0] in ['restart_role']: pprint.pprint(az.restart_role(service=(arg.service[0] if arg.service else None),
                                                                              deployment=(arg.deployment[0] if arg.deployment else None),
                                                                              name=(arg.name[0] if arg.name else None)))
        elif arg.action[0] in ['start_role']: pprint.pprint(az.start_role(service=(arg.service[0] if arg.service else None),
                                                                          deployment=(arg.deployment[0] if arg.deployment else None),
                                                                          name=(arg.name[0] if arg.name else None)))
        elif arg.action[0] in ['start_roles']: pprint.pprint(az.start_roles(service=(arg.service[0] if arg.service else None),
                                                                            deployment=(arg.deployment[0] if arg.deployment else None),
                                                                            names=(arg.name if arg.name else None)))
        elif arg.action[0] in ['shutdown_roles']: pprint.pprint(az.shutdown_roles(service=(arg.service[0] if arg.service else None),
                                                                                  deployment=(arg.deployment[0] if arg.deployment else None),
                                                                                  names=(arg.name if arg.name else None)))
        elif arg.action[0] in ['delete_dns_server']: pprint.pprint(az.delete_dns_server(service=(arg.service[0] if arg.service else None),
                                                                                        deployment=(arg.deployment[0] if arg.deployment else None),
                                                                                        name=(arg.name[0] if arg.name else None)))
        elif arg.action[0] in ['add_dns_server']: pprint.pprint(az.add_dns_server(service=(arg.service[0] if arg.service else None),
                                                                                  deployment=(arg.deployment[0] if arg.deployment else None),
                                                                                  ipaddr=(arg.ipaddr[0] if arg.ipaddr else None),
                                                                                  name=(arg.name[0] if arg.name else None)))
        elif arg.action[0] in ['get_service_certificate']: pprint.pprint(az.get_service_certificate(service=(arg.service[0] if arg.service else None),
                                                                                                    thumbprint=(arg.thumbprint[0] if arg.thumbprint else None),
                                                                                                    algorithm=(arg.algorithm[0] if arg.algorithm else None)))
        elif arg.action[0] in ['get_storage_account_keys']: pprint.pprint(az.get_storage_account_keys(account=(arg.account[0] if arg.account else None)))
        elif arg.action[0] in ['update_role']: pprint.pprint(az.update_role(arg))
        elif arg.action[0] in ['add_customscript_extension']:
            az.os = az.get_os_for_role(service=(arg.service[0] if arg.service else None),
                                       deployment=(arg.deployment[0] if arg.deployment else None),
                                       name=(arg.name[0] if arg.name else None))
            csre = az.build_customscript_resource_extension(os=az.os)
            pprint.pprint(az.update_role(deployment=(arg.deployment[0] if arg.deployment else None),
                                         service=(arg.service[0] if arg.service else None),
                                         name=(arg.name[0] if arg.name else None),
                                         rextrs=csre,
                                         async=arg.async,
                                         readonly=arg.readonly))
        elif arg.action[0] in ['add_chefclient_extension']:
            az.os = az.get_os_for_role(service=(arg.service[0] if arg.service else None),
                                       deployment=(arg.deployment[0] if arg.deployment else None),
                                       name=(arg.name[0] if arg.name else None))
            ccre = az.build_chefclient_resource_extension(os=az.os)
            pprint.pprint(az.update_role(deployment=(arg.deployment[0] if arg.deployment else None),
                                         service=(arg.service[0] if arg.service else None),
                                         name=(arg.name[0] if arg.name else None),
                                         rextrs=ccre,
                                         async=arg.async,
                                         readonly=arg.readonly))
        elif arg.action[0] in ['add_vmaccess_extension']:
            az.os = az.get_os_for_role(service=(arg.service[0] if arg.service else None),
                                       deployment=(arg.deployment[0] if arg.deployment else None),
                                       name=(arg.name[0] if arg.name else None))
            vmare = az.build_vmaccess_resource_extension(os=az.os,
                                                         username=(arg.username[0] if arg.username else None),
                                                         password=(arg.password[0] if arg.password else None),
                                                         vmaop=(arg.vmaop[0] if arg.vmaop else None))
            pprint.pprint(az.update_role(deployment=(arg.deployment[0] if arg.deployment else None),
                                         service=(arg.service[0] if arg.service else None),
                                         name=(arg.name[0] if arg.name else None),
                                         rextrs=vmare,
                                         async=arg.async,
                                         readonly=arg.readonly))
        elif arg.action[0] in ['add_ospatching_extension']:
            az.os = az.get_os_for_role(service=(arg.service[0] if arg.service else None),
                                       deployment=(arg.deployment[0] if arg.deployment else None),
                                       name=(arg.name[0] if arg.name else None))
            ospre = az.build_ospatching_resource_extension(os=az.os,
                                                           patching_disabled=arg.patching_disabled,
                                                           patching_stop=arg.patching_stop,
                                                           patching_reboot_after=(arg.patching_reboot_after[0] if arg.patching_reboot_after else None),
                                                           patching_interval=(arg.patching_interval[0] if arg.patching_interval else None),
                                                           patching_day=(arg.patching_day[0] if arg.patching_day else None),
                                                           patching_starttime=(arg.patching_starttime[0] if arg.patching_starttime else None),
                                                           patching_category=(arg.patching_category[0] if arg.patching_category else None),
                                                           patching_duration=(arg.patching_duration[0] if arg.patching_duration else None),
                                                           patching_local=arg.patching_local,
                                                           patching_oneoff=arg.patching_oneoff)
            pprint.pprint(az.update_role(deployment=(arg.deployment[0] if arg.deployment else None),
                                         service=(arg.service[0] if arg.service else None),
                                         name=(arg.name[0] if arg.name else None),
                                         rextrs=ospre,
                                         async=arg.async,
                                         readonly=arg.readonly))
        elif arg.action[0] in ['get_role_properties_xml']:
            pprint.pprint(az.get_role_properties_xml(deployment=arg.deployment[0] if arg.deployment else None,
                                                     service=arg.service[0] if arg.service else None,
                                                     name=arg.name[0] if arg.name else None))
        elif arg.action[0] in ['add_data_disk']: pprint.pprint(az.add_data_disk(arg))
        else:
            logger(message='Unknown action' % arg.action)
            sys.exit(1)
    else:
        logger(message='Unknown provider' % arg.provider)
        sys.exit(1)
