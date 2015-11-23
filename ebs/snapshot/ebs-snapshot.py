#!/usr/bin/python

## Automatic EBS Volume Snapshot Creation & Clean-Up Python Script
#
# Written by MSolution. (http://www.msolution.io)
# Script Github repo: https://raw.githubusercontent.com/msolutionio/aws-tools/master/ebs/snapshot/ebs-snapshot.py
#
# PURPOSE: This Python script can be used to take automatic snapshots of your EBS volumes. Script process:
# - Determine the list of EBS volumes to snapshot
# - Gather information for each EBS volume
# - Take a snapshot of each EBS volume
# - The script will then delete all associated snapshots taken by the script that are older than the specified expiration value associated at the snapshot creation (by default 30 days)
#
# DISCLAIMER: This script deletes snapshots (though only the ones that it creates). 
# Make sure that you understand how the script works. No responsibility accepted in event of accidental data loss.
#

import sys
import argparse
import logging
import boto3
import botocore
from datetime import datetime, date
import time

## Function Declarations

# Function: Initialize logging
def logging_setup():
    logger = logging.getLogger('ebs-snapshot')
    logger.setLevel(logging.DEBUG)

    # Send all the level of log in the log file
    try:
        file_handler = logging.FileHandler('/var/log/ebs-snapshot.log')
    except IOError as e:
        print(str(e))
        sys.exit(1)
    file_handler.setLevel(logging.DEBUG)

    # Display error on the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)

    # Setup a log format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Function: Initialize arguments parsing
def parse_options():
    parser = argparse.ArgumentParser(prog = command_name, usage = '%(prog)s [options]')
    parser.add_argument(
            '-v',
            '--volume-ids',
            type = str,
            nargs = '+',
            default = None,
            help = 'Create and delete snapshot for the specified EBS volumes')
    parser.add_argument(
            '-p',
            '--profile',
            type = str,
            nargs = '?',
            default = 'ebs-snapshot',
            help = 'Use specific AWS profile (default \'ebs-default\')')
    parser.add_argument(
            '-e',
            '--expire-after',
            type = int,
            nargs = '?',
            default = 30,
            help = 'Define a specific expiration time in days (default 30 days)')
    parser.add_argument(
            '-r',
            '--region',
            type = str,
            nargs = '?',
            default = 'us-east-1',
            help = 'Use specific AWS region (default \'us-east-1\')')
    parser.add_argument(
            '-l',
            '--list-volumes',
            action = 'store_true',
            help = 'List all EBS volumes')
    return parser.parse_args()

# Function: Initialize the AWS API with the provided credential or the default one
def initialize_aws_api():
    try:
        logger.info('Initializing AWS API with profile: ' + args.profile + ' and region: ' + args.region)
        session = boto3.session.Session(
                region_name = args.region,
                profile_name = args.profile)
        logger.info('Initialized AWS API with profile: ' + args.profile + ' and region: ' + args.region)
        logger.info('Initializing EC2 client')
        ec2 = session.client(
                service_name = 'ec2')
        logger.info('Initialized EC2 client')
        return ec2
    except botocore.exceptions.ProfileNotFound as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('An error occured when Initializing AWS API with profile: ' + args.profile + ' and region: ' + args.region + ': ' + str(e))
        sys.exit(2)

# Function: Gather information about the provided volume ID
def get_volume_infos(volume_id):
    try:
        logger.info('Getting informations for the volume ' + volume_id)
        volume_infos = ec2.describe_volumes(
                VolumeIds = [volume_id],
                )['Volumes'][0]
        return volume_infos
    except botocore.exceptions.ClientError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('An error occured when Getting informations for the volume ' + volume_id + ': ' + str(e))
        sys.exit(2)

# Function: Create a snapshot for the provided volume ID
def create_snapshot(volume_id, description):
    try:
        logger.info('Creating snapshot for the volume ' + volume_id)
        snapshot_id = ec2.create_snapshot(
                VolumeId = volume_id,
                Description = description
                )['SnapshotId']
        logger.info('Created snapshot for the volume ' + volume_id + ' is ' + snapshot_id)
        return snapshot_id
    except botocore.exceptions.ClientError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('An error occured when Created snapshot for the volume ' + volume_id + ': ' + str(e))
        sys.exit(2)

# Function: Gather the hostname of the instance ID provided
def get_instance_hostname(instance_id):
    try:
        logger.info('Getting instance hostname for the instance ' + instance_id)
        instance_hostname = ec2.describe_tags(
                Filters = [
                    {
                        'Name': 'resource-id',
                        'Values': [instance_id]
                    },
                    {
                        'Name': 'key',
                        'Values': ['fqdn']
                    }
                ])

        # If the 'fqdn' tag is not found, we use the instance ID instead
        if len(instance_hostname['Tags']) > 0:
            return instance_hostname['Tags'][0]['Value']
        else:
            return instance_id
    except botocore.exceptions.ClientError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('An error occured when Getting instance hostname for the instance ' + instance_id + ': ' + str(e))
        sys.exit(2)

# Function: Create a tag 'key' for the resource 'resource' with the value 'value'
def create_tag(resource, key, value):
    try:
        logger.info('Creating tag for the resource ' + resource)
        ec2.create_tags(
                Resources = [resource],
                Tags = [
                    {
                        'Key': key,
                        'Value': value
                    }
                ])
        logger.info('Created tag for the resource ' + resource + ' is Key:' + key + ', Value:' + value)
    except botocore.exceptions.ClientError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('An error occured when Creating tag for resource ' + resource + ': ' + str(e))
        sys.exit(2)

# Function: Snapshot all volumes present in the volume_list argument
def snapshot_volumes(volume_list):
    for volume_id in volume_list:
        logger.info('Snapshotting volume id ' + volume_id)

        volume_infos = get_volume_infos(volume_id)

        if len(volume_infos['Attachments']) > 0:
            instance_id = volume_infos['Attachments'][0]['InstanceId']
            volume_name = volume_infos['Attachments'][0]['Device']
        else:
            instance_id = 'detached'
            volume_name = volume_id

        snapshot_description = volume_id + '-' + instance_id + '-backup-' + str(date.today())
        
        snapshot_id = create_snapshot(volume_id, snapshot_description)

        instance_hostname = get_instance_hostname(instance_id)

        create_tag(snapshot_id, 'Name', instance_hostname + '-' + volume_name)
        create_tag(snapshot_id, 'ExpirationTime', str(seconds_in_day * args.expire_after))
        create_tag(snapshot_id, 'CreatedBy', 'AutomatedBackup')

        logger.info('Snapshotted volume id ' + volume_id)

# Function: Get a list of snapshots associated with the volume IDs provided, return a list of structure not only the snapshot ID
def get_snapshots_info(volume_list):
    try:
        logger.info('Getting snapshots informations')
        snapshots_info = ec2.describe_snapshots(
                Filters = [
                    {
                        'Name': 'volume-id',
                        'Values': volume_list
                    },
                    {
                        'Name': 'tag:CreatedBy',
                        'Values': ['AutomatedBackup']
                    }
                ])
        return snapshots_info['Snapshots']
    except botocore.exceptions.ClientError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('An error occured when Getting snapshots informations: ' + str(e))
        sys.exit(2)

# Function: Check if the snapshot is expired
def is_snapshot_expired(snapshot_info):
    for tag in snapshot_info['Tags']:
        if tag['Key'] == 'ExpirationTime':
            expiration_time = int(tag['Value'])
            break
    else:
        expiration_time = None
        logger.warning('Snapshot ' + snapshot_id + ' does not have an ExpirationTime tag')

    # If an ExpirationTime tag is found, we compare the actual datetime value minus the snapshot creation datetime with the expiration duration value
    # Datetime are UTC+0 based
    if (expiration_time != None) and (time.mktime(datetime.utcnow().timetuple()) - time.mktime(snapshot_info['StartTime'].timetuple()) > expiration_time):
        return True
    else:
        return False

def delete_snapshot(snapshot_id):
    try:
        logger.info('Deleting snapshot ' + snapshot_id)
        ec2.delete_snapshot(
                SnapshotId = snapshot_id)
        logger.info('Deleted snapshot ' + snapshot_id)
    except botocore.exceptions.ClientError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('An unknown error occured when Deleting snapshot ' + snapshot_id + ': ' + str(e))
        sys.exit(2)

def cleanup_snapshots(volume_list):
    snapshot_list = get_snapshots_info(volume_list)
    for snapshot in snapshot_list:
        logger.info('Checking snapshot ' + snapshot['SnapshotId'])

        if is_snapshot_expired(snapshot):
            logger.info('DELETING snapshot ' + snapshot['SnapshotId'] + '. Description: ' + snapshot['Description'])
            delete_snapshot(snapshot['SnapshotId'])
        else:
            logger.info('Not deleting snapshot ' + snapshot['SnapshotId'] + '. Description: ' + snapshot['Description'])

# Function: Return a list of array with all the EBS volumes informations
def get_volumes_infos_list():
    try:
        logger.info('Getting volumes informations list')
        volumes_infos = ec2.describe_volumes()['Volumes']
        return volumes_infos
    except botocore.exceptions.ClientError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('An unknown error occured when Getting volumes informations list: ' + str(e))
        sys.exit(2)

def get_volume_ids_list():
    volume_ids = []
    for volume_info in get_volumes_infos_list():
        volume_ids.append(volume_info['VolumeId'])
    return volume_ids

# Function: Display EBS volumes informations
def print_volumes_infos():
    for volume_info in get_volumes_infos_list():
        if len(volume_info['SnapshotId']) == 0:
            volume_info['SnapshotId'] = 'No snapshot'
        if volume_info['Attachments'] != None and len(volume_info['Attachments']) > 0:
            print(volume_info['VolumeId'] + '	' + volume_info['SnapshotId'] + '	' + volume_info['Attachments'][0]['State'] + '	' + volume_info['Attachments'][0]['InstanceId'] + '	' + volume_info['Attachments'][0]['Device'])
        else:
            print(volume_info['VolumeId'] + '	' + volume_info['SnapshotId'])
    sys.exit(0)

## Variable Declarations ##

command_name='ebs-snapshot.py'
seconds_in_day = 60 * 60 * 24
logger = logging_setup()
args = parse_options()
ec2 = initialize_aws_api()

## Script ##

try:
    logger.info('STARTING')
    if args.list_volumes:
        print_volumes_infos()
    if args.volume_ids == None:
        args.volume_ids = get_volume_ids_list()
    volume_ids_list = list(set(args.volume_ids))
    snapshot_volumes(volume_ids_list)
    cleanup_snapshots(volume_ids_list)
    
    logger.info('ENDING')
except KeyboardInterrupt as e:
    logger.error('Aborted by user')
    sys.exit(1)
except Exception as e:
    logger.error('An unknown error occured:' + str(e))
    raise
    sys.exit(2)

