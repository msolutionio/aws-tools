#!/bin/bash
export PATH=$PATH:/usr/local/bin/:/usr/bin

command_name="ebs-snapshot.sh"

# Safety feature: exit script if error is returned, or if variables not set.
# Exit if a pipeline results in an error.
set -ue
set -o pipefail

## Automatic EBS Volume Snapshot Creation & Clean-Up Script
#
# Written by Casey Labs Inc. (https://www.caseylabs.com)
# Contact us for all your Amazon Web Services Consulting needs!
# Script Github repo: https://github.com/CaseyLabs/aws-ec2-ebs-automatic-snapshot-bash
#
# Additonal credits: Log function by Alan Franzoni; Pre-req check by Colin Johnson
#
# PURPOSE: This Bash script can be used to take automatic snapshots of your Linux EC2 instance. Script process:
# - Determine the instance ID of the EC2 server on which the script runs
# - Gather a list of all volume IDs attached to that instance
# - Take a snapshot of each attached volume
# - The script will then delete all associated snapshots taken by the script that are older than 7 days
#
# DISCLAIMER: This script deletes snapshots (though only the ones that it creates). 
# Make sure that you understand how the script works. No responsibility accepted in event of accidental data loss.
#


## Variable Declartions ##

# Set Logging Options
logfile="/var/log/ebs-snapshot.log"
logfile_max_lines="5000"

# How many days do you wish to retain backups for? Default: 7 days
retention_days="7"
retention_date_in_seconds=$(date +%s --date "$retention_days days ago")


## Function Declarations ##

# Function: Print usage.
print_usage() {
  cat <<EOF
$command_name,
Usage
    $command_name 
            [-v <EBS Volume Ids>] [-p <AWS CLI profile>] [-r <AWS region>]

    Retrieved all the EBS volume ids of your Amazon Web Service (AWS) Virtual
    Private Cloud (VPC).
    Create snapshot for each one of them with a description matching the
    pattern:
      'vol-aaaaaaaa-i-bbbbbbbb-backup-2000-12-31'
    Add a tag 'CreatedBy' with the value 'AutomatedBackup' to differenciate the
    snapshots.
    Add a tag 'Name' with the name of the instance and the device name of the
    EBS volume, if there is no name the id is used instead.

    Check if one of the snapshot is older than 7 days and delete it if one is
    found.

    The snapshots are created before the deletion of any previous snapshots.
    And if the creation of one snapshot failed the script is exited avoiding
    the deletion of any previous snapshot.

    -v Volume Id (string)
        Create and delete snapshots only for the EBS volume ids provided.
        If more than one id is provided, use quotes:
            $command_name -v "vol-aaaaaaaa vol-bbbbbbbb"
        By default the creation and delation of snapshots will happen for all
        the EBS of your VPC.

    -p AWS CLI profile (string)
        Use the AWS Command Line Interface profile provided instead of the
        'ebs-snapshot' profile by default. By default the configuration file
        location for the different profile is '\$HOME/.aws/config'.

    -r AWS Region (string)
        Use the provided region to search for EBS.
        By default the region value is 'us-east-1'.

    -h
        Print this help.

EOF
}

# Function: Set default value to the differents global variables
default_value() {
  aws_cli_profile='ebs-snapshot'
  region='us-east-1'
  volume_list=$(aws ec2 describe-volumes --profile $aws_cli_profile --region $region --output=text --query Volumes[].VolumeId)
}

# Function: Setup command line arguments
options_setup() {
  while getopts r:v:p:h option; do
    case "$option" in
      r) region="$OPTARG" ;;
      v) volume_list="$OPTARG" ;;
      p) aws_cli_profile="$OPTARG" ;;
      h) print_usage; exit 0 ;;
      *) print_usage; exit 3 ;;
    esac
  done
}

# Function: Setup logfile and redirect stdout/stderr.
log_setup() {
  # Check if logfile exists and is writable.
  ( [ -e "$logfile" ] || touch "$logfile" ) && [ ! -w "$logfile" ] && echo "ERROR: Cannot write to $logfile. Check permissions or sudo access." && exit 1

  tmplog=$(tail -n $logfile_max_lines $logfile 2>/dev/null) && echo "${tmplog}" > $logfile
  exec > >(tee -a $logfile)
  exec 2>&1
}

# Function: Log an event.
log() {
  echo "[$(date +"%Y-%m-%d"+"%T")]: $*"
}

# Function: Confirm that the AWS CLI and related tools are installed.
prerequisite_check() {
  for prerequisite in aws wget; do
    hash $prerequisite &> /dev/null
    if [[ $? == 1 ]]; then
      echo "In order to use this script, the executable \"$prerequisite\" must be installed." 1>&2; exit 70
    fi
  done
}

# Function: Snapshot all volumes attached to this instance.
snapshot_volumes() {
  for volume_id in $volume_list; do
    log "Volume ID is $volume_id"

    # Get the attached instance id to add to the description so we can easily tell which volume this is.
    instance_id=$(aws ec2 describe-volumes --profile $aws_cli_profile --region $region --output=text --volume-ids $volume_id --query 'Volumes[0].Attachments[0].InstanceId')

    # Take a snapshot of the current volume, and capture the resulting snapshot ID
    if [ -z $instance_id ]; then
      instance_id='detached'
    fi
    snapshot_description="$volume_id-$instance_id-backup-$(date +%Y-%m-%d)"

    snapshot_id=$(aws ec2 create-snapshot --profile $aws_cli_profile --region $region --output=text --description $snapshot_description --volume-id $volume_id --query 'SnapshotId')
    log "New snapshot is $snapshot_id"

    volume_name=$(aws ec2 describe-volumes --profile $aws_cli_profile --region $region --output=text --volume-ids $volume_id --query 'Volumes[0].Attachments[0].Device')
    instance_hostname=$(aws ec2 describe-tags --profile $aws_cli_profile --region $region --output=text --filter "Name=resource-id,Values=$instance_id" "Name=key,Values=fqdn" --query 'Tags[].Value')

    if [ -z $instance_hostname ]; then
      instance_hostname=$instance_id
    fi
    if [ -z $volume_name ]; then
      volume_name=$volume_id
    fi
    aws ec2 create-tags --profile $aws_cli_profile --region $region --resource $snapshot_id --tags "Key=Name,Value=$instance_hostname-$volume_name"

    # Add a "CreatedBy:AutomatedBackup" tag to the resulting snapshot.
    # Why? Because we only want to purge snapshots taken by the script later, and not delete snapshots manually taken.
    aws ec2 create-tags --profile $aws_cli_profile --region $region --resource $snapshot_id --tags "Key=CreatedBy,Value=AutomatedBackup"
  done
}

# Function: Cleanup all snapshots associated with this instance that are older than $retention_days
cleanup_snapshots() {
  for volume_id in $volume_list; do
    snapshot_list=$(aws ec2 describe-snapshots --profile $aws_cli_profile --region $region --output=text --filters "Name=volume-id,Values=$volume_id" "Name=tag:CreatedBy,Values=AutomatedBackup" --query 'Snapshots[].SnapshotId')
    for snapshot in $snapshot_list; do
      log "Checking $snapshot..."
      # Check age of snapshot
      snapshot_date=$(aws ec2 describe-snapshots --profile $aws_cli_profile --region $region --output=text --snapshot-ids $snapshot --query 'Snapshots[].StartTime' | awk -F "T" '{printf "%s\n", $1}')
      snapshot_date_in_seconds=$(date "--date=$snapshot_date" +%s)
      snapshot_description=$(aws ec2 describe-snapshots --profile $aws_cli_profile --region $region --snapshot-id $snapshot --query 'Snapshots[].Description')

      if (( $snapshot_date_in_seconds <= $retention_date_in_seconds )); then
        log "DELETING snapshot $snapshot. Description: $snapshot_description ..."
        aws ec2 delete-snapshot --profile $aws_cli_profile --region $region --snapshot-id $snapshot
      else
        log "Not deleting snapshot $snapshot. Description: $snapshot_description ..."
      fi
    done
  done
} 


## SCRIPT COMMANDS ##

log_setup
prerequisite_check

default_value
options_setup "$@"

snapshot_volumes
cleanup_snapshots
