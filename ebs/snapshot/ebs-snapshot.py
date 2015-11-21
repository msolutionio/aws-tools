#!/usr/bin/python

import sys
import argparse
import logging
import boto3
import botocore
from datetime import datetime, date
import time

command_name='ebs-snapshot.py'

## Function Declarations

# Function: Initialize logging
def logging_setup():
    logger = logging.getLogger('ebs-snapshot')
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler('/var/log/ebs-snapshot.log')
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)

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
            help = 'volume help')
    return parser.parse_args()

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

def is_snapshot_expired(snapshot_info):
    for tag in snapshot_info['Tags']:
        if tag['Key'] == 'ExpirationTime':
            expiration_time = int(tag['Value'])
            break
    else:
        expiration_time = None
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

def get_volume_ids_list():
    try:
        logger.info('Getting volume ids list')
        volumes_info = ec2.describe_volumes()['Volumes']
        volume_ids = []
        for volume_info in volumes_info:
            volume_ids.append(volume_info['VolumeId'])
        return volume_ids
    except botocore.exceptions.ClientError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('An unknown error occured when Getting volume ids list: ' + str(e))
        sys.exit(2)

## Variable Declarations ##

seconds_in_day = 60 * 60 * 24
logger = logging_setup()
args = parse_options()
ec2 = initialize_aws_api()

## Script ##

try:
    logger.info('STARTING')
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
    sys.exit(2)

